import os, sys, json, shutil, uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR     = Path(__file__).parent
ROOT_DIR     = BASE_DIR.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
STORAGE_DIR  = ROOT_DIR / "storage"
IMAGES_DIR   = STORAGE_DIR / "images"
VIDEOS_DIR   = STORAGE_DIR / "videos"
AUDIO_DIR    = STORAGE_DIR / "audio"
FILES_DIR    = STORAGE_DIR / "files"

sys.path.insert(0, str(ROOT_DIR))

app = FastAPI(title="Vault")

for d in [IMAGES_DIR, VIDEOS_DIR, AUDIO_DIR, FILES_DIR, FRONTEND_DIR / "static"]:
    d.mkdir(parents=True, exist_ok=True)

app.mount("/static",         StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")
app.mount("/storage/images", StaticFiles(directory=str(IMAGES_DIR)),  name="images")
app.mount("/storage/videos", StaticFiles(directory=str(VIDEOS_DIR)),  name="videos")
app.mount("/storage/audio",  StaticFiles(directory=str(AUDIO_DIR)),   name="audio")
app.mount("/storage/files",  StaticFiles(directory=str(FILES_DIR)),   name="files")

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
    from database.db import update_person_name
    update_person_name(pid, name)
    return {"ok": True}

@app.delete("/api/people/{pid}")
def api_delete(pid: int):
    from database.db import delete_person
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
        "media":  [{"id":m[0],"type":m[1],"filename":m[2],"path":m[3],"caption":m[4],"added_at":m[5]} for m in media]
    }

# ── Fields ──
@app.post("/api/people/{pid}/fields")
async def api_add_field(
    pid:        int,
    field_type: str          = Form(...),
    value:      str          = Form(...),
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
    media_type: str               = Form(...),
    caption:    Optional[str]     = Form(default=None),
    repo_url:   Optional[str]     = Form(default=None),
    file:       Optional[UploadFile] = File(default=None),
):
    from database.db import add_media

    if media_type == "repo_url":
        if not repo_url:
            raise HTTPException(400, "repo_url required")
        mid = add_media(pid, "repo_url", repo_url, filename=None, caption=caption)
        return {"ok": True, "id": mid}

    if not file or not file.filename:
        raise HTTPException(400, "No file provided")

    ext       = Path(file.filename).suffix.lower()
    safe_name = f"{uuid.uuid4().hex}{ext}"

    if media_type in ("photo", "screenshot", "profile_pic"):
        dest = IMAGES_DIR / safe_name
        url  = f"/storage/images/{safe_name}"
    elif media_type == "video":
        dest = VIDEOS_DIR / safe_name
        url  = f"/storage/videos/{safe_name}"
    elif media_type == "audio":
        dest = AUDIO_DIR / safe_name
        url  = f"/storage/audio/{safe_name}"
    else:
        dest = FILES_DIR / safe_name
        url  = f"/storage/files/{safe_name}"

    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    # path = uuid url, filename = original display name
    mid = add_media(pid, media_type, url, file.filename, caption)
    return {"ok": True, "id": mid, "path": url}

@app.delete("/api/media/{mid}")
def api_delete_media(mid: int):
    from database.db import delete_media
    delete_media(mid)
    return {"ok": True}

# ── Rename media display name ──
@app.patch("/api/media/{mid}/rename")
async def api_rename_media(mid: int, filename: str = Form(...)):
    from database.db import rename_media
    rename_media(mid, filename)
    return {"ok": True}