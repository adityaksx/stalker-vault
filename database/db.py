import sqlite3, json
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "vault.db"

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()

    # Core person record — minimal, just identity
    c.execute("""
    CREATE TABLE IF NOT EXISTS people (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        name     TEXT NOT NULL,
        added_at TEXT DEFAULT (datetime('now'))
    )""")

    # Every piece of info is a "field" row
    # field_type: instagram | snapchat | twitter | linkedin | pinterest |
    #             facebook | tiktok | youtube | telegram | discord | reddit |
    #             threads | bereal | phone | email | whatsapp | dob | gender |
    #             nickname | school | college | workplace | jobtitle | github |
    #             website | location | address | note | tag | custom
    c.execute("""
    CREATE TABLE IF NOT EXISTS fields (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        person_id  INTEGER NOT NULL,
        field_type TEXT NOT NULL,
        label      TEXT,        -- optional custom label e.g. "main account"
        value      TEXT NOT NULL,
        added_at   TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE CASCADE
    )""")

    # Media files (images, videos, zips, repos)
    c.execute("""
    CREATE TABLE IF NOT EXISTS media (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        person_id   INTEGER NOT NULL,
        media_type  TEXT NOT NULL,  -- photo | video | screenshot | repo_zip | repo_url
        filename    TEXT,
        path        TEXT,           -- local file path or URL
        caption     TEXT,
        added_at    TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE CASCADE
    )""")

    conn.commit()
    conn.close()

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
               (SELECT value FROM fields WHERE person_id=p.id AND field_type='instagram' LIMIT 1) as insta,
               (SELECT path  FROM media  WHERE person_id=p.id AND media_type='profile_pic' LIMIT 1) as pic,
               (SELECT value FROM fields WHERE person_id=p.id AND field_type='tag' LIMIT 1) as tag
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
def add_media(person_id: int, media_type: str, path: str, filename: str = None, caption: str = None) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO media (person_id, media_type, filename, path, caption) VALUES (?,?,?,?,?)",
        (person_id, media_type, filename, path, caption)
    )
    mid = c.lastrowid
    conn.commit(); conn.close()
    return mid

def get_media(person_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id, media_type, filename, path, caption, added_at FROM media WHERE person_id=? ORDER BY added_at DESC",
        (person_id,)
    )
    rows = c.fetchall(); conn.close()
    return rows

def delete_media(media_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM media WHERE id=?", (media_id,))
    conn.commit(); conn.close()