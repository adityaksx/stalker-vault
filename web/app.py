import sys, shutil, uuid
from pathlib import Path
from typing import Optional
import re
import httpx

from fastapi import FastAPI, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR     = Path(__file__).parent
ROOT_DIR     = BASE_DIR.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
STORAGE_DIR  = ROOT_DIR / "storage"

sys.path.insert(0, str(ROOT_DIR))

app = FastAPI(title="Vault")

STORAGE_DIR.mkdir(parents=True, exist_ok=True)
(FRONTEND_DIR / "static").mkdir(parents=True, exist_ok=True)

app.mount("/static",   StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")
app.mount("/storage",  StaticFiles(directory=str(STORAGE_DIR)),              name="storage")

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    from database.db import init_db
    init_db()
    yield

app = FastAPI(title="Vault", lifespan=lifespan)

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

@app.get("/api/ig-snapshots/{sid}/entries")
def api_ig_entries(sid: int):
    from database.db import get_ig_entries
    rows = get_ig_entries(sid)
    return {"entries": [
        {"id":r[0],"username":r[1],"full_name":r[2],"profile_pic_url":r[3],"local_pic_path":r[4]}
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
    from database.db import create_ig_snapshot, add_ig_entry, get_person
    import csv, io

    person_row  = get_person(pid)
    person_name = person_row[1] if person_row else f"person_{pid}"
    safe_name   = safe_folder_name(person_name)

    # CSV columns: followed_by_viewer;full_name;id;is_verified;profile_pic_url;requested_by_viewer;username
    reader  = csv.DictReader(io.StringIO(csv_data), delimiter=';')
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

    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        for (uname, fname, pic_url) in entries:
            local_path = None
            if pic_url:
                try:
                    filename   = f"{uname}_{uuid.uuid4().hex[:8]}.jpg"
                    dest       = pic_dir / filename
                    r          = await client.get(pic_url)
                    if r.status_code == 200:
                        dest.write_bytes(r.content)
                        local_path = f"/storage/{safe_name}/ig_pics/{filename}"
                except Exception:
                    pass
            add_ig_entry(sid, uname, fname, pic_url, local_path)

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

@app.delete("/api/ig-snapshots/{sid}")
def api_ig_delete_snapshot(sid: int):
    from database.db import delete_ig_snapshot
    delete_ig_snapshot(sid)
    return {"ok": True}
