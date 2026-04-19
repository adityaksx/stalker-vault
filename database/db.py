import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).parent / "vault.db"

CATEGORIES = ["friend", "close_friend", "related", "random", "misc", "archived"]

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS people (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        name       TEXT NOT NULL,
        added_at   TEXT DEFAULT (datetime('now','localtime')),
        category   TEXT DEFAULT 'random'
    )""")
    # Migration: add category column if it doesn't exist yet (for existing DBs)
    try:
        c.execute("ALTER TABLE people ADD COLUMN category TEXT DEFAULT 'random'")
    except Exception:
        pass  # column already exists — safe to ignore
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
    # FIX #1: both helpers called inside init_db at the same level
    init_ig_tables()
    init_highlight_tables()


# ── People ──
def create_person(name: str, category: str = "random") -> int:
    if category not in CATEGORIES:
        category = "random"
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO people (name, category) VALUES (?, ?)", (name, category))
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
               (SELECT value FROM fields WHERE person_id=p.id AND field_type='tag' LIMIT 1),
               COALESCE(p.category, 'random')
        FROM people p ORDER BY p.id DESC
    """)
    rows = c.fetchall(); conn.close()
    return rows

def get_person(pid: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, added_at, COALESCE(category, 'random') FROM people WHERE id=?", (pid,))
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

def update_person_category(pid: int, category: str):
    if category not in CATEGORIES:
        category = "random"
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE people SET category=? WHERE id=?", (category, pid))
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
    c.execute("SELECT local_pic_path FROM ig_entries WHERE snapshot_id=?", (snapshot_id,))
    pic_paths = [r[0] for r in c.fetchall() if r[0]]
    c.execute("DELETE FROM ig_snapshots WHERE id=?", (snapshot_id,))
    conn.commit()
    conn.close()
    for p in pic_paths:
        try:
            Path(p).unlink(missing_ok=True)
        except Exception:
            pass

def get_media_by_id(media_id: int):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM media WHERE id=?", (media_id,))
    row = c.fetchone()
    conn.close()
    return row

def update_media_path(media_id: int, path: str, local_path: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE media SET path=?, local_path=? WHERE id=?", (path, local_path, media_id))
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════
# Highlights & Feed Posts
# ═══════════════════════════════════════════════════════════════

def init_highlight_tables():
    # FIX #2: use a proper cursor, not the connection object directly
    conn = get_connection()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS ig_highlights (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        person_id   INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
        name        TEXT NOT NULL,
        zip_name    TEXT,
        imported_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS ig_highlight_stories (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        highlight_id INTEGER NOT NULL REFERENCES ig_highlights(id) ON DELETE CASCADE,
        filename     TEXT,
        path         TEXT,
        is_video     INTEGER DEFAULT 0,
        story_date   TEXT,
        added_at     TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS feed_posts (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        person_id   INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
        post_date   TEXT,
        zip_name    TEXT,
        added_at    TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS feed_post_items (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id     INTEGER NOT NULL REFERENCES feed_posts(id) ON DELETE CASCADE,
        filename    TEXT,
        path        TEXT,
        is_video    INTEGER DEFAULT 0,
        item_date   TEXT,
        added_at    TEXT DEFAULT (datetime('now'))
    );
    """)
    conn.close()

# FIX #3: all highlight/feed write functions use consistent conn+cursor pattern
def create_highlight(person_id, name, zip_name=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO ig_highlights (person_id,name,zip_name) VALUES (?,?,?)", (person_id, name, zip_name))
    hid = c.lastrowid
    conn.commit(); conn.close()
    return hid

def add_highlight_story(highlight_id, filename, path, is_video, story_date=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO ig_highlight_stories (highlight_id,filename,path,is_video,story_date) VALUES (?,?,?,?,?)",
              (highlight_id, filename, path, int(is_video), story_date))
    conn.commit(); conn.close()

def get_highlights(person_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT h.id,h.name,h.imported_at,COUNT(s.id),
               (SELECT path FROM ig_highlight_stories WHERE highlight_id=h.id AND is_video=0 LIMIT 1)
        FROM ig_highlights h LEFT JOIN ig_highlight_stories s ON s.highlight_id=h.id
        WHERE h.person_id=? GROUP BY h.id ORDER BY h.imported_at DESC
    """, (person_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(zip(['id','name','imported_at','story_count','thumb'], r)) for r in rows]

def get_highlight_stories(highlight_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id,filename,path,is_video,story_date,added_at FROM ig_highlight_stories WHERE highlight_id=? ORDER BY story_date,filename",
        (highlight_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(zip(['id','filename','path','is_video','story_date','added_at'], r)) for r in rows]

def create_feed_post(person_id, post_date, zip_name=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO feed_posts (person_id,post_date,zip_name) VALUES (?,?,?)", (person_id, post_date, zip_name))
    post_id = c.lastrowid
    conn.commit(); conn.close()
    return post_id

def add_feed_post_item(post_id, filename, path, is_video, item_date=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO feed_post_items (post_id,filename,path,is_video,item_date) VALUES (?,?,?,?,?)",
              (post_id, filename, path, int(is_video), item_date))
    conn.commit(); conn.close()

def get_feed_posts(person_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id,post_date,added_at FROM feed_posts WHERE person_id=? ORDER BY post_date DESC,added_at DESC", (person_id,))
    post_rows = c.fetchall()
    posts = []
    for row in post_rows:
        post_id, post_date, added_at = row
        c.execute("SELECT id,filename,path,is_video FROM feed_post_items WHERE post_id=? ORDER BY item_date,filename", (post_id,))
        items = c.fetchall()
        posts.append({
            'id': post_id,
            'post_date': post_date,
            'added_at': added_at,
            'items': [dict(zip(['id','filename','path','is_video'], i)) for i in items]
        })
    conn.close()
    return posts

def get_feed_post_items(post_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id,filename,path,is_video,item_date FROM feed_post_items WHERE post_id=? ORDER BY item_date,filename", (post_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(zip(['id','filename','path','is_video','item_date'], r)) for r in rows]
