import sys
import io
import os
import re
import json
import uuid
import shutil
import random
import zipfile
import asyncio
import traceback
import re as _re
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

import httpx
import instaloader
from PIL import Image
from dotenv import load_dotenv
from fastapi import FastAPI, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from playwright.sync_api import sync_playwright

# ── Paths & config ─────────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent
ROOT_DIR     = BASE_DIR.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
STORAGE_DIR  = ROOT_DIR / "storage"
UPLOADS_DIR  = ROOT_DIR / "uploads"
SESSION_FILE = BASE_DIR / ".ig_session"
STATE_FILE   = BASE_DIR / "ig_browser_state.json"
MIN_PFP_SIZE = 250

sys.path.insert(0, str(ROOT_DIR))
load_dotenv()

IG_USER = os.getenv("IG_USERNAME", "")
IG_PASS = os.getenv("IG_PASSWORD", "")

_executor = ThreadPoolExecutor(max_workers=2)
_il = instaloader.Instaloader(download_pictures=False, quiet=True, request_timeout=10)

TYPE_FOLDER = {
    "profile_pic": "images",
    "photo":       "images",
    "screenshot":  "images",
    "video":       "videos",
    "audio":       "audio",
    "repo_zip":    "files",
    "other":       "files",
}

# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    from database.db import init_db
    init_db()
    if IG_USER and IG_PASS:
        try:
            if SESSION_FILE.exists():
                _il.load_session_from_file(IG_USER, str(SESSION_FILE))
                print(f"[OK] Instagram session loaded for @{IG_USER}")
            else:
                _il.login(IG_USER, IG_PASS)
                _il.save_session_to_file(str(SESSION_FILE))
                print(f"[OK] Instagram logged in + session saved for @{IG_USER}")
        except Exception as ex:
            print(f"[!] Instagram login failed: {ex}")
    yield

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(title="Vault", lifespan=lifespan)

STORAGE_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
(FRONTEND_DIR / "static").mkdir(parents=True, exist_ok=True)

app.mount("/static",  StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")
app.mount("/storage", StaticFiles(directory=str(STORAGE_DIR)),             name="storage")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)),             name="uploads")

# ── Helpers ────────────────────────────────────────────────────────────────────
def safe_folder_name(name: str) -> str:
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name)
    s = re.sub(r'\s+', '_', s.strip())
    return s or "unknown"

def get_person_dir(pid: int, person_name: str, media_type: str) -> tuple[Path, str, str]:
    folder    = TYPE_FOLDER.get(media_type, "files")
    safe_name = safe_folder_name(person_name)
    d = STORAGE_DIR / safe_name / folder
    d.mkdir(parents=True, exist_ok=True)
    return d, folder, safe_name

# ── Pages ──────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def index():
    return (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")

@app.get("/person/{pid}", response_class=HTMLResponse)
def person_page(pid: int):
    return (FRONTEND_DIR / "person.html").read_text(encoding="utf-8")

# ── People ─────────────────────────────────────────────────────────────────────
@app.get("/api/people")
def api_list():
    from database.db import get_all_people
    rows = get_all_people()
    return {"people": [
        {"id": r[0], "name": r[1], "added_at": r[2], "insta": r[3],
         "profile_pic": r[4], "tag": r[5], "category": r[6]}
        for r in rows
    ]}

@app.post("/api/people")
async def api_create(name: str = Form(...), category: str = Form(default="random")):
    from database.db import create_person
    pid = create_person(name, category)
    return {"ok": True, "id": pid}

@app.get("/api/people/{pid}")
def api_get(pid: int):
    from database.db import get_person, get_fields, get_media
    row = get_person(pid)
    if not row:
        raise HTTPException(404, "Not found")
    fields = get_fields(pid)
    media  = get_media(pid)
    return {
        "id": row[0], "name": row[1], "added_at": row[2], "category": row[3],
        "fields": [{"id": f[0], "type": f[1], "label": f[2], "value": f[3], "added_at": f[4]} for f in fields],
        "media":  [{"id": m[0], "type": m[1], "filename": m[2], "path": m[3],
                    "caption": m[4], "added_at": m[5], "local_path": m[6]} for m in media],
    }

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

@app.patch("/api/people/{pid}/category")
async def api_update_category(pid: int, category: str = Form(...)):
    from database.db import update_person_category
    update_person_category(pid, category)
    return {"ok": True}

@app.delete("/api/people/{pid}")
def api_delete(pid: int):
    from database.db import delete_person, get_person
    row = get_person(pid)
    if row:
        folder = STORAGE_DIR / safe_folder_name(row[1])
        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)
    delete_person(pid)
    return {"ok": True}

# ── Fields ─────────────────────────────────────────────────────────────────────
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

# ── Media ──────────────────────────────────────────────────────────────────────
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
        mid = add_media(pid, "repo_url", repo_url, filename=None, caption=caption, local_path=None)
        return {"ok": True, "id": mid}

    if not file or not file.filename:
        raise HTTPException(400, "No file provided")

    person_row  = get_person(pid)
    person_name = person_row[1] if person_row else f"person_{pid}"
    original    = file.filename
    ext         = Path(original).suffix.lower()
    uuid_name   = f"{uuid.uuid4().hex}{ext}"

    dest_dir, folder_type, safe_name = get_person_dir(pid, person_name, media_type)
    dest       = dest_dir / uuid_name
    url        = f"/storage/{safe_name}/{folder_type}/{uuid_name}"
    local_path = str(dest.resolve()).replace("\\", "/")

    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    mid = add_media(pid, media_type, url, filename=original, caption=caption, local_path=local_path)
    return {"ok": True, "id": mid, "path": url}

@app.delete("/api/media/{mid}")
def api_delete_media(mid: int):
    from database.db import get_media_by_id, delete_media
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
    from database.db import rename_media, get_media_by_id, update_media_path
    row = get_media_by_id(mid)
    if row and row["local_path"]:
        old_path = Path(row["local_path"])
        new_path = old_path.parent / filename
        if old_path.exists() and not new_path.exists():
            old_path.rename(new_path)
            new_url = "/".join(row["path"].split("/")[:-1]) + "/" + filename
            update_media_path(mid, new_url, str(new_path).replace("\\", "/"))
    rename_media(mid, filename)
    return {"ok": True}

# ── Instagram Snapshots ────────────────────────────────────────────────────────
@app.get("/api/people/{pid}/ig-snapshots")
def api_ig_snapshots(pid: int):
    from database.db import get_ig_snapshots
    rows = get_ig_snapshots(pid)
    return {"snapshots": [
        {"id": r[0], "ig_username": r[1], "list_type": r[2],
         "label": r[3], "imported_at": r[4], "count": r[5]}
        for r in rows
    ]}

@app.post("/api/people/{pid}/ig-snapshots")
async def api_ig_import(
    pid:         int,
    ig_username: str           = Form(...),
    list_type:   str           = Form(...),
    label:       Optional[str] = Form(default=None),
    csv_data:    str           = Form(...),
):
    import csv
    from database.db import create_ig_snapshot, add_ig_entry, get_person

    person_row  = get_person(pid)
    person_name = person_row[1] if person_row else f"person_{pid}"
    safe_name   = safe_folder_name(person_name)

    sample = csv_data[:500]
    delim  = ";" if ";" in sample and "," not in sample else ","
    reader = csv.DictReader(io.StringIO(csv_data), delimiter=delim)

    entries = []
    for row in reader:
        uname = (row.get("username") or "").strip().strip('"')
        fname = (row.get("full_name") or "").strip().strip('"')
        pic   = (row.get("profile_pic_url") or "").strip().strip('"')
        if uname:
            entries.append((uname, fname, pic))

    if not entries:
        raise HTTPException(400, "No valid entries in CSV")

    sid     = create_ig_snapshot(pid, ig_username, list_type, label)
    pic_dir = STORAGE_DIR / safe_name / "ig_pics"
    pic_dir.mkdir(parents=True, exist_ok=True)

    hd_count         = 0
    rejected_count   = 0
    consecutive_429s = 0

    for i, (uname, fname, csv_pic_url) in enumerate(entries):
        if consecutive_429s >= 3:
            print("[RATE LIMITED] 3 consecutive failures – pausing 5 min")
            await asyncio.sleep(300)
            consecutive_429s = 0

        wait = random.uniform(2, 4) if i < 10 else random.uniform(6, 12)
        print(f"[rate-limit] waiting {wait:.1f}s before @{uname} ({i+1}/{len(entries)})")
        await asyncio.sleep(wait)

        local_path, fetched_url = await fetch_and_save_pfp(uname, pic_dir)

        if local_path:
            hd_count        += 1
            consecutive_429s = 0
            save_url         = fetched_url
        else:
            rejected_count   += 1
            consecutive_429s += 1
            save_url          = csv_pic_url

        add_ig_entry(sid, uname, fname, save_url, local_path)

    print(f"[import] Done – HD: {hd_count}  rejected: {rejected_count}  total: {len(entries)}")
    return {"ok": True, "snapshot_id": sid, "count": len(entries)}

@app.get("/api/ig-snapshots/diff")
def api_ig_diff(old_sid: int, new_sid: int):
    from database.db import get_ig_entries
    old_map = {e[1]: e for e in get_ig_entries(old_sid)}
    new_map = {e[1]: e for e in get_ig_entries(new_sid)}
    old_set, new_set = set(old_map), set(new_map)

    def fmt(e):
        return {"username": e[1], "full_name": e[2],
                "profile_pic_url": e[3], "local_pic_path": e[4]}

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
        {"id": r[0], "username": r[1], "full_name": r[2],
         "profile_pic_url": r[3], "local_pic_path": r[4]}
        for r in rows
    ]}

@app.delete("/api/ig-snapshots/{sid}")
def api_ig_delete_snapshot(sid: int):
    from database.db import delete_ig_snapshot
    delete_ig_snapshot(sid)
    return {"ok": True}

# ── Highlights ─────────────────────────────────────────────────────────────────
@app.post("/api/people/{pid}/highlights/import-zip")
async def import_highlight_zip(pid: int, file: UploadFile = File(...)):
    from database.db import get_person, create_highlight, add_highlight_story
    if not get_person(pid):
        raise HTTPException(404, "Person not found")

    content  = await file.read()
    zip_name = file.filename or "highlight.zip"
    stem     = zip_name.replace(".zip", "").replace(".ZIP", "")
    m        = _re.match(r'^(.+?)_highlights?', stem, _re.IGNORECASE)
    hl_name  = m.group(1).replace("_", " ").strip().title() if m else stem
    hl_id    = create_highlight(pid, hl_name, zip_name)

    upload_dir = UPLOADS_DIR / str(pid) / "highlights" / str(hl_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        for entry in sorted(zf.namelist()):
            base = Path(entry).name
            if not base or base.startswith("."):
                continue
            ext      = Path(base).suffix.lower()
            is_video = ext in (".mp4", ".mov", ".webm", ".avi")
            if not (is_video or ext in (".jpg", ".jpeg", ".png", ".webp", ".heic")):
                continue
            dm       = _re.search(r'_(\d{2})_(\d{2})_(\d{4})_', base)
            date_str = f"{dm.group(3)}-{dm.group(2)}-{dm.group(1)}" if dm else None
            dest     = upload_dir / base
            with zf.open(entry) as sf, open(dest, "wb") as df:
                df.write(sf.read())
            add_highlight_story(
                hl_id, base,
                f"/uploads/{pid}/highlights/{hl_id}/{base}",
                is_video, date_str,
            )
            count += 1

    return {"ok": True, "name": hl_name, "story_count": count, "id": hl_id}

@app.get("/api/people/{pid}/highlights")
def get_highlights(pid: int):
    from database.db import get_highlights as db_get_highlights
    return db_get_highlights(pid)

@app.get("/api/highlights/{hl_id}/stories")
def get_highlight_stories(hl_id: int):
    from database.db import get_highlight_stories as db_get_highlight_stories
    return db_get_highlight_stories(hl_id)

# ── Feed Posts ─────────────────────────────────────────────────────────────────
@app.post("/api/people/{pid}/feed-posts/import-zip")
async def import_feed_zip(pid: int, file: UploadFile = File(...)):
    from database.db import get_person, create_feed_post, add_feed_post_item
    if not get_person(pid):
        raise HTTPException(404, "Person not found")

    content   = await file.read()
    zip_name  = file.filename or "feed.zip"
    upload_dir = UPLOADS_DIR / str(pid) / "feed"
    upload_dir.mkdir(parents=True, exist_ok=True)

    def parse_date(name: str) -> str:
        dm = _re.search(r'_(\d{2})_(\d{2})_(\d{4})_', name)
        return f"{dm.group(3)}-{dm.group(2)}-{dm.group(1)}" if dm else "unknown"

    groups: dict[str, list] = {}
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        for entry in sorted(zf.namelist()):
            base = Path(entry).name
            if not base or base.startswith("."):
                continue
            ext      = Path(base).suffix.lower()
            is_video = ext in (".mp4", ".mov", ".webm", ".avi")
            if not (is_video or ext in (".jpg", ".jpeg", ".png", ".webp", ".heic")):
                continue
            groups.setdefault(parse_date(base), []).append((entry, base, is_video))

    post_count = 0
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        for dk, items in sorted(groups.items()):
            post_id = create_feed_post(pid, dk, zip_name)
            for entry, base, is_video in items:
                dest = upload_dir / base
                with zf.open(entry) as sf, open(dest, "wb") as df:
                    df.write(sf.read())
                add_feed_post_item(post_id, base, f"/uploads/{pid}/feed/{base}", is_video, dk)
            post_count += 1

    return {"ok": True, "post_count": post_count}

@app.get("/api/people/{pid}/feed-posts")
def get_feed_posts(pid: int):
    from database.db import get_feed_posts as db_get_feed_posts
    return db_get_feed_posts(pid)

@app.get("/api/feed-posts/{post_id}/items")
def get_feed_post_items(post_id: int):
    from database.db import get_feed_post_items as db_get_feed_post_items
    return db_get_feed_post_items(post_id)

# ── Instagram PFP fetching ─────────────────────────────────────────────────────
def _get_browser_cookies() -> dict:
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

def check_image_size(data: bytes, username: str) -> bool:
    try:
        img  = Image.open(io.BytesIO(data))
        w, h = img.size
        print(f"[{'HD' if w >= 300 else 'LOW-RES'}] @{username} – {w}x{h}")
        return w >= 100
    except Exception as e:
        print(f"[size-check-error] @{username} – {e}")
        return len(data) > 3000

async def fetch_pfp_api(username: str):
    ig_cookies = _get_browser_cookies()
    if not ig_cookies:
        try:
            ig_cookies = {c.name: c.value for c in _il.context._session.cookies if c.value}
        except Exception:
            pass

    headers = {
        "accept":          "*/*",
        "accept-language": "en-US,en;q=0.9",
        "x-ig-app-id":     "936619743392459",
        "User-Agent":      ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/122.0.0.0 Safari/537.36"),
    }

    async with httpx.AsyncClient(cookies=ig_cookies) as client:
        try:
            r = await client.get(
                f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}",
                headers=headers, timeout=10.0,
            )
            print(f"[api-status] @{username} – HTTP {r.status_code}")
            if r.status_code != 200:
                return None, None

            user = r.json().get("data", {}).get("user", {})
            if not user:
                return None, None

            versions = user.get("hd_profile_pic_versions") or []
            best_url = max(versions, key=lambda x: x.get("width", 0)).get("url") if versions else None
            hd_url   = (
                user.get("hd_profile_pic_url_info", {}).get("url")
                or best_url
                or user.get("profile_pic_url_hd")
                or user.get("profile_pic_url")
            )
            if not hd_url:
                return None, None

            img = await client.get(hd_url, timeout=15.0, follow_redirects=True)
            if img.status_code == 200 and check_image_size(img.content, username):
                return img.content, hd_url

        except Exception as e:
            print(f"[api-error] @{username} – {e}")

    return None, None

async def fetch_pfp_api_with_retry(username: str):
    for attempt in range(2):
        data, url = await fetch_pfp_api(username)
        if data:
            return data, url
        if attempt == 0:
            wait = random.uniform(8, 15)
            print(f"[api-retry] @{username} – retrying in {wait:.1f}s")
            await asyncio.sleep(wait)
    return None, None

def _playwright_fetch_sync(username: str):
    print(f"[playwright] STATE_FILE={STATE_FILE}, exists={STATE_FILE.exists()}")
    captured_url = None

    def on_response(response):
        nonlocal captured_url
        if "web_profile_info" in response.url and captured_url is None:
            try:
                data     = response.json()
                user     = data.get("data", {}).get("user", {})
                versions = user.get("hd_profile_pic_versions") or []
                best_url = (
                    max(versions, key=lambda x: x.get("width", 0)).get("url")
                    if versions else None
                )
                captured_url = (
                    user.get("hd_profile_pic_url_info", {}).get("url")
                    or best_url
                    or user.get("profile_pic_url_hd")
                    or user.get("profile_pic_url")
                )
                if captured_url:
                    print(f"[playwright-intercept] @{username} – captured URL")
            except Exception as e:
                print(f"[playwright-intercept-err] @{username} – {e}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36")

            if STATE_FILE.exists():
                context = browser.new_context(storage_state=str(STATE_FILE), user_agent=ua)
            else:
                context = browser.new_context(user_agent=ua)
                try:
                    ig_cookies = [
                        {"name": c.name, "value": c.value, "domain": ".instagram.com", "path": "/"}
                        for c in _il.context._session.cookies if c.value
                    ]
                    context.add_cookies(ig_cookies)
                except Exception as e:
                    print(f"[playwright-cookie-warn] {e}")

            page = context.new_page()
            page.on("response", on_response)

            try:
                page.goto(
                    f"https://www.instagram.com/{username}/",
                    wait_until="domcontentloaded", timeout=15000,
                )
                content = page.content()
                if "This Account is Private" in content or "Sorry, this page" in content:
                    print(f"[playwright-private] @{username} – private/unavailable")
                    return None, None

                page.wait_for_timeout(3000)

                if not captured_url:
                    try:
                        result = page.evaluate(f"""
                            async () => {{
                                const r = await fetch(
                                    'https://www.instagram.com/api/v1/users/web_profile_info/?username={username}',
                                    {{ headers: {{ 'x-ig-app-id': '936619743392459', 'accept': '*/*' }},
                                       credentials: 'include' }}
                                );
                                if (!r.ok) return {{ error: r.status }};
                                const data = await r.json();
                                const user = data?.data?.user || {{}};
                                const versions = user.hd_profile_pic_versions || [];
                                const best = versions.sort((a, b) => b.width - a.width)[0]?.url || null;
                                return {{
                                    hd_info:      user.hd_profile_pic_url_info?.url || null,
                                    best_version: best,
                                    hd:           user.profile_pic_url_hd || null,
                                    sd:           user.profile_pic_url || null,
                                }};
                            }}
                        """)
                        if result and not result.get("error"):
                            captured_url = (
                                result.get("hd_info")
                                or result.get("best_version")
                                or result.get("hd")
                                or result.get("sd")
                            )
                    except Exception as e:
                        print(f"[playwright-evaluate-err] @{username} – {e}")

                if not captured_url:
                    return None, None

                img_page = context.new_page()
                try:
                    img_resp = img_page.goto(captured_url, wait_until="commit", timeout=10000)
                    if img_resp and img_resp.ok:
                        data = img_resp.body()
                        if check_image_size(data, username):
                            return data, captured_url
                except Exception as e:
                    print(f"[playwright-img-error] @{username} – {e}")
                finally:
                    img_page.close()

            except Exception as e:
                print(f"[playwright-fail] @{username} – {e}")
            finally:
                context.close()
                browser.close()

    except Exception as e:
        print(f"[playwright-crash] @{username} – {e}")
        traceback.print_exc()

    return None, None

async def fetch_and_save_pfp(username: str, save_dir: Path):
    data, pic_url = await fetch_pfp_api_with_retry(username)

    if not data:
        print(f"[fallback] @{username} – API failed, trying Playwright…")
        try:
            loop = asyncio.get_event_loop()
            data, pic_url = await loop.run_in_executor(_executor, _playwright_fetch_sync, username)
            if data:
                print(f"[SUCCESS] @{username} – fetched via Playwright")
        except Exception as e:
            print(f"[playwright-thread-crash] @{username} – {e}")
            traceback.print_exc()

    if not data:
        print(f"[NO HD] @{username} – all tiers failed")
        return None, None

    save_dir.mkdir(parents=True, exist_ok=True)
    safe_name = username.replace(".", "_").replace("/", "_")
    out_path  = save_dir / f"{safe_name}.jpg"
    out_path.write_bytes(data)
    print(f"[SAVED] @{username} – {out_path}")
    return str(out_path), pic_url
