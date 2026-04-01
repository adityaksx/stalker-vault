import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).parent / "vault.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")   # ← add this
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS people (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        name     TEXT NOT NULL,
        added_at TEXT DEFAULT (datetime('now','localtime'))
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS fields (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        person_id  INTEGER NOT NULL,
        field_type TEXT NOT NULL,
        label      TEXT,
        value      TEXT NOT NULL,
        added_at   TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE CASCADE
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS media (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        person_id   INTEGER NOT NULL,
        media_type  TEXT NOT NULL,
        path        TEXT,
        filename    TEXT,
        caption     TEXT,
        added_at    TEXT DEFAULT (datetime('now','localtime')),
        local_path  TEXT,
        FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE CASCADE
    )""")
    conn.commit()
    conn.close()
    init_ig_tables()

# ── People ──
def create_person(name: str) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO people (name) VALUES (?)", (name,))
    pid = c.lastrowid
    conn.commit(); conn.close()
    return pid

def get_all_people():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT p.id, p.name, p.added_at,
               (SELECT value FROM fields WHERE person_id=p.id AND field_type='instagram' LIMIT 1),
               (SELECT path  FROM media  WHERE person_id=p.id AND media_type='profile_pic' LIMIT 1),
               (SELECT value FROM fields WHERE person_id=p.id AND field_type='tag' LIMIT 1)
        FROM people p ORDER BY p.id DESC
    """)
    rows = c.fetchall(); conn.close()
    return rows

def get_person(pid: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, added_at FROM people WHERE id=?", (pid,))
    row = c.fetchone(); conn.close()
    return row

def delete_person(pid: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM people WHERE id=?", (pid,))
    conn.commit(); conn.close()

def update_person_name(pid: int, name: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE people SET name=? WHERE id=?", (name, pid))
    conn.commit(); conn.close()

# ── Fields ──
def add_field(person_id: int, field_type: str, value: str, label: str = None) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO fields (person_id, field_type, label, value) VALUES (?,?,?,?)",
        (person_id, field_type, label, value)
    )
    fid = c.lastrowid
    conn.commit(); conn.close()
    return fid

def get_fields(person_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id, field_type, label, value, added_at FROM fields WHERE person_id=? ORDER BY added_at ASC",
        (person_id,)
    )
    rows = c.fetchall(); conn.close()
    return rows

def delete_field(field_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM fields WHERE id=?", (field_id,))
    conn.commit(); conn.close()

def update_field(field_id: int, value: str, label: str = None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE fields SET value=?, label=? WHERE id=?", (value, label, field_id))
    conn.commit(); conn.close()

# ── Media ──
def add_media(person_id: int, media_type: str, path: str,
              filename: str = None, caption: str = None, local_path: str = None) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO media (person_id, media_type, path, filename, caption, local_path) VALUES (?,?,?,?,?,?)",
        (person_id, media_type, path, filename, caption, local_path)
    )
    mid = c.lastrowid
    conn.commit(); conn.close()
    return mid

def get_media(person_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """SELECT id, media_type, filename, path, caption, added_at, local_path
           FROM media WHERE person_id=? ORDER BY added_at DESC""",
        (person_id,)
    )
    rows = c.fetchall(); conn.close()
    return rows

def delete_media(media_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM media WHERE id=?", (media_id,))
    conn.commit(); conn.close()

def rename_media(media_id: int, filename: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE media SET filename=? WHERE id=?", (filename, media_id))
    conn.commit(); conn.close()

# ── Instagram Snapshots ──

def init_ig_tables():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS ig_snapshots (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        person_id   INTEGER NOT NULL,
        ig_username TEXT NOT NULL,
        list_type   TEXT NOT NULL,
        label       TEXT,
        imported_at TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE CASCADE
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS ig_entries (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id      INTEGER NOT NULL,
        username         TEXT NOT NULL,
        full_name        TEXT,
        profile_pic_url  TEXT,
        local_pic_path   TEXT,
        FOREIGN KEY (snapshot_id) REFERENCES ig_snapshots(id) ON DELETE CASCADE
    )""")
    conn.commit()
    conn.close()

def create_ig_snapshot(person_id, ig_username, list_type, label=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO ig_snapshots (person_id,ig_username,list_type,label) VALUES (?,?,?,?)",
              (person_id, ig_username, list_type, label))
    sid = c.lastrowid; conn.commit(); conn.close(); return sid

def add_ig_entry(snapshot_id, username, full_name, profile_pic_url, local_pic_path=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO ig_entries (snapshot_id,username,full_name,profile_pic_url,local_pic_path) VALUES (?,?,?,?,?)",
              (snapshot_id, username, full_name, profile_pic_url, local_pic_path))
    eid = c.lastrowid; conn.commit(); conn.close(); return eid

def get_ig_snapshots(person_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""SELECT s.id,s.ig_username,s.list_type,s.label,s.imported_at,COUNT(e.id)
                 FROM ig_snapshots s LEFT JOIN ig_entries e ON e.snapshot_id=s.id
                 WHERE s.person_id=? GROUP BY s.id ORDER BY s.imported_at DESC""", (person_id,))
    rows = c.fetchall(); conn.close(); return rows

def get_ig_entries(snapshot_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id,username,full_name,profile_pic_url,local_pic_path FROM ig_entries WHERE snapshot_id=? ORDER BY username ASC", (snapshot_id,))
    rows = c.fetchall(); conn.close(); return rows

def delete_ig_snapshot(snapshot_id: int):
    conn = get_connection()
    c = conn.cursor()
    # Fetch local pic paths before cascade delete
    c.execute("SELECT local_pic_path FROM ig_entries WHERE snapshot_id=?", (snapshot_id,))
    pic_paths = [r[0] for r in c.fetchall() if r[0]]
    c.execute("DELETE FROM ig_snapshots WHERE id=?", (snapshot_id,))
    conn.commit()
    conn.close()
    # Clean files from disk
    for p in pic_paths:
        try:
            Path(p).unlink(missing_ok=True)
        except Exception:
            print(f"[warn] could not delete pic {p}: {ex}")
            pass

def get_media_by_id(media_id: int):
    conn = get_connection()
    conn.row_factory = sqlite3.Row   # ← add this
    c = conn.cursor()
    c.execute("SELECT * FROM media WHERE id=?", (media_id,))
    row = c.fetchone()
    conn.close()
    return row

# ADD this new function:

def update_media_path(media_id: int, path: str, local_path: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE media SET path=?, local_path=? WHERE id=?", (path, local_path, media_id))
    conn.commit()
    conn.close()