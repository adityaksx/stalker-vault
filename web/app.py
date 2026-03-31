import os, sys, json, shutil, uuid
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR     = Path(__file__).parent
ROOT_DIR     = BASE_DIR.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
STORAGE_DIR  = ROOT_DIR / "storage"
IMAGES_DIR   = STORAGE_DIR / "images"
VIDEOS_DIR   = STORAGE_DIR / "videos"
FILES_DIR    = STORAGE_DIR / "files"

sys.path.insert(0, str(ROOT_DIR))

app = FastAPI(title="Vault")

# ── Create dirs + mount static ──
for d in [IMAGES_DIR, VIDEOS_DIR, FILES_DIR, FRONTEND_DIR / "static"]:
    d.mkdir(parents=True, exist_ok=True)

app.mount("/static",           StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")
app.mount("/storage/images",   StaticFiles(directory=str(IMAGES_DIR)),  name="images")
app.mount("/storage/videos",   StaticFiles(directory=str(VIDEOS_DIR)),  name="videos")
app.mount("/storage/files",    StaticFiles(directory=str(FILES_DIR)),    name="files")

@app.on_event("startup")
async def startup():
    from database.db import init_db
    init_db()

# ── Pages ──
@app.get("/", response_class=HTMLResponse)
def index():
    return (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")

@app.get("/person/{pid}", response_class=HTMLResponse)
def person_page(pid: int):
    return (FRONTEND_DIR / "person.html").read_text(encoding="utf-8")

# ── API: People ──
@app.get("/api/people")
def api_list():
    from database.db import get_all_people
    rows = get_all_people()
    return {"people": [
        {"id": r[0], "name": r[1], "added_at": r[2],
         "insta": r[3], "profile_pic": r[4], "tag": r[5]}
        for r in rows
    ]}

@app.post("/api/people")
async def api_create(name: str = Form(...)):
    from database.db import create_person
    pid = create_person(name)
    return {"ok": True, "id": pid}

@app.patch("/api/people/{pid}")
async def api_update_name(pid: int, name: str = Form(...)):
    from database.db import update_person_name
    update_person_name(pid, name)
    return {"ok": True}

@app.delete("/api/people/{pid}")
def api_delete(pid: int):
    from database.db import delete_person
    delete_person(pid)
    return {"ok": True}

# ── API: Person detail (fields + media combined) ──
@app.get("/api/people/{pid}")
def api_get(pid: int):
    from database.db import get_person, get_fields, get_media
    row = get_person(pid)
    if not row: raise HTTPException(404, "Not found")
    fields = get_fields(pid)
    media  = get_media(pid)
    return {
        "id":       row[0],
        "name":     row[1],
        "added_at": row[2],
        "fields": [
            {"id": f[0], "type": f[1], "label": f[2], "value": f[3], "added_at": f[4]}
            for f in fields
        ],
        "media": [
            {"id": m[0], "type": m[1], "filename": m[2], "path": m[3], "caption": m[4], "added_at": m[5]}
            for m in media
        ]
    }

# ── API: Fields ──
@app.post("/api/people/{pid}/fields")
async def api_add_field(
    pid: int,
    field_type: str = Form(...),
    value:      str = Form(...),
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

# ── API: Media upload ──
@app.post("/api/people/{pid}/media")
async def api_add_media(
    pid:        int,
    media_type: str                  = Form(...),
    caption:    Optional[str]        = Form(default=None),
    repo_url:   Optional[str]        = Form(default=None),
    file:       Optional[UploadFile] = File(default=None),
):
    from database.db import add_media

    # GitHub repo URL (no file)
    if media_type == "repo_url" and repo_url:
        mid = add_media(pid, "repo_url", repo_url, caption=caption)
        return {"ok": True, "id": mid}

    if not file or not file.filename:
        raise HTTPException(400, "No file provided")

    ext  = Path(file.filename).suffix.lower()
    name = f"{uuid.uuid4().hex}{ext}"

    if media_type in ("photo", "screenshot", "profile_pic"):
        dest = IMAGES_DIR / name
        url  = f"/storage/images/{name}"
    elif media_type == "video":
        dest = VIDEOS_DIR / name
        url  = f"/storage/videos/{name}"
    else:  # repo_zip, other
        dest = FILES_DIR / name
        url  = f"/storage/files/{name}"

    with dest.open("wb") as f: shutil.copyfileobj(file.file, f)

    mid = add_media(pid, media_type, file.filename, url, caption)
    return {"ok": True, "id": mid, "path": url}

@app.delete("/api/media/{mid}")
def api_delete_media(mid: int):
    from database.db import delete_media
    delete_media(mid)
    return {"ok": True}