import sys, shutil, uuid
from pathlib import Path
from typing import Optional
import re
import httpx
import instaloader
import asyncio
import os
import time
import random
import io as _io

from PIL import Image
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from contextlib import asynccontextmanager

_t1_failures = 0        # consecutive tier1 failures
_T1_GIVE_UP  = 10       # after this many, skip tier1 for rest of import
BASE_DIR     = Path(__file__).parent
ROOT_DIR     = BASE_DIR.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
STORAGE_DIR  = ROOT_DIR / "storage"
MIN_PFP_SIZE = 150  # reject anything smaller than 300x300
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
}

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

    if IG_USER and IG_PASS:
        try:
            if SESSION_FILE.exists():
                # Load saved session — no password needed
                _il.load_session_from_file(IG_USER, str(SESSION_FILE))
                print(f"[✓] Instagram session loaded for @{IG_USER}")
            else:
                # First run — login and save session
                _il.login(IG_USER, IG_PASS)
                _il.save_session_to_file(str(SESSION_FILE))
                print(f"[✓] Instagram logged in + session saved for @{IG_USER}")
        except Exception as ex:
            print(f"[!] Instagram login failed: {ex}")

    yield

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

    global _t1_failures
    _t1_failures = 0

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

def _fetch_pfp_sync(username: str) -> bytes | None:
    global _t1_failures
    time.sleep(random.uniform(1.5, 3.0))

    # ── Tier 1: Instaloader HD ──
    if _t1_failures < _T1_GIVE_UP:
        try:
            profile = instaloader.Profile.from_username(_il.context, username)
            hd_url  = getattr(profile, 'profile_pic_url_hd', None) or profile.profile_pic_url
            r = httpx.get(hd_url, headers=BROWSER_HEADERS, timeout=15, follow_redirects=True)
            if r.status_code == 200 and check_image_size(r.content, username):
                _t1_failures = 0          # reset on success
                return r.content
            else:
                _t1_failures += 1
                print(f"[tier1-fail {_t1_failures}/{_T1_GIVE_UP}] @{username} — low-res or bad response")
        except instaloader.exceptions.ProfileNotExistsException:
            _t1_failures += 1
            print(f"[tier1-fail {_t1_failures}/{_T1_GIVE_UP}] @{username} — ProfileNotFound (likely rate-limited)")
            return None
        except instaloader.exceptions.ConnectionException as ex:
            _t1_failures += 1
            print(f"[tier1-ratelimit {_t1_failures}/{_T1_GIVE_UP}] @{username} — {ex}")
            time.sleep(60)
        except Exception as ex:
            _t1_failures += 1
            print(f"[tier1-fail {_t1_failures}/{_T1_GIVE_UP}] @{username}: {ex}")

        if _t1_failures >= _T1_GIVE_UP:
            print(f"[⚠️  TIER 1 DISABLED] — {_T1_GIVE_UP} consecutive failures, switching to tier 2 only")
    else:
        print(f"[tier1-skip] @{username} — tier1 disabled")

    # ── Tier 2: og:image HTML scrape ──
    try:
        time.sleep(random.uniform(1.0, 2.0))
        headers = {
            **BROWSER_HEADERS,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
            "Upgrade-Insecure-Requests": "1",
        }
        r = httpx.get(
            f"https://www.instagram.com/{username}/",
            headers=headers,
            timeout=15,
            follow_redirects=True,
        )
        if r.status_code == 200:
            import re as _re
            match = _re.search(
                r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\'](https://[^"\']+)["\']',
                r.text,
            ) or _re.search(
                r'<meta[^>]+content=["\'](https://[^"\']+)["\'][^>]+property=["\']og:image["\']',
                r.text,
            )
            if match:
                og_url = match.group(1).replace("&amp;", "&")
                img = httpx.get(og_url, headers=BROWSER_HEADERS, timeout=15, follow_redirects=True)
                if img.status_code == 200 and check_image_size(img.content, username):
                    return img.content
                print(f"[tier2-lowres] @{username} — og:image too small")
            else:
                print(f"[tier2-miss] @{username} — og:image not in HTML (login wall?)")
        else:
            print(f"[tier2-http] @{username} — status {r.status_code}")
    except Exception as ex:
        print(f"[warn] tier2 @{username}: {ex}")

    print(f"[❌ NO HD] @{username} — all tiers failed, skipping")
    return None

async def fetch_and_save_pfp(username: str, csv_pic_url: str, dest_dir: Path, safe_name: str) -> str | None:
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(_executor, _fetch_pfp_sync, username)
    if data:
        filename = f"{username}_{uuid.uuid4().hex[:8]}.jpg"
        (dest_dir / filename).write_bytes(data)
        return f"/storage/{safe_name}/ig_pics/{filename}"
    return None