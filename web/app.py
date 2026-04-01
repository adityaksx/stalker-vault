import sys, shutil, uuid
from pathlib import Path
from typing import Optional
import re
import httpx
import instaloader
import asyncio
import os
import traceback
import io
import json
import random

from PIL import Image
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from contextlib import asynccontextmanager
from playwright.sync_api import sync_playwright

BASE_DIR     = Path(__file__).parent
ROOT_DIR     = BASE_DIR.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
STORAGE_DIR  = ROOT_DIR / "storage"
MIN_PFP_SIZE = 250  # reject anything smaller than 300x300
STATE_FILE = Path(__file__).parent / "ig_browser_state.json"
_executor = ThreadPoolExecutor(max_workers=2)

load_dotenv()   # loads .env file automatically

IG_USER = os.getenv("IG_USERNAME", "")
IG_PASS = os.getenv("IG_PASSWORD", "")

_il = instaloader.Instaloader(
    download_pictures=False,   # we handle saving ourselves
    quiet=True,
    request_timeout=10,
)

sys.path.insert(0, str(ROOT_DIR))

SESSION_FILE = Path(__file__).parent / ".ig_session"

@asynccontextmanager
async def lifespan(app: FastAPI):
    from database.db import init_db
    init_db()

    # 1. Start Instaloader session
    if IG_USER and IG_PASS:
        try:
            if SESSION_FILE.exists():
                _il.load_session_from_file(IG_USER, str(SESSION_FILE))
                print(f"[✓] Instagram session loaded for @{IG_USER}")
            else:
                _il.login(IG_USER, IG_PASS)
                _il.save_session_to_file(str(SESSION_FILE))
                print(f"[✓] Instagram logged in + session saved for @{IG_USER}")
        except Exception as ex:
            print(f"[!] Instagram login failed: {ex}")
    yield  # ─── APP IS RUNNING ───


app = FastAPI(title="Vault", lifespan=lifespan)


STORAGE_DIR.mkdir(parents=True, exist_ok=True)
(FRONTEND_DIR / "static").mkdir(parents=True, exist_ok=True)

app.mount("/static",   StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")
app.mount("/storage",  StaticFiles(directory=str(STORAGE_DIR)),              name="storage")

# ── Helpers ──
TYPE_FOLDER = {
    "profile_pic": "images",
    "photo":       "images",
    "screenshot":  "images",
    "video":       "videos",
    "audio":       "audio",
    "repo_zip":    "files",
    "other":       "files",
}

def safe_folder_name(name: str) -> str:
    # Remove characters not safe for folder names, collapse spaces
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name)
    s = re.sub(r'\s+', '_', s.strip())
    return s or "unknown"

def get_person_dir(pid: int, person_name: str, media_type: str) -> tuple[Path, str, str]:
    folder      = TYPE_FOLDER.get(media_type, "files")
    safe_name   = safe_folder_name(person_name)
    d = STORAGE_DIR / safe_name / folder
    d.mkdir(parents=True, exist_ok=True)
    return d, folder, safe_name

# ── Pages ──
@app.get("/", response_class=HTMLResponse)
def index():
    return (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")

@app.get("/person/{pid}", response_class=HTMLResponse)
def person_page(pid: int):
    return (FRONTEND_DIR / "person.html").read_text(encoding="utf-8")

# ── People ──
@app.get("/api/people")
def api_list():
    from database.db import get_all_people
    rows = get_all_people()
    return {"people": [
        {"id":r[0],"name":r[1],"added_at":r[2],"insta":r[3],"profile_pic":r[4],"tag":r[5]}
        for r in rows
    ]}

@app.post("/api/people")
async def api_create(name: str = Form(...)):
    from database.db import create_person
    pid = create_person(name)
    return {"ok": True, "id": pid}

@app.patch("/api/people/{pid}")
async def api_update_name(pid: int, name: str = Form(...)):
    from database.db import update_person_name, get_person
    row = get_person(pid)
    if row:
        old_folder = STORAGE_DIR / safe_folder_name(row[1])
        new_folder = STORAGE_DIR / safe_folder_name(name)
        if old_folder.exists() and not new_folder.exists():
            old_folder.rename(new_folder)
    update_person_name(pid, name)
    return {"ok": True}

@app.delete("/api/people/{pid}")
def api_delete(pid: int):
    from database.db import delete_person, get_person
    row = get_person(pid)
    if row:
        safe_name = safe_folder_name(row[1])
        folder = STORAGE_DIR / safe_name
        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)
    delete_person(pid)
    return {"ok": True}

@app.get("/api/people/{pid}")
def api_get(pid: int):
    from database.db import get_person, get_fields, get_media
    row = get_person(pid)
    if not row: raise HTTPException(404, "Not found")
    fields = get_fields(pid)
    media  = get_media(pid)
    return {
        "id": row[0], "name": row[1], "added_at": row[2],
        "fields": [{"id":f[0],"type":f[1],"label":f[2],"value":f[3],"added_at":f[4]} for f in fields],
        "media":  [{"id":m[0],"type":m[1],"filename":m[2],"path":m[3],"local_path":m[6],"caption":m[4],"added_at":m[5]} for m in media]
    }

# ── Fields ──
@app.post("/api/people/{pid}/fields")
async def api_add_field(
    pid:        int,
    field_type: str           = Form(...),
    value:      str           = Form(...),
    label:      Optional[str] = Form(default=None),
):
    from database.db import add_field
    fid = add_field(pid, field_type, value, label)
    return {"ok": True, "id": fid}

@app.delete("/api/fields/{fid}")
def api_delete_field(fid: int):
    from database.db import delete_field
    delete_field(fid)
    return {"ok": True}

# ── Media ──
@app.post("/api/people/{pid}/media")
async def api_add_media(
    pid:        int,
    media_type: str                  = Form(...),
    caption:    Optional[str]        = Form(default=None),
    repo_url:   Optional[str]        = Form(default=None),
    file:       Optional[UploadFile] = File(default=None),
):
    from database.db import add_media, get_person

    if media_type == "repo_url":
        if not repo_url:
            raise HTTPException(400, "repo_url required")
        mid = add_media(pid, "repo_url", repo_url,
                        filename=None, caption=caption, local_path=None)
        return {"ok": True, "id": mid}

    if not file or not file.filename:
        raise HTTPException(400, "No file provided")

    # Get person name for folder
    person_row  = get_person(pid)
    person_name = person_row[1] if person_row else f"person_{pid}"

    original_name        = file.filename
    ext                  = Path(original_name).suffix.lower()
    uuid_name            = f"{uuid.uuid4().hex}{ext}"

    dest_dir, folder_type, safe_name = get_person_dir(pid, person_name, media_type)
    dest       = dest_dir / uuid_name
    url        = f"/storage/{safe_name}/{folder_type}/{uuid_name}"

    # Use forward slashes for local_path so it displays cleanly in UI
    local_path = str(dest.resolve()).replace("\\", "/")

    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f) # noqa

    mid = add_media(pid, media_type, url,
                    filename=original_name, caption=caption, local_path=local_path)
    return {"ok": True, "id": mid, "path": url}

@app.delete("/api/media/{mid}")
def api_delete_media(mid: int):
    from database.db import get_media_by_id, delete_media
    # fetch path before deleting
    row = get_media_by_id(mid)
    if row and row["local_path"]:
        try:
            Path(row["local_path"]).unlink(missing_ok=True)
        except Exception:
            pass
    delete_media(mid)
    return {"ok": True}

@app.patch("/api/media/{mid}/rename")
async def api_rename_media(mid: int, filename: str = Form(...)):
    from database.db import rename_media, get_media_by_id
    row = get_media_by_id(mid)
    if row and row[7]:  # local_path is index 7
        old_path = Path(row[7])
        new_path = old_path.parent / filename
        if old_path.exists() and not new_path.exists():
            old_path.rename(new_path)
            # Update local_path and url path too
            new_url = "/".join(row[3].split("/")[:-1]) + "/" + filename
            from database.db import update_media_path
            update_media_path(mid, new_url, str(new_path).replace("\\", "/"))
    rename_media(mid, filename)
    return {"ok": True}

# ── Instagram Snapshots ──

@app.get("/api/people/{pid}/ig-snapshots")
def api_ig_snapshots(pid: int):
    from database.db import get_ig_snapshots
    rows = get_ig_snapshots(pid)
    return {"snapshots": [
        {"id":r[0],"ig_username":r[1],"list_type":r[2],"label":r[3],"imported_at":r[4],"count":r[5]}
        for r in rows
    ]}

@app.post("/api/people/{pid}/ig-snapshots")
async def api_ig_import(
    pid: int,
    ig_username: str = Form(...),
    list_type: str = Form(...),
    label: Optional[str] = Form(default=None),
    csv_data: str = Form(...),
):

    hd_count       = 0
    rejected_count = 0
    from database.db import create_ig_snapshot, add_ig_entry, get_person
    import csv, io

    person_row  = get_person(pid)
    person_name = person_row[1] if person_row else f"person_{pid}"
    safe_name   = safe_folder_name(person_name)

    sample = csv_data[:500]
    delim = ';' if ';' in sample and ',' not in sample else ','
    reader = csv.DictReader(io.StringIO(csv_data), delimiter=delim)
    entries = []
    for row in reader:
        uname = (row.get('username') or '').strip().strip('"')
        fname = (row.get('full_name') or '').strip().strip('"')
        pic   = (row.get('profile_pic_url') or '').strip().strip('"')
        if uname:
            entries.append((uname, fname, pic))

    if not entries:
        raise HTTPException(400, "No valid entries in CSV")

    sid     = create_ig_snapshot(pid, ig_username, list_type, label)
    pic_dir = STORAGE_DIR / safe_name / "ig_pics"
    pic_dir.mkdir(parents=True, exist_ok=True)

    hd_count       = 0
    rejected_count = 0

    # per request delay
    await asyncio.sleep(random.uniform(1.5, 4))

    for i, (uname, fname, pic_url) in enumerate(entries):
        await asyncio.sleep(random.uniform(1.5, 3.5))
        if i > 0 and i % 20 == 0:
            print(f"[pause] {i}/{len(entries)} done — sleeping 10s")
            await asyncio.sleep(10)

        local_path, pic_url = await fetch_and_save_pfp(uname, pic_dir)

        if local_path:
            hd_count += 1
        else:
            rejected_count += 1

        add_ig_entry(sid, uname, fname, pic_url, local_path)

    print(f"[import] Done — ✅ HD: {hd_count}  ❌ rejected/skipped: {rejected_count}  Total: {len(entries)}")
    return {"ok": True, "snapshot_id": sid, "count": len(entries)}


@app.get("/api/ig-snapshots/diff")
def api_ig_diff(old_sid: int, new_sid: int):
    from database.db import get_ig_entries
    old_map = {e[1]: e for e in get_ig_entries(old_sid)}
    new_map = {e[1]: e for e in get_ig_entries(new_sid)}
    old_set, new_set = set(old_map), set(new_map)

    def fmt(e): return {"username":e[1],"full_name":e[2],"profile_pic_url":e[3],"local_pic_path":e[4]}

    return {
        "unfollowed": sorted([fmt(old_map[u]) for u in old_set - new_set], key=lambda x: x["username"]),
        "new":        sorted([fmt(new_map[u]) for u in new_set - old_set], key=lambda x: x["username"]),
        "retained":   len(old_set & new_set),
        "old_count":  len(old_set),
        "new_count":  len(new_set),
    }

@app.get("/api/ig-snapshots/{sid}/entries")
def api_ig_entries(sid: int):
    from database.db import get_ig_entries
    rows = get_ig_entries(sid)
    return {"entries": [
        {"id":r[0],"username":r[1],"full_name":r[2],"profile_pic_url":r[3],"local_pic_path":r[4]}
        for r in rows
    ]}

@app.delete("/api/ig-snapshots/{sid}")
def api_ig_delete_snapshot(sid: int):
    from database.db import delete_ig_snapshot
    delete_ig_snapshot(sid)
    return {"ok": True}


# ─── Cookie Helper ────────────────────────────────────────────────────────────

def _get_browser_cookies() -> dict:
    """Extract Instagram cookies from saved Playwright browser session."""
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())
            return {
                c["name"]: c["value"]
                for c in state.get("cookies", [])
                if "instagram.com" in c.get("domain", "") and c.get("value")
            }
        except Exception as e:
            print(f"[cookie-warn] Could not read browser state: {e}")
    return {}


# ─── Image Size Validator ─────────────────────────────────────────────────────

def check_image_size(data: bytes, username: str) -> bool:
    try:
        img = Image.open(io.BytesIO(data))
        w, h = img.size
        label = "✅ HD" if w >= 300 else "⚠️ LOW-RES"
        print(f"[{label}] @{username} — {w}x{h}")
        return w >= 100  # accept everything — 150px is best Instagram gives for some accounts
    except Exception as e:
        print(f"[size-check-error] @{username} — {e}")
        return len(data) > 3000


# ─── Tier 1: Direct API ───────────────────────────────────────────────────────
async def fetch_pfp_api(username: str):
    ig_cookies = _get_browser_cookies()
    if not ig_cookies:
        try:
            ig_cookies = {c.name: c.value for c in _il.context._session.cookies if c.value}
        except Exception:
            pass

    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "x-ig-app-id": "936619743392459",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }

    async with httpx.AsyncClient(cookies=ig_cookies) as client:
        try:
            r = await client.get(
                f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}",
                headers=headers, timeout=10.0,
            )
            print(f"[api-status] @{username} — HTTP {r.status_code}")
            if r.status_code != 200:
                print(f"[api-fail] @{username} — Status: {r.status_code}")
                return None, None

            user = r.json().get("data", {}).get("user", {})
            if not user:
                print(f"[api-empty] @{username} — no user in response")
                return None, None

            versions = user.get("hd_profile_pic_versions") or []
            best_version_url = max(versions, key=lambda x: x.get("width", 0)).get("url") if versions else None

            hd_url = (
                user.get("hd_profile_pic_url_info", {}).get("url")
                or best_version_url
                or user.get("profile_pic_url_hd")
                or user.get("profile_pic_url")
            )

            if not hd_url:
                print(f"[api-nourl] @{username} — no pic URL in response")
                return None, None

            print(f"[api-url] @{username} — {hd_url}")
            img = await client.get(hd_url, timeout=15.0, follow_redirects=True)
            if img.status_code == 200 and check_image_size(img.content, username):
                return img.content, hd_url
            else:
                print(f"[api-img-fail] @{username} — img HTTP {img.status_code}")

        except Exception as e:
            print(f"[api-error] @{username} — {e}")

    return None, None


async def fetch_pfp_api_with_retry(username: str):
    for attempt in range(2):
        data, url = await fetch_pfp_api(username)
        if data:
            return data, url
        if attempt == 0:
            # Check if last call was rate-limited — wait longer
            wait = random.uniform(8, 15)   # was 2-5, now 8-15 for 429 recovery
            print(f"[api-retry] @{username} — retrying in {wait:.1f}s")
            await asyncio.sleep(wait)
    return None, None

def _playwright_fetch_sync(username: str):
    print(f"[debug] STATE_FILE = {STATE_FILE}, exists = {STATE_FILE.exists()}")
    captured_url = None

    def on_response(response):
        nonlocal captured_url
        if "web_profile_info" in response.url and captured_url is None:
            try:
                data = response.json()
                user = data.get("data", {}).get("user", {})
                versions = user.get("hd_profile_pic_versions") or []
                best_version_url = (
                    max(versions, key=lambda x: x.get("width", 0)).get("url")
                    if versions else None
                )
                captured_url = (
                    user.get("hd_profile_pic_url_info", {}).get("url")
                    or best_version_url
                    or user.get("profile_pic_url_hd")
                    or user.get("profile_pic_url")
                )
                if captured_url:
                    print(f"[playwright-intercept] @{username} — captured URL via response listener")
            except Exception as e:
                print(f"[playwright-intercept-err] @{username} — {e}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )

            if STATE_FILE.exists():
                context = browser.new_context(
                    storage_state=str(STATE_FILE),
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                )
                print(f"[playwright] Loaded saved browser session from {STATE_FILE.name}")
            else:
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    )
                )
                try:
                    ig_cookies = [
                        {"name": c.name, "value": c.value,
                         "domain": ".instagram.com", "path": "/"}
                        for c in _il.context._session.cookies if c.value
                    ]
                    context.add_cookies(ig_cookies)
                    print(f"[playwright] No state file — injected {len(ig_cookies)} fallback cookies")
                except Exception as e:
                    print(f"[playwright-cookie-warn] {e}")

            page = context.new_page()
            page.on("response", on_response)  # must be before goto

            try:
                page.goto(
                    f"https://www.instagram.com/{username}/",
                    wait_until="domcontentloaded",
                    timeout=15000,
                )

                # Check for login wall or unavailable page
                content = page.content()
                if "This Account is Private" in content or "Sorry, this page" in content:
                    print(f"[playwright-private] @{username} — private/unavailable")
                    return None, None

                # Give background XHRs time to fire and be intercepted
                page.wait_for_timeout(3000)

                # Tier 2b: page.evaluate — call API directly from inside browser
                # Uses browser's own cookies via credentials:include, bypasses external 429
                if not captured_url:
                    print(f"[playwright-evaluate] @{username} — calling API from browser context")
                    try:
                        result = page.evaluate(f"""
                            async () => {{
                                const r = await fetch(
                                    'https://www.instagram.com/api/v1/users/web_profile_info/?username={username}',
                                    {{
                                        headers: {{
                                            'x-ig-app-id': '936619743392459',
                                            'accept': '*/*',
                                        }},
                                        credentials: 'include'
                                    }}
                                );
                                if (!r.ok) return {{ error: r.status }};
                                const data = await r.json();
                                const user = data?.data?.user || {{}};
                                const versions = user.hd_profile_pic_versions || [];
                                const best = versions.sort((a, b) => b.width - a.width)[0]?.url || null;
                                return {{
                                    hd_info: user.hd_profile_pic_url_info?.url || null,
                                    best_version: best,
                                    hd: user.profile_pic_url_hd || null,
                                    sd: user.profile_pic_url || null
                                }};
                            }}
                        """)
                        print(f"[playwright-evaluate-result] @{username} — {result}")
                        if result and not result.get("error"):
                            captured_url = (
                                result.get("hd_info")
                                or result.get("best_version")
                                or result.get("hd")
                                or result.get("sd")
                            )
                        elif result and result.get("error"):
                            print(f"[playwright-evaluate-fail] @{username} — API returned HTTP {result['error']}")
                    except Exception as e:
                        print(f"[playwright-evaluate-err] @{username} — {e}")

                # All methods exhausted
                if not captured_url:
                    page.screenshot(path=f"debug_{username}.png")
                    print(f"[playwright-fail] @{username} — all methods exhausted, screenshot saved")
                    return None, None

                print(f"[playwright-url] @{username} — {captured_url}")

                # Download image inside same authenticated context
                img_page = context.new_page()
                try:
                    img_resp = img_page.goto(
                        captured_url, wait_until="commit", timeout=10000
                    )
                    if img_resp and img_resp.ok:
                        data = img_resp.body()
                        if check_image_size(data, username):
                            return data, captured_url
                    else:
                        status = img_resp.status if img_resp else "no response"
                        print(f"[playwright-img-fail] @{username} — HTTP {status}")
                except Exception as e:
                    print(f"[playwright-img-error] @{username} — {e}")
                finally:
                    img_page.close()

            except Exception as e:
                print(f"[playwright-fail] @{username} — {e}")
            finally:
                context.close()
                browser.close()

    except Exception as e:
        print(f"[playwright-crash] @{username} — {e}")
        traceback.print_exc()

    return None, None


async def fetch_and_save_pfp(username: str, save_dir: Path):
    # Tier 1: API
    data, pic_url = await fetch_pfp_api_with_retry(username)

    # Tier 2: Playwright
    if not data:
        print(f"[fallback] @{username} — API failed, trying Playwright thread...")
        try:
            loop = asyncio.get_event_loop()
            data, pic_url = await loop.run_in_executor(_executor, _playwright_fetch_sync, username)
            if data:
                print(f"[✅ SUCCESS] @{username} — Fetched via Playwright")
        except Exception as e:
            print(f"[playwright-thread-crash] @{username} — {e}")
            traceback.print_exc()

    if not data:
        print(f"[❌ NO HD] @{username} — All tiers failed")
        return None, None

    save_dir.mkdir(parents=True, exist_ok=True)
    safe_name = username.replace(".", "_").replace("/", "_")
    out_path = save_dir / f"{safe_name}.jpg"
    out_path.write_bytes(data)
    print(f"[✅ SAVED] @{username} — {out_path}")
    return str(out_path), pic_url