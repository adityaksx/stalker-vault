import sys, shutil, uuid
from pathlib import Path
from typing import Optional
import re
import httpx
import instaloader
import asyncio
import os
import io as _io
import logging

from PIL import Image
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from playwright.sync_api import sync_playwright

BASE_DIR     = Path(__file__).parent
ROOT_DIR     = BASE_DIR.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
STORAGE_DIR  = ROOT_DIR / "storage"
MIN_PFP_SIZE = 150  # reject anything smaller than 300x300

load_dotenv()   # loads .env file automatically

IG_USER = os.getenv("IG_USERNAME", "")
IG_PASS = os.getenv("IG_PASSWORD", "")

_il = instaloader.Instaloader(
    download_pictures=False,   # we handle saving ourselves
    quiet=True,
    request_timeout=10,
)
_executor = ThreadPoolExecutor(max_workers=4)


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

    for i, (uname, fname, pic_url) in enumerate(entries):
        if i > 0 and i % 20 == 0:
            print(f"[pause] {i}/{len(entries)} done — sleeping 10s")
            await asyncio.sleep(10)

        local_path = await fetch_and_save_pfp(uname, pic_url, pic_dir, safe_name)

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


def check_image_size(data: bytes, username: str) -> bool:
    try:
        img = Image.open(_io.BytesIO(data))
        w, h = img.size
        if w < MIN_PFP_SIZE or h < MIN_PFP_SIZE:
            print(f"[❌ LOW-RES] @{username} — {w}x{h} (rejected, min {MIN_PFP_SIZE}px)")
            return False
        print(f"[✅ HD] @{username} — {w}x{h}")
        return True
    except Exception:
        return False


# New Tier 1: Fast Hidden Web API (No login required)
async def fetch_pfp_api(username: str) -> bytes | None:
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "x-ig-app-id": "936619743392459",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    # Extract cookies from Instaloader session
    ig_cookies = {}
    try:
        ig_cookies = {c.name: c.value for c in _il.context._session.cookies if c.value}
    except Exception:
        pass

    async with httpx.AsyncClient(cookies=ig_cookies) as client:
        try:
            response = await client.get(url, headers=headers, timeout=10.0)
            print(f"[api-status] @{username} — HTTP {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                user = data.get("data", {}).get("user", {})
                if not user:
                    print(f"[api-empty] @{username} — no user in response")
                    return None
                hd_url = (
                    user.get("hd_profile_pic_url_info", {}).get("url")
                    or user.get("profile_pic_url_hd")
                    or user.get("profile_pic_url")
                )
                if hd_url:
                    img_response = await client.get(hd_url, timeout=15.0, follow_redirects=True)
                    if img_response.status_code == 200 and check_image_size(img_response.content, username):
                        return img_response.content
            else:
                print(f"[api-fail] @{username} — Status: {response.status_code}")
        except Exception as e:
            print(f"[api-error] @{username} — {str(e)}")
    return None

# Runs in a ThreadPoolExecutor — completely isolated from asyncio loop
def _playwright_fetch_sync(username: str) -> bytes | None:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            try:
                ig_cookies = [
                    {"name": c.name, "value": c.value, "domain": ".instagram.com", "path": "/"}
                    for c in _il.context._session.cookies if c.value
                ]
                context.add_cookies(ig_cookies)
                print(f"[playwright] Injected {len(ig_cookies)} session cookies")
            except Exception as e:
                print(f"[playwright-cookie-warn] Could not inject cookies: {e}")

            page = context.new_page()
            try:
                page.goto(f"https://www.instagram.com/{username}/", wait_until="networkidle", timeout=20000)

                img_element = None
                for sel in ['header img', 'header section img', 'img[alt$="profile picture"]',
                            'img[data-testid="user-avatar"]']:
                    try:
                        img_element = page.wait_for_selector(sel, timeout=3000)
                        if img_element:
                            print(f"[playwright-selector] @{username} — matched '{sel}'")
                            break
                    except Exception:
                        continue

                if not img_element:
                    page.screenshot(path=f"debug_{username}.png")
                    print(f"[playwright-debug] @{username} — screenshot saved as debug_{username}.png — check it!")
                    raise Exception("No profile picture selector matched")

                hd_url = img_element.get_attribute('src')
                print(f"[playwright-url] @{username} — {hd_url[:80] if hd_url else 'None'}")
                if hd_url and "150x150" not in hd_url:
                    img_response = page.request.get(hd_url)
                    if img_response.ok:
                        data = img_response.body()
                        if check_image_size(data, username):
                            return data
                    else:
                        print(f"[playwright-img-fail] @{username} — status {img_response.status}")

            except Exception as e:
                print(f"[playwright-fail] @{username} — {str(e)}")
            except Exception as e:
                print(f"[playwright-fail] @{username} — {str(e)}")
            finally:
                context.close()
                browser.close()
    except Exception as e:
        print(f"[playwright-outer-fail] @{username} — {str(e)}")
    return None

# The new fetch and save orchestrator
async def fetch_and_save_pfp(username: str, csv_pic_url: str, dest_dir: Path, safe_name: str) -> str | None:
    # Tier 1: Fast Hidden Web API
    data = await fetch_pfp_api(username)

    if data:
        print(f"[✅ SUCCESS] @{username} — Fetched via API")
    else:
        # Tier 2: Playwright in a thread (avoids Windows asyncio conflict)
        print(f"[fallback] @{username} — API failed, trying Playwright thread...")
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(_executor, _playwright_fetch_sync, username)
        if data:
            print(f"[✅ SUCCESS] @{username} — Fetched via Playwright")

    if data:
        filename = f"{username}_{uuid.uuid4().hex[:8]}.jpg"
        (dest_dir / filename).write_bytes(data)
        return f"/storage/{safe_name}/ig_pics/{filename}"

    print(f"[❌ NO HD] @{username} — All tiers failed")
    return None