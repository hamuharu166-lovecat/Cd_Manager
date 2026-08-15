import os
import re
import streamlit as st
import sqlite3
import datetime as dt

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None


def get_database_url():
    value = os.getenv("DATABASE_URL")
    if value:
        return value
    try:
        return st.secrets["DATABASE_URL"]
    except Exception:
        return None


DB_NAME = "music.db"
DATABASE_URL = get_database_url()
USE_POSTGRES = bool(DATABASE_URL)


class SqlCompatCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query, params=None):
        if USE_POSTGRES and params is not None and "?" in query:
            query = query.replace("?", "%s")
        return self._cursor.execute(query, params)

    @property
    def lastrowid(self):
        return getattr(self._cursor, "lastrowid", None)

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class SqlCompatConnection:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return SqlCompatCursor(self._conn.cursor())

    def commit(self):
        return self._conn.commit()

    def close(self):
        return self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)


def connect_db():
    if USE_POSTGRES:
        if psycopg is None:
            raise RuntimeError("DATABASE_URL が設定されていますが、psycopg が未インストールです。pip install psycopg[binary] を実行してください。")
        try:
            return SqlCompatConnection(psycopg.connect(DATABASE_URL, connect_timeout=10, sslmode="require"))
        except Exception as exc:
            raise RuntimeError(f"PostgreSQL 接続に失敗しました: {exc}") from exc
    try:
        return sqlite3.connect(DB_NAME)
    except Exception as exc:
        raise RuntimeError(f"SQLite 接続に失敗しました: {exc}") from exc


def is_full_width_kana(value):
    if value is None:
        return True
    value = str(value).strip()
    if value == "":
        return True
    return bool(re.fullmatch(r"[ぁ-ゖァ-ヶー　\s]+", value))

# -----------------------------
# DB 初期化
# -----------------------------
def init_db():
    conn = connect_db()
    c = conn.cursor()

    def ensure_column(table_name, column_name, column_type):
        if USE_POSTGRES:
            c.execute(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column_name} {column_type}")
            return
        columns = c.execute(f"PRAGMA table_info({table_name})").fetchall()
        if not any(col[1] == column_name for col in columns):
            c.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

    if USE_POSTGRES:
        album_id_type = "BIGSERIAL PRIMARY KEY"
        people_id_type = "BIGSERIAL PRIMARY KEY"
        role_id_type = "BIGSERIAL PRIMARY KEY"
        other_id_type = "BIGSERIAL PRIMARY KEY"
    else:
        album_id_type = "INTEGER PRIMARY KEY AUTOINCREMENT"
        people_id_type = "INTEGER PRIMARY KEY AUTOINCREMENT"
        role_id_type = "INTEGER PRIMARY KEY AUTOINCREMENT"
        other_id_type = "INTEGER PRIMARY KEY AUTOINCREMENT"

    # -----------------------------
    # アルバム
    # -----------------------------
    c.execute(f"""
        CREATE TABLE IF NOT EXISTS albums (
            id {album_id_type},
            catalog_no TEXT,
            title TEXT NOT NULL,
            year INTEGER,
            release_date TEXT,
            omnibus_flag BOOLEAN DEFAULT FALSE,
            album_type TEXT,
            note TEXT,
            album_kana TEXT,
            original_release_date TEXT
        )
    """)
    ensure_column("albums", "album_kana", "TEXT")
    ensure_column("albums", "original_release_date", "TEXT")

    # -----------------------------
    # 曲
    # -----------------------------
    c.execute(f"""
        CREATE TABLE IF NOT EXISTS tracks (
            id {other_id_type},
            album_id INTEGER,
            track_no INTEGER,
            title TEXT NOT NULL,
            duration TEXT,
            note TEXT,
            track_kana TEXT,
            original_release_date TEXT,
            FOREIGN KEY(album_id) REFERENCES albums(id)
        )
    """)
    ensure_column("tracks", "track_kana", "TEXT")
    ensure_column("tracks", "original_release_date", "TEXT")

    # -----------------------------
    # 人物（アーティスト・作詞者・作曲者・編曲者・演奏者）
    # -----------------------------
    c.execute(f"""
        CREATE TABLE IF NOT EXISTS people (
            id {people_id_type},
            name TEXT NOT NULL UNIQUE,
            note TEXT
        )
    """)

    # -----------------------------
    # 役割（Artist / Composer / Arranger / Lyricist / Performer）
    # -----------------------------
    c.execute(f"""
        CREATE TABLE IF NOT EXISTS roles (
            id {role_id_type},
            role_name TEXT NOT NULL UNIQUE
        )
    """)

    # 初期役割データを挿入
    default_roles = ["Artist", "Composer", "Arranger", "Lyricist", "Performer"]
    for role in default_roles:
        if USE_POSTGRES:
            c.execute("INSERT INTO roles (role_name) VALUES (%s) ON CONFLICT (role_name) DO NOTHING", (role,))
        else:
            c.execute("INSERT OR IGNORE INTO roles (role_name) VALUES (?)", (role,))

    # -----------------------------
    # アルバム × 人物 × 役割
    # -----------------------------
    c.execute(f"""
        CREATE TABLE IF NOT EXISTS album_people (
            id {other_id_type},
            album_id INTEGER,
            person_id INTEGER,
            role_id INTEGER,
            instrument TEXT,
            note TEXT,
            FOREIGN KEY(album_id) REFERENCES albums(id),
            FOREIGN KEY(person_id) REFERENCES people(id),
            FOREIGN KEY(role_id) REFERENCES roles(id)
        )
    """)

    # -----------------------------
    # 曲 × 人物 × 役割
    # -----------------------------
    c.execute(f"""
        CREATE TABLE IF NOT EXISTS track_people (
            id {other_id_type},
            track_id INTEGER,
            person_id INTEGER,
            role_id INTEGER,
            instrument TEXT,
            note TEXT,
            FOREIGN KEY(track_id) REFERENCES tracks(id),
            FOREIGN KEY(person_id) REFERENCES people(id),
            FOREIGN KEY(role_id) REFERENCES roles(id)
        )
    """)

    conn.commit()
    conn.close()

# -----------------------------
# DB 操作（アルバム）
# -----------------------------
def add_album(catalog_no, title,  year, release_date, album_type, note, omnibus_flag=False, album_kana="", original_release_date=""):
    conn = connect_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO albums (catalog_no, title, year, release_date, omnibus_flag, album_type, note, album_kana, original_release_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (catalog_no, title, year, release_date, omnibus_flag, album_type, note, album_kana, original_release_date))
    conn.commit()
    album_id = c.lastrowid
    conn.close()
    return album_id

def get_album(album_id):
    conn = connect_db()
    c = conn.cursor()
    c.execute("""
        SELECT id, catalog_no, title, year, release_date, omnibus_flag, album_type, note, album_kana, original_release_date
        FROM albums
        WHERE id = ?
    """, (album_id,))
    result = c.fetchone()
    conn.close()
    return result

@st.cache_data(ttl=120)
def load_albums_page(limit=50, offset=0, search_artist=None, search_title=None):
    conn = connect_db()
    c = conn.cursor()

    # Fast path for artist search on Postgres: first resolve matching person ids using trigram index,
    # then restrict album_people to those person_ids and artist role to avoid large joins.
    params = []

    if search_artist and USE_POSTGRES:
        # get matching person ids
        person_ids = get_person_ids_by_name(search_artist)
        if not person_ids:
            conn.close()
            return []
        artist_role_id = get_artist_role_id()
        sql = """
            SELECT a.id, a.catalog_no, a.title, a.year, a.release_date,
                COALESCE(string_agg(p.name, ', ' ORDER BY p.name) FILTER (WHERE r.role_name = 'Artist'), '') AS artists
            FROM albums a
            JOIN album_people ap ON ap.album_id = a.id AND ap.role_id = ? AND ap.person_id = ANY(?)
            LEFT JOIN roles r ON ap.role_id = r.id
            LEFT JOIN people p ON ap.person_id = p.id
            GROUP BY a.id
            ORDER BY artists, COALESCE(a.release_date, a.year::text), a.title
            LIMIT ? OFFSET ?
        """
        params = [artist_role_id, tuple(person_ids), limit, offset]
        c.execute(sql, params)
        rows = c.fetchall()
        conn.close()
        return rows

    # Fallback / generic path (handles title search and SQLite)
    where_clauses = []
    if search_title:
        where_clauses.append("lower(a.title) LIKE ?")
        params.append(f"%{search_title.lower()}%")

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    if USE_POSTGRES:
        sql = f"""
            SELECT a.id, a.catalog_no, a.title, a.year, a.release_date,
                COALESCE(string_agg(p.name, ', ' ORDER BY p.name) FILTER (WHERE r.role_name = 'Artist'), '') AS artists
            FROM albums a
            LEFT JOIN album_people ap ON ap.album_id = a.id
            LEFT JOIN roles r ON ap.role_id = r.id
            LEFT JOIN people p ON ap.person_id = p.id
            WHERE {where_sql}
            GROUP BY a.id
            ORDER BY artists, COALESCE(a.release_date, a.year::text), a.title
            LIMIT ? OFFSET ?
        """
    else:
        sql = f"""
            SELECT a.id, a.catalog_no, a.title, a.year, a.release_date,
                COALESCE(GROUP_CONCAT(DISTINCT CASE WHEN r.role_name='Artist' THEN p.name END), '') AS artists
            FROM albums a
            LEFT JOIN album_people ap ON ap.album_id = a.id
            LEFT JOIN roles r ON ap.role_id = r.id
            LEFT JOIN people p ON ap.person_id = p.id
            WHERE {where_sql}
            GROUP BY a.id
            ORDER BY artists, COALESCE(a.release_date, a.year), a.title
            LIMIT ? OFFSET ?
        """

    params.extend([limit, offset])
    c.execute(sql, params)
    rows = c.fetchall()
    conn.close()
    return rows


def count_albums(search_artist=None, search_title=None):
    conn = connect_db()
    c = conn.cursor()

    # If searching by artist on Postgres, leverage person id resolution for efficiency
    params = []
    if search_artist and USE_POSTGRES:
        person_ids = get_person_ids_by_name(search_artist)
        if not person_ids:
            conn.close()
            return 0
        artist_role_id = get_artist_role_id()
        sql = "SELECT COUNT(DISTINCT a.id) FROM albums a JOIN album_people ap ON ap.album_id = a.id AND ap.role_id = ? AND ap.person_id = ANY(?)"
        params = [artist_role_id, tuple(person_ids)]
        c.execute(sql, params)
        row = c.fetchone()
        conn.close()
        return row[0] if row else 0

    where_clauses = []
    if search_title:
        where_clauses.append("lower(a.title) LIKE ?")
        params.append(f"%{search_title.lower()}%")
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    sql = f"SELECT COUNT(DISTINCT a.id) FROM albums a LEFT JOIN album_people ap ON ap.album_id = a.id LEFT JOIN roles r ON ap.role_id = r.id LEFT JOIN people p ON ap.person_id = p.id WHERE {where_sql}"
    c.execute(sql, params)
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0


def get_albums():
    # backward-compatible wrapper that returns all albums (no paging)
    return load_albums_page(limit=1000, offset=0)


def get_album_artist_names(album_id):
    conn = connect_db()
    c = conn.cursor()
    c.execute("""
        SELECT p.name
        FROM album_people ap
        JOIN people p ON ap.person_id = p.id
        JOIN roles r ON ap.role_id = r.id
        WHERE ap.album_id = ? AND r.role_name = 'Artist'
        ORDER BY p.name
    """, (album_id,))
    result = [row[0] for row in c.fetchall()]
    conn.close()
    return result


def get_all_tracks():
    conn = connect_db()
    c = conn.cursor()
    c.execute("""
        SELECT id, album_id, track_no, title, duration, note, track_kana, original_release_date
        FROM tracks
        ORDER BY title
    """)
    result = c.fetchall()
    conn.close()
    return result


def get_track_artist_names(track_id):
    conn = connect_db()
    c = conn.cursor()
    c.execute("""
        SELECT p.name
        FROM track_people tp
        JOIN people p ON tp.person_id = p.id
        JOIN roles r ON tp.role_id = r.id
        WHERE tp.track_id = ? AND r.role_name = 'Artist'
        ORDER BY p.name
    """, (track_id,))
    result = [row[0] for row in c.fetchall()]
    conn.close()
    return result


def get_albums_by_person(person_id):
    conn = connect_db()
    c = conn.cursor()
    c.execute("""
        SELECT
            ap.album_id,
            a.catalog_no,
            a.title,
            r.role_name,
            ap.instrument,
            ap.note
        FROM album_people ap
        JOIN albums a ON ap.album_id = a.id
        JOIN roles r ON ap.role_id = r.id
        WHERE ap.person_id = ?
        ORDER BY a.year, a.title
    """, (person_id,))
    result = c.fetchall()
    conn.close()
    return result

def update_album(album_id, catalog_no, title, year, release_date, album_type, note, omnibus_flag, album_kana="", original_release_date=""):
    conn = connect_db()
    c = conn.cursor()
    c.execute("""
        UPDATE albums
        SET catalog_no=?, title=?, year=?, release_date=?, album_type=?, note=?, omnibus_flag=?, album_kana=?, original_release_date=?
        WHERE id=?
    """, (catalog_no, title, year, release_date, album_type, note, omnibus_flag, album_kana, original_release_date, album_id))
    conn.commit()
    conn.close()

# -----------------------------
# DB 操作（曲）
# -----------------------------
def add_track(album_id, track_no, title, duration, note, track_kana="", original_release_date=""):
    conn = connect_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO tracks (album_id, track_no, title, duration, note, track_kana, original_release_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (album_id, track_no, title, duration, note, track_kana, original_release_date))
    conn.commit()
    track_id = c.lastrowid
    conn.close()
    return track_id

def update_track(track_id, track_no, title, duration, note, track_kana="", original_release_date=""):
    conn = connect_db()
    c = conn.cursor()
    c.execute("""
        UPDATE tracks
        SET track_no=?, title=?, duration=?, note=?, track_kana=?, original_release_date=?
        WHERE id=?
    """, (track_no, title, duration, note, track_kana, original_release_date, track_id))
    conn.commit()
    conn.close()

def get_tracks_by_album(album_id):
    conn = connect_db()
    c = conn.cursor()
    c.execute("""
        SELECT id, album_id, track_no, title, duration, note, track_kana, original_release_date
        FROM tracks
        WHERE album_id = ?
        ORDER BY track_no ASC
    """, (album_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_track(track_id):
    conn = connect_db()
    c = conn.cursor()
    c.execute("""
        SELECT id, album_id, track_no, title, duration, note, track_kana, original_release_date
        FROM tracks
        WHERE id = ?
    """, (track_id,))
    row = c.fetchone()
    conn.close()
    return row

def delete_track(track_id):
    conn = connect_db()
    c = conn.cursor()
    # delete related track_people rows
    c.execute("DELETE FROM track_people WHERE track_id = ?", (track_id,))
    # delete the track itself
    c.execute("DELETE FROM tracks WHERE id = ?", (track_id,))
    conn.commit()
    conn.close()

def get_tracks_by_person(person_id):
    conn = connect_db()
    c = conn.cursor()
    c.execute("""
        SELECT
            tp.track_id,
            t.title,
            r.role_name,
            tp.instrument,
            tp.note
        FROM track_people tp
        JOIN tracks t ON tp.track_id = t.id
        JOIN roles r ON tp.role_id = r.id
        WHERE tp.person_id = ?
        ORDER BY t.track_no, t.title
    """, (person_id,))
    result = c.fetchall()
    conn.close()
    return result

# -----------------------------
# DB 操作（曲 × 人物）
# -----------------------------
def add_track_people(track_id, person_id, role_id, instrument, note):
    conn = connect_db()
    c = conn.cursor()
    # avoid duplicate track_people entries
    c.execute("SELECT 1 FROM track_people WHERE track_id = ? AND person_id = ? AND role_id = ?", (track_id, person_id, role_id))
    if c.fetchone():
        conn.close()
        return None

    try:
        if USE_POSTGRES:
            c.execute(
                "INSERT INTO track_people (track_id, person_id, role_id, instrument, note) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (track_id, person_id, role_id, instrument, note)
            )
            inserted = c.rowcount
        else:
            c.execute(
                "INSERT OR IGNORE INTO track_people (track_id, person_id, role_id, instrument, note) VALUES (?, ?, ?, ?, ?)",
                (track_id, person_id, role_id, instrument, note)
            )
            inserted = c.rowcount
        conn.commit()
    except Exception as exc:
        print(f"add_track_people: unexpected error inserting track_id={track_id}, person_id={person_id}, role_id={role_id}: {exc}")
        conn.close()
        raise
    finally:
        conn.close()
    return bool(inserted)

def get_track_people(track_id):
    conn = connect_db()
    c = conn.cursor()
    c.execute("""
        SELECT 
            tp.id,               -- track_people の ID（削除時に使う）
            tp.person_id,        -- 人物ID
            p.name,              -- 人物名
            tp.role_id,          -- 役割ID
            r.role_name,         -- 役割名
            tp.instrument,       -- 楽器
            tp.note              -- 備考
        FROM track_people tp
        JOIN people p ON tp.person_id = p.id
        JOIN roles r ON tp.role_id = r.id
        WHERE tp.track_id = ?
        ORDER BY r.role_name, p.name
    """, (track_id,))
    result = c.fetchall()
    conn.close()
    return result

def delete_track_people(tp_id):
    conn = connect_db()
    c = conn.cursor()
    c.execute("DELETE FROM track_people WHERE id = ?", (tp_id,))
    conn.commit()
    conn.close()

def update_track_people(tp_id, person_id, role_id, instrument, note):
    conn = connect_db()
    c = conn.cursor()
    c.execute("""
        UPDATE track_people
        SET person_id = ?, role_id = ?, instrument = ?, note = ?
        WHERE id = ?
    """, (person_id, role_id, instrument, note, tp_id))
    conn.commit()
    conn.close()

# -----------------------------
# DB 操作（アルバム × 役割 × 人物）
# -----------------------------
def add_album_people(album_id, person_id, role_id, instrument, note):
    conn = connect_db()
    c = conn.cursor()
    # avoid duplicate album_people entries: check existence first (best-effort)
    try:
        c.execute("SELECT 1 FROM album_people WHERE album_id = ? AND person_id = ? AND role_id = ?", (album_id, person_id, role_id))
        if c.fetchone():
            conn.close()
            return None
    except Exception:
        # if this select fails for any reason, continue to attempt insert and let DB handle uniqueness
        pass

    try:
        if USE_POSTGRES:
            # use Postgres upsert-free pattern to avoid race conditions
            c.execute(
                "INSERT INTO album_people (album_id, person_id, role_id, instrument, note) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (album_id, person_id, role_id, instrument, note)
            )
            inserted = c.rowcount
        else:
            # SQLite: use INSERT OR IGNORE to avoid unique constraint errors
            c.execute(
                "INSERT OR IGNORE INTO album_people (album_id, person_id, role_id, instrument, note) VALUES (?, ?, ?, ?, ?)",
                (album_id, person_id, role_id, instrument, note)
            )
            inserted = c.rowcount
        conn.commit()
    except Exception as exc:
        # If unexpected error, log and re-raise
        print(f"add_album_people: unexpected error inserting album_id={album_id}, person_id={person_id}, role_id={role_id}: {exc}")
        conn.close()
        raise
    finally:
        conn.close()

    # rowcount is 1 if a row was inserted, 0 if ignored due to conflict
    return bool(inserted)

def get_album_people(album_id):
    conn = connect_db()
    c = conn.cursor()
    c.execute("""
        SELECT ap.id, ap.person_id, p.name, ap.role_id, r.role_name, ap.instrument, ap.note
        FROM album_people ap
        JOIN people p ON ap.person_id = p.id
        JOIN roles r ON ap.role_id = r.id
        WHERE ap.album_id = ?
        ORDER BY r.role_name, p.name
    """, (album_id,))
    result = c.fetchall()
    conn.close()
    return result

def delete_album_people(ap_id):
    conn = connect_db()
    c = conn.cursor()
    c.execute("DELETE FROM album_people WHERE id = ?", (ap_id,))
    conn.commit()
    conn.close()

# -----------------------------
# DB 操作（人物）
# -----------------------------
def get_people():
    conn = connect_db()
    c = conn.cursor()
    c.execute("SELECT id, name, note FROM people ORDER BY name")
    result = c.fetchall()
    conn.close()
    return result

def add_person(name, note):
    conn = connect_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO people (name, note)
        VALUES (?, ?)
    """, (name, note))
    conn.commit()
    conn.close()

def get_person(person_id):
    conn = connect_db()
    c = conn.cursor()
    c.execute("SELECT id, name, note FROM people WHERE id = ?", (person_id,))
    result = c.fetchone()
    conn.close()
    return result

def update_person(person_id, name, note):
    conn = connect_db()
    c = conn.cursor()
    c.execute("""
        UPDATE people
        SET name = ?, note = ?
        WHERE id = ?
    """, (name, note, person_id))
    conn.commit()
    conn.close()

def get_person_by_name(name):
    conn = connect_db()
    c = conn.cursor()
    c.execute("SELECT id, name, note FROM people WHERE name = ?", (name,))
    result = c.fetchone()
    conn.close()
    return result

# -----------------------------
# DB 操作（役割）
# -----------------------------
def get_roles():
    conn = connect_db()
    c = conn.cursor()
    c.execute("SELECT id, role_name FROM roles ORDER BY role_name")
    result = c.fetchall()
    conn.close()
    return result

def get_role_by_name(role_name):
    conn = connect_db()
    c = conn.cursor()
    c.execute("""
        SELECT id, role_name
        FROM roles
        WHERE role_name = ?
    """, (role_name,))
    result = c.fetchone()
    conn.close()
    return result


# Helper: return list of person ids matching a name pattern (uses trigram index on Postgres)
def get_person_ids_by_name(name):
    conn = connect_db()
    c = conn.cursor()
    if USE_POSTGRES:
        # ILIKE uses trigram index when pg_trgm is available
        c.execute("SELECT id FROM people WHERE name ILIKE ?", (f"%{name}%",))
    else:
        c.execute("SELECT id FROM people WHERE lower(name) LIKE ?", (f"%{name.lower()}%",))
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]


# Helper: cached artist role id
@st.cache_data(ttl=3600)
def get_artist_role_id():
    row = get_role_by_name('Artist')
    return row[0] if row else None

def add_role(role_name):
    conn = connect_db()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO roles (role_name) VALUES (?)", (role_name,))
    conn.commit()
    # fetch id
    c.execute("SELECT id FROM roles WHERE role_name = ?", (role_name,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="CD / 曲データ管理アプリ", layout="wide")
st.title("🎵 CD / 曲データ管理アプリ")

try:
    init_db()
except Exception as exc:
    masked = str(DATABASE_URL)
    if DATABASE_URL:
        try:
            prefix, rest = DATABASE_URL.split("://", 1)
            if "@" in rest:
                userinfo, hostpart = rest.rsplit("@", 1)
                user, password = userinfo.split(":", 1)
                masked = f"{prefix}://{user}:***@{hostpart}"
            else:
                masked = f"{prefix}://***@{rest}"
        except Exception:
            pass
    st.error(f"データベース接続に失敗しました。詳細: {exc}")
    st.code(f"DATABASE_URL={masked}")
    st.stop()

# initialize session state defaults
if "view" not in st.session_state:
    st.session_state.view = "album_list"
if "current_album_id" not in st.session_state:
    st.session_state.current_album_id = None
if "current_track_id" not in st.session_state:
    st.session_state.current_track_id = None
if "current_person_id" not in st.session_state:
    st.session_state.current_person_id = None
if "return_view" not in st.session_state:
    st.session_state.return_view = "album_list"

# Define canonical view names to avoid accidental mismatches later
ALL_VIEWS = {
    "album_list",
    "album_search",
    "album_search_results",
    "album_view",
    "album_edit",
    "album_register",
    "track_register",
    "track_edit",
    "track_search",
    "track_search_results",
    "track_view",
    "people_list",
    "person_edit"
}

# sanitize current view
if st.session_state.view not in ALL_VIEWS:
    st.session_state.view = "album_list"

# Sidebar menu as clickable links (buttons) so user can navigate from any screen
st.sidebar.markdown("### メニュー")
if st.sidebar.button("アルバム一覧"):
    st.session_state.view = "album_list"
    st.session_state.current_album_id = None
    st.session_state.current_track_id = None
    st.rerun()

if st.sidebar.button("アルバム検索"):
    st.session_state.view = "album_search"
    st.session_state.current_album_id = None
    st.session_state.current_track_id = None
    st.rerun()

if st.sidebar.button("曲検索"):
    st.session_state.view = "track_search"
    st.session_state.current_album_id = None
    st.session_state.current_track_id = None
    st.rerun()

if st.sidebar.button("人物一覧"):
    st.session_state.view = "people_list"
    st.session_state.current_person_id = None
    st.rerun()

# -----------------------------
# アルバム検索画面
# -----------------------------
if st.session_state.view == "album_search":
    st.header("🔎 アルバム検索")
    artist_keyword = st.text_input("アーティスト名", value="")
    album_keyword = st.text_input("アルバム名", value="")

    if st.button("検索"):
        st.session_state.album_search_artist = artist_keyword.strip()
        st.session_state.album_search_album = album_keyword.strip()
        st.session_state.view = "album_search_results"
        st.rerun()

    if st.button("アルバム一覧に戻る"):
        st.session_state.view = "album_list"
        st.rerun()

elif st.session_state.view == "album_search_results":
    st.header("🔎 アルバム検索結果")
    artist_keyword = (st.session_state.get("album_search_artist") or "").strip().lower()
    album_keyword = (st.session_state.get("album_search_album") or "").strip().lower()

    rows = []
    for album in get_albums():
        album_id = album[0]
        title = album[2] or ""
        release_date = album[4] or album[3] or ""
        artists = get_album_artist_names(album_id)
        artist_text = ", ".join(artists) if artists else "（未登録）"

        if artist_keyword and artist_keyword not in artist_text.lower():
            continue
        if album_keyword and album_keyword not in title.lower():
            continue

        rows.append({
            "album_id": album_id,
            "artist": artist_text,
            "title": title,
            "release_date": release_date,
        })

    def album_sort_key(row):
        release_text = str(row["release_date"] or "")
        if release_text:
            release_key = release_text
        else:
            release_key = "9999-12-31"
        return (row["artist"].lower(), release_key, row["title"].lower())

    rows.sort(key=album_sort_key)

    if not rows:
        st.info("条件に一致するアルバムはありません。")
    else:
        cols = st.columns([3, 4, 2])
        cols[0].write("**アーティスト名**")
        cols[1].write("**アルバム名**")
        cols[2].write("**発売日**")

        for row in rows:
            cols = st.columns([3, 4, 2])
            cols[0].write(row["artist"])
            if cols[1].button(row["title"], key=f"album_search_result_{row['album_id']}"):
                st.session_state.current_album_id = row["album_id"]
                st.session_state.return_view = "album_search_results"
                st.session_state.view = "album_view"
                st.rerun()
            cols[2].write(row["release_date"])

    if st.button("条件を変更"):
        st.session_state.view = "album_search"
        st.rerun()

# -----------------------------
# 曲検索画面
# -----------------------------
elif st.session_state.view == "track_search":
    st.header("🔎 曲検索")

    search_cols = st.columns(5)
    artist_keyword = search_cols[0].text_input("アーティスト名", value="")
    track_keyword = search_cols[1].text_input("曲名", value="")
    lyricist_keyword = search_cols[2].text_input("作詞者", value="")
    composer_keyword = search_cols[3].text_input("作曲者", value="")
    arranger_keyword = search_cols[4].text_input("編曲者", value="")

    other_person_cols = st.columns(2)
    other_person_keyword = other_person_cols[0].text_input("人物名（作詞者/作曲者/編曲者以外）", value="")

    if st.button("検索"):
        st.session_state.track_search_artist = artist_keyword.strip()
        st.session_state.track_search_title = track_keyword.strip()
        st.session_state.track_search_lyricist = lyricist_keyword.strip()
        st.session_state.track_search_composer = composer_keyword.strip()
        st.session_state.track_search_arranger = arranger_keyword.strip()
        st.session_state.track_search_other_person = other_person_keyword.strip()
        st.session_state.view = "track_search_results"
        st.rerun()

    if st.button("アルバム一覧に戻る"):
        st.session_state.view = "album_list"
        st.rerun()

elif st.session_state.view == "track_search_results":
    st.header("🔎 曲検索結果")
    artist_keyword = (st.session_state.get("track_search_artist") or "").strip().lower()
    track_keyword = (st.session_state.get("track_search_title") or "").strip().lower()
    lyricist_keyword = (st.session_state.get("track_search_lyricist") or "").strip().lower()
    composer_keyword = (st.session_state.get("track_search_composer") or "").strip().lower()
    arranger_keyword = (st.session_state.get("track_search_arranger") or "").strip().lower()
    other_person_keyword = (st.session_state.get("track_search_other_person") or "").strip().lower()

    rows = []
    for track in get_all_tracks():
        track_id = track[0]
        album_id = track[1]
        album = get_album(album_id)
        if album is None:
            continue

        title = track[3] or ""
        album_title = album[2] or ""
        artists = get_track_artist_names(track_id) or get_album_artist_names(album_id)
        artist_text = ", ".join(artists) if artists else "（未登録）"
        tp = get_track_people(track_id)
        lyricists = ", ".join([r[2] for r in tp if r[4] == "Lyricist"]) or ""
        composers = ", ".join([r[2] for r in tp if r[4] == "Composer"]) or ""
        arrangers = ", ".join([r[2] for r in tp if r[4] == "Arranger"]) or ""
        other_people = ", ".join([r[2] for r in tp if r[4] not in ("Lyricist", "Composer", "Arranger", "Artist")]) or ""

        if artist_keyword and artist_keyword not in artist_text.lower():
            continue
        if track_keyword and track_keyword not in title.lower():
            continue
        if lyricist_keyword and lyricist_keyword not in lyricists.lower():
            continue
        if composer_keyword and composer_keyword not in composers.lower():
            continue
        if arranger_keyword and arranger_keyword not in arrangers.lower():
            continue
        if other_person_keyword and other_person_keyword not in other_people.lower():
            continue

        rows.append({
            "track_id": track_id,
            "album_id": album_id,
            "artist": artist_text,
            "album_title": album_title,
            "title": title,
            "lyricist": lyricists,
            "composer": composers,
            "arranger": arrangers,
        })

    def track_search_sort_key(row):
        album_obj = get_album(row["album_id"])
        album_release = album_obj[4] if album_obj else ""
        release_text = str(album_release or "")
        if release_text:
            release_key = release_text
        else:
            release_key = "9999-12-31"
        return (row["artist"].lower(), release_key, row["album_title"].lower(), row["title"].lower())

    rows.sort(key=track_search_sort_key)

    if not rows:
        st.info("条件に一致する曲はありません。")
    else:
        cols = st.columns([3, 4, 4, 2, 2, 2])
        cols[0].write("**アーティスト名**")
        cols[1].write("**アルバム名**")
        cols[2].write("**曲名**")
        cols[3].write("**作詞者**")
        cols[4].write("**作曲者**")
        cols[5].write("**編曲者**")

        for row in rows:
            cols = st.columns([3, 4, 4, 2, 2, 2])
            cols[0].write(row["artist"])
            cols[1].write(row["album_title"])
            if cols[2].button(row["title"], key=f"track_search_result_{row['track_id']}"):
                st.session_state.current_track_id = row["track_id"]
                st.session_state.current_album_id = row["album_id"]
                st.session_state.return_view = "track_search_results"
                st.session_state.view = "track_view"
                st.rerun()
            cols[3].write(row["lyricist"] or "-")
            cols[4].write(row["composer"] or "-")
            cols[5].write(row["arranger"] or "-")

    if st.button("条件を変更"):
        st.session_state.view = "track_search"
        st.rerun()

# -----------------------------
# 人物一覧画面
# -----------------------------
elif st.session_state.view == "people_list":
    st.header("👤 人物一覧")

    people = get_people()  # [(id, name, note)]

    if not people:
        st.info("登録されている人物はありません。")
    else:
        for p in people:
            person_id = p[0]
            name = p[1]
            note = p[2]

            # 人物名をクリックすると編集画面へ遷移
            if st.button(name, key=f"person_{person_id}"):
                st.session_state.current_person_id = person_id
                st.session_state.view = "person_edit"
                st.rerun()

            st.write(note or "")
            st.markdown("---")

# -----------------------------
# 人物編集画面
# -----------------------------
elif st.session_state.view == "person_edit":
    st.header("👤 人物編集")

    if st.session_state.current_person_id is None:
        st.warning("人物が選択されていません。")
        if st.button("人物一覧に戻る"):
            st.session_state.view = "people_list"
            st.rerun()
        st.stop()

    person = get_person(st.session_state.current_person_id)
    if person is None:
        st.warning("人物情報が見つかりませんでした。")
        if st.button("人物一覧に戻る"):
            st.session_state.view = "people_list"
            st.rerun()
        st.stop()

    person_id, person_name, person_note = person

    edited_name = st.text_input("人物名", value=person_name or "")
    edited_note = st.text_area("備考", value=person_note or "")

    col1, col2 = st.columns([1, 1])
    if col1.button("更新する"):
        if not edited_name.strip():
            st.error("人物名は必須です")
        else:
            update_person(person_id, edited_name.strip(), edited_note)
            st.success("人物情報を更新しました")
            st.session_state.view = "people_list"
            st.rerun()

    if col2.button("一覧に戻る"):
        st.session_state.view = "people_list"
        st.rerun()

    st.markdown("---")

    st.subheader("関連アルバム")
    related_albums = get_albums_by_person(person_id)
    if related_albums:
        for album_id, catalog_no, title, role_name, instrument, note in related_albums:
            album_label = f"{title} ({catalog_no or '品番未登録'})"
            st.write(f"- {album_label} / 役割: {role_name} / 楽器: {instrument or '-'}")
    else:
        st.write("関連するアルバムはありません")

    st.markdown("---")

    st.subheader("関連曲")
    related_tracks = get_tracks_by_person(person_id)
    if related_tracks:
        for track_id, title, role_name, instrument, note in related_tracks:
            st.write(f"- {title} / 役割: {role_name} / 楽器: {instrument or '-'}")
    else:
        st.write("関連する曲はありません")

# -----------------------------
# アルバム一覧画面
# -----------------------------
elif st.session_state.view == "album_list":
    st.header("📚 アルバム一覧")

    # paging
    page_size = 50
    page = st.session_state.get("album_list_page", 0)
    total = count_albums()
    max_page = max(0, (total - 1) // page_size) if total else 0

    cols_nav = st.columns([1, 1, 6])
    if cols_nav[0].button("前のページ") and page > 0:
        st.session_state.album_list_page = page - 1
        st.experimental_rerun()
    cols_nav[1].button("次のページ") and (page < max_page) and st.session_state.update({"album_list_page": page + 1})

    st.write(f"ページ {page + 1} / {max_page + 1} （合計 {total} 件）")

    offset = page * page_size
    albums = load_albums_page(limit=page_size, offset=offset)

    if not albums:
        st.info("登録されているアルバムはありません。")
    else:
        cols = st.columns([3, 4, 2])
        cols[0].write("**アーティスト名**")
        cols[1].write("**アルバム名**")
        cols[2].write("**発売日**")

        for album in albums:
            album_id, catalog_no, title, year, release_date, artists = album
            artist_text = artists or "（アーティスト未登録）"
            cols = st.columns([3, 4, 2])
            cols[0].write(artist_text)
            if cols[1].button(title or "(無題)", key=f"album_{album_id}"):
                st.session_state.current_album_id = album_id
                st.session_state.return_view = "album_list"
                st.session_state.view = "album_view"
                st.rerun()
            cols[2].write(release_date or (year or ""))

    st.markdown("---")

    # 新規登録ボタン
    if st.button("＋ 新規アルバムを登録"):
        st.session_state.view = "album_register"
        st.rerun()

# -----------------------------
# アルバム表示画面
# -----------------------------
elif st.session_state.view == "album_view":
    album_id = st.session_state.current_album_id
    album = get_album(album_id)

    if not album:
        st.error("アルバムが選択されていません")
        st.stop()

    st.header(f"📀 アルバム表示：{album[2]}")

    # -----------------------------
    # アルバム基本情報の表示
    # -----------------------------
    st.write(f"**品番**：{album[1] or ''}")
    st.write(f"**アルバム名**：{album[2]}")

    # アーティスト名表示
    ap_list = get_album_people(album_id)
    artists = [ap[2] for ap in ap_list if ap[4] == "Artist"]
    artist_text = ", ".join(artists) if artists else "（未登録）"
    st.write(f"**アーティスト**：{artist_text}")

    if album[4]:
        st.write(f"**発売日**：{album[4]}")
    else:
        st.write(f"**発売年**：{album[3] or ''}")
    st.write(f"**種別**：{album[6] or ''}")
    st.write(f"**オムニバス**：{'はい' if album[5] else ''}")
    st.write(f"**備考**：{album[7] or ''}")

    st.markdown("---")

    # -----------------------------
    # 曲一覧表示（曲番号、アーティスト（オムニバスの場合のみ）、曲名、作詞、作曲、編曲）
    # -----------------------------
    st.subheader("曲一覧")

    tracks = get_tracks_by_album(album_id)
    is_omnibus = bool(album[5])
    if tracks:
        # header
        if is_omnibus:
            cols = st.columns([1, 3, 5, 3, 3, 3])
            cols[0].write("#")
            cols[1].write("アーティスト")
            cols[2].write("曲名")
            cols[3].write("作詞")
            cols[4].write("作曲")
            cols[5].write("編曲")
        else:
            cols = st.columns([1, 5, 3, 3, 3])
            cols[0].write("#")
            cols[1].write("曲名")
            cols[2].write("作詞")
            cols[3].write("作曲")
            cols[4].write("編曲")

        for t in tracks:
            track_id = t[0]
            track_no = t[2]
            track_title = t[3] or "(無題)"
            tp = get_track_people(track_id)
            lyricist = ", ".join([r[2] for r in tp if r[4] == "Lyricist"]) or ""
            composer = ", ".join([r[2] for r in tp if r[4] == "Composer"]) or ""
            arranger = ", ".join([r[2] for r in tp if r[4] == "Arranger"]) or ""
            artist = ", ".join([r[2] for r in tp if r[4] == "Artist"]) or ""

            if is_omnibus:
                row_cols = st.columns([1, 3, 5, 3, 3, 3])
                row_cols[0].write(str(track_no))
                row_cols[1].write(artist or "（未登録）")
                if row_cols[2].button(track_title, key=f"view_track_{track_id}"):
                    st.session_state.current_track_id = track_id
                    st.session_state.current_album_id = album_id
                    st.session_state.return_view = "album_view"
                    st.session_state.view = "track_view"
                    st.rerun()
                row_cols[3].write(lyricist)
                row_cols[4].write(composer)
                row_cols[5].write(arranger)
            else:
                row_cols = st.columns([1, 5, 3, 3, 3])
                row_cols[0].write(str(track_no))
                if row_cols[1].button(track_title, key=f"view_track_{track_id}"):
                    st.session_state.current_track_id = track_id
                    st.session_state.current_album_id = album_id
                    st.session_state.return_view = "album_view"
                    st.session_state.view = "track_view"
                    st.rerun()
                row_cols[2].write(lyricist)
                row_cols[3].write(composer)
                row_cols[4].write(arranger)
    else:
        st.write("曲が登録されていません")

    st.markdown("---")

    # -----------------------------
    # 編集ボタン
    # -----------------------------
    if st.button("✏️ 編集する"):
        st.session_state.view = "album_edit"
        st.rerun()

    # -----------------------------
    # 前の画面に戻る
    # -----------------------------
    if st.button("前の画面に戻る"):
        st.session_state.view = st.session_state.get("return_view", "album_list")
        st.rerun()

    if st.button("一覧に戻る"):
        st.session_state.view = "album_list"
        st.rerun()

# -----------------------------
# 曲情報表示画面
# -----------------------------
elif st.session_state.view == "track_view":
    track_id = st.session_state.get("current_track_id")
    album_id = st.session_state.get("current_album_id")
    if not track_id or not album_id:
        st.error("表示する曲が選択されていません")
        st.stop()

    tr = get_track(track_id)
    if not tr:
        st.error("曲が見つかりません")
        st.stop()

    album_row = get_album(album_id)
    is_omnibus = bool(album_row[5]) if album_row else False

    st.header(f"🎵 曲情報：{tr[3]}")

    # 上部情報: 曲番号、アーティスト（オムニバスのみ）、曲名、作詞、作曲、編曲
    tp = get_track_people(track_id)
    lyricist = ", ".join([r[2] for r in tp if r[4] == "Lyricist"]) or ""
    composer = ", ".join([r[2] for r in tp if r[4] == "Composer"]) or ""
    arranger = ", ".join([r[2] for r in tp if r[4] == "Arranger"]) or ""
    artist = ", ".join([r[2] for r in tp if r[4] == "Artist"]) or ""

    if is_omnibus:
        col_a, col_b, col_c, col_d, col_e, col_f = st.columns([1,3,6,3,3,3])
        col_a.write(f"**#{tr[2]}**")
        col_b.write(f"**アーティスト**：{artist or '（未登録）'}")
        col_c.write(f"**曲名**：{tr[3]}")
        col_d.write(f"**作詞**：{lyricist}")
        col_e.write(f"**作曲**：{composer}")
        col_f.write(f"**編曲**：{arranger}")
    else:
        col_a, col_b, col_c, col_d, col_e = st.columns([1,6,3,3,3])
        col_a.write(f"**#{tr[2]}**")
        col_b.write(f"**曲名**：{tr[3]}")
        col_c.write(f"**作詞**：{lyricist}")
        col_d.write(f"**作曲**：{composer}")
        col_e.write(f"**編曲**：{arranger}")

    st.markdown("---")

    # 下部: その他の役割（作詞/作曲/編曲/Artist以外）と人物
    st.subheader("その他の役割と人物")
    others = [r for r in tp if r[4] not in ("Lyricist", "Composer", "Arranger", "Artist")]
    if others:
        for o in others:
            role_name = o[4]
            person_name = o[2]
            st.write(f"- {role_name}：{person_name}")
    else:
        st.write("該当する役割と人物はありません")

    st.markdown("---")
    if st.button("前の画面に戻る"):
        st.session_state.view = st.session_state.get("return_view", "album_view")
        st.rerun()

# -----------------------------
# アルバム登録画面
# -----------------------------
elif st.session_state.view == "album_register":
    st.header("📀 アルバム登録")

    # -----------------------------
    # アルバム基本情報
    # -----------------------------
    catalog_no = st.text_input("品番")
    title = st.text_input("アルバム名")

    # アーティスト（people）選択 UI
    st.subheader("アーティスト（人物）")

    people = get_people()  # [(id, name, note)]
    people_names = [p[1] for p in people]

    selected_artist = st.selectbox(
        "既存の人物から選択",
        ["新規入力"] + people_names
    )

    if selected_artist == "新規入力":
        artist_name = st.text_input("新規アーティスト名")
    else:
        artist_name = selected_artist

    # 発売日
    min_date = dt.date(1960, 1, 1)
    max_date = dt.datetime.today().date()

    release_date = st.date_input(
        "発売日",
        value=None,
        min_value=min_date,
        max_value=max_date
    )
    release_date_str = release_date.strftime("%Y-%m-%d") if release_date else ""

    # 発売年
    if release_date:
        year_input = release_date.year
        st.number_input(
            "発売年（release_dateの年を自動設定）",
            value=release_date.year,
            min_value=1960,
            max_value=dt.datetime.today().year,
            disabled=True
        )
    else:
        year_text = st.text_input("発売年", value="", placeholder="未設定（空欄可）")
        if year_text.strip() == "":
            year_input = None
        else:
            # accept only digits, optionally whitespace
            if year_text.strip().isdigit():
                year_input = int(year_text.strip())
                if year_input < 1960 or year_input > dt.datetime.today().year:
                    st.error(f"発売年は1960から{dt.datetime.today().year}の間で指定してください")
            else:
                st.error("発売年は数字で入力してください（空欄可）")
                year_input = None

    album_type_options = ["アルバム", "シングル"]
    album_type = st.selectbox("種別", album_type_options)

    note = st.text_area("備考")
    album_kana = st.text_input("かな")
    if album_kana and not is_full_width_kana(album_kana):
        st.error("かなは全角かなで入力してください")

    original_release_date = st.date_input(
        "初回オリジナル版発売日",
        value=None,
        min_value=min_date,
        max_value=max_date
    )
    original_release_date_str = original_release_date.strftime("%Y-%m-%d") if original_release_date else ""

    omnibus_flag = st.checkbox("オムニバスアルバム（複数人物）")

    st.markdown("---")

    # -----------------------------
    # 登録処理
    # -----------------------------
    if st.button("登録"):
        if not title:
            st.error("アルバム名は必須です")
        elif album_kana and not is_full_width_kana(album_kana):
            st.error("かなは全角かなで入力してください")
        else:
            # アーティストが新規なら people に追加
            if artist_name:
                person_row = get_person_by_name(artist_name)
                if not person_row:
                    add_person(artist_name, "")
                    person_row = get_person_by_name(artist_name)
                artist_person_id = person_row[0]
            else:
                artist_person_id = None

            # アルバム登録
            album_id = add_album(
                catalog_no,
                title,
                year_input,
                release_date_str,
                album_type,
                note,
                omnibus_flag,
                album_kana.strip(),
                original_release_date_str
            )

            # アーティストを album_people に紐づけ（役割は Artist）
            if artist_person_id:
                role_row = get_role_by_name("Artist")
                if role_row:
                    role_id = role_row[0]
                    add_album_people(
                        album_id,
                        artist_person_id,
                        role_id,
                        "",
                        ""
                    )

            st.success("アルバムを登録しました")
            st.session_state.view = "album_list"
            #st.rerun()

    if st.button("一覧に戻る"):
        st.session_state.view = "album_list"
        st.rerun()

# -----------------------------
# アルバム編集画面
# -----------------------------
elif st.session_state.view == "album_edit":

    st.header("📀 アルバム編集")

    # アルバム選択
    albums = get_albums()
    album_dict = {f"{a[2]}": a[0] for a in albums}
    
    if len(album_dict) == 0:
        st.warning("アルバムがありません")
        st.stop()
    
    #selected_label = st.selectbox("編集するアルバム", list(album_dict.keys()))
    #st.session_state.current_album_id = album_dict[selected_label]
    album = get_album(st.session_state.current_album_id)
    
    # -----------------------------
    # アルバム情報編集
    # -----------------------------
    st.subheader("アルバム情報")
    
    catalog_no = st.text_input("品番", value=album[1] or "")
    title = st.text_input("アルバム名", value=album[2] or "")

    # 現在のアーティストを取得
    ap_list = get_album_people(album[0])
    current_artist_person_id = None
    for ap in ap_list:
        if ap[4] == "Artist":  # role_name
            current_artist_person_id = ap[1]  # person_id
            break
    # 人物一覧
    people = get_people()  # [(id, name, note)]
    if not people:
        st.warning("人物が未登録です。まず人物一覧から人物を登録してください。")
        if st.button("一覧に戻る"):
            st.session_state.view = "album_list"
            st.rerun()
        st.stop()

    people_names = [p[1] for p in people]
    people_ids = [p[0] for p in people]
    # 現在のアーティストの index
    if current_artist_person_id in people_ids:
        default_index = people_ids.index(current_artist_person_id)
    else:
        default_index = 0
    default_index = min(max(default_index, 0), len(people_names) - 1)
    # アーティスト選択（新規入力なし）
    selected_artist_name = st.selectbox(
        "アーティスト",
        people_names,
        index=default_index
    )
    if selected_artist_name in people_names:
        selected_artist_id = people_ids[people_names.index(selected_artist_name)]
    else:
        selected_artist_id = people_ids[0]
    
    # 発売日
    release_date_val = None
    if album[4]:
        try:
            release_date_val = dt.datetime.strptime(album[4], "%Y-%m-%d").date()
        except ValueError:
            release_date_val = None
    
    min_date = dt.date(1960, 1, 1)
    max_date = dt.datetime.today().date()
    release_date = st.date_input(
        "発売日",
        value=release_date_val,
        min_value=min_date,
        max_value=max_date
    )
    release_date_str = release_date.strftime("%Y-%m-%d") if release_date else ""
    
    # 発売年
    if release_date:
        year = release_date.year
        year_input = release_date.year
        st.number_input("発売年（release_dateの年を自動設定）", value=year, min_value=1960, max_value=dt.datetime.today().year, disabled=True)
    else:
        # allow NULL: show text input (blank means NULL)
        default_year_val = album[3]
        default_year_text = ""
        if default_year_val is not None:
            try:
                default_year_text = str(int(default_year_val))
            except (TypeError, ValueError):
                default_year_text = ""

        year_text = st.text_input("発売年", value=default_year_text, placeholder="未設定（空欄可）")
        if year_text.strip() == "":
            year_input = None
        else:
            if year_text.strip().isdigit():
                year_input = int(year_text.strip())
                if year_input < 1960 or year_input > dt.datetime.today().year:
                    st.error(f"発売年は1960から{dt.datetime.today().year}の間で指定してください")
            else:
                st.error("発売年は数字で入力してください（空欄可）")
                year_input = None
    
    album_type_options = ["アルバム", "シングル"]
    current_type = album[6] if album[6] in album_type_options else album_type_options[0]
    album_type = st.selectbox("種別", album_type_options, index=album_type_options.index(current_type))
    
    note = st.text_area("備考", value=album[7] or "")
    album_kana = st.text_input("かな", value=album[8] or "")
    if album_kana and not is_full_width_kana(album_kana):
        st.error("かなは全角かなで入力してください")

    original_release_date_value = None
    if album[9]:
        try:
            original_release_date_value = dt.datetime.strptime(album[9], "%Y-%m-%d").date()
        except ValueError:
            original_release_date_value = None

    original_release_date = st.date_input(
        "初回オリジナル版発売日",
        value=original_release_date_value,
        min_value=min_date,
        max_value=max_date
    )
    original_release_date_str = original_release_date.strftime("%Y-%m-%d") if original_release_date else ""
    
    omnibus_flag = st.checkbox("オムニバスアルバム（複数人物）", value=bool(album[5]))
    
    if st.button("アルバム情報を更新"):
        if album_kana and not is_full_width_kana(album_kana):
            st.error("かなは全角かなで入力してください")
        else:
            # アルバム情報更新
            update_album(album[0], catalog_no, title, year_input, release_date_str, album_type, note, omnibus_flag, album_kana.strip(), original_release_date_str)

        # アーティスト更新処理
        # 1. 既存の Artist を削除
        for ap in ap_list:
            if ap[4] == "Artist":
                delete_album_people(ap[0])  # ap.id

        # 2. 新しい Artist を追加
        role_row = get_role_by_name("Artist")
        role_id = role_row[0]
        added = add_album_people(album[0], selected_artist_id, role_id, "", "")
        if added:
            st.success("アルバム情報を更新しました（アーティストを更新しました）")
        else:
            st.warning("アーティストの更新が適用されませんでした（既に同じ情報があるか、DB 側で挿入が抑制されました）。ログを確認してください。")
        #st.rerun()

    st.markdown("---")

    if st.button("一覧に戻る"):
        st.session_state.view = "album_list"
        st.rerun()

    # -----------------------------
    # アルバム × 人物 × 役割 一覧
    # -----------------------------
    others = [ap for ap in ap_list if ap[4] != "Artist"]

    st.subheader("人物一覧（役割別）")

    if others:
        for ap in others:
            ap_id = ap[0]
            person_name = ap[2]
            role_name = ap[4]
            instrument = ap[5]
            ap_note = ap[6]

            cols = st.columns([3, 3, 3, 3, 2])
            cols[0].write(role_name)
            cols[1].write(person_name)
            cols[2].write(instrument or "")
            cols[3].write(ap_note or "")

            if cols[4].button("削除", key=f"delete_ap_{ap_id}"):
                delete_album_people(ap_id)

                col1, col2 = st.columns([3,1])
                col1.success(f"{person_name}を削除しました")
                if col2.button("🔄 更新"):
                    st.session_state.need_refresh = False
                    st.rerun()

    else:
        st.write("人物が登録されていません")
    
    st.markdown("---")
    
    # -----------------------------
    # 人物追加 UI（新構造）
    # -----------------------------
    st.subheader("人物を追加")
    
    # 役割選択
    roles = get_roles()  # [(id, role_name)]
    role_names = [r[1] for r in roles]
    selected_role = st.selectbox("役割", role_names)
    role_id = [r[0] for r in roles if r[1] == selected_role][0]
    
    # 人物選択（既存＋新規）
    people = get_people()  # [(id, name, note)]
    people_names = [p[1] for p in people]
    
    selected_person = st.selectbox("人物（既存）", ["新規入力"] + people_names)
    
    if selected_person == "新規入力":
        person_name = st.text_input("新規人物名")
        person_note = st.text_input("備考（所属バンドなど）")
    else:
        person_name = selected_person
        person_note = ""
    
    # 楽器（Performer の場合のみ）
    instrument = ""
    if selected_role == "Performer":
        instrument = st.text_input("楽器")
    
    ap_note_input = st.text_input("備考（アルバムでの役割など）")
    
    # -----------------------------
    # 人物追加処理
    # -----------------------------
    if st.button("人物をアルバムに追加"):
        if person_name:
    
            # 新規人物なら登録
            if selected_person == "新規入力":
                existing = get_person_by_name(person_name)
                if existing:
                    st.error("既に登録済です")
                    st.stop()  # 追加処理を止める
                else:
                    add_person(person_name, person_note)
                    person_id = get_people()[-1][0]
            else:
                person_id = [p[0] for p in people if p[1] == person_name][0]
    
            # アルバム × 人物 × 役割 に追加
            add_album_people(album[0], person_id, role_id, instrument, ap_note_input)

            col1, col2 = st.columns([3,1])
            col1.success(f"{person_name}を追加しました")
            if col2.button("🔄 更新"):
                st.session_state.need_refresh = False
                st.rerun()

        else:
            st.error("人物名は必須です")

    # -----------------------------
    # 曲一覧
    # -----------------------------
    st.subheader("曲一覧")

    tracks = get_tracks_by_album(album[0])  # returns ordered by track_no

    if tracks:
        # header
        cols = st.columns([1, 4, 3, 3, 3, 2, 1])
        cols[0].write("#")
        cols[1].write("曲名")
        cols[2].write("作詞")
        cols[3].write("作曲")
        cols[4].write("編曲")
        cols[5].write("演奏時間")
        cols[6].write("")

        for t in tracks:
            track_id = t[0]
            track_no = t[2]
            track_title = t[3]
            duration = t[4] or ""

            # fetch related people for roles
            tp = get_track_people(track_id)
            lyricist = ", ".join([r[2] for r in tp if r[4] == "Lyricist"]) or ""
            composer = ", ".join([r[2] for r in tp if r[4] == "Composer"]) or ""
            arranger = ", ".join([r[2] for r in tp if r[4] == "Arranger"]) or ""

            cols = st.columns([1, 4, 3, 3, 3, 2, 1])
            cols[0].write(str(track_no))
            # 曲名はリンク化をやめ、プレーンテキストで表示
            cols[1].write(track_title or "(無題)")
            cols[2].write(lyricist)
            cols[3].write(composer)
            cols[4].write(arranger)
            cols[5].write(duration)

    else:
        st.write("曲が登録されていません")

    st.markdown("---")

    # 曲編集ボタン（曲の編集画面へ遷移）
    if st.button("曲編集"):
        st.session_state.current_track_id = None
        st.session_state.current_album_id = album[0]
        st.session_state.view = "track_register"
        st.rerun()

# -----------------------------
# 曲登録画面
# -----------------------------
elif st.session_state.view == "track_register":
    st.header("🎵 曲編集")

    album_id = st.session_state.current_album_id

    # Top:曲一覧 (track_no, title clickable, lyricist, composer, arranger, duration, delete)
    st.subheader("曲一覧")
    tracks = get_tracks_by_album(album_id)
    if tracks:
        cols = st.columns([1, 4, 3, 3, 3, 2, 1])
        cols[0].write("#")
        cols[1].write("曲名")
        cols[2].write("作詞")
        cols[3].write("作曲")
        cols[4].write("編曲")
        cols[5].write("演奏時間")
        cols[6].write("")

        for t in tracks:
            track_id = t[0]
            track_no = t[2]
            track_title = t[3]
            duration = t[4] or ""
            tp = get_track_people(track_id)
            lyricist = ", ".join([r[2] for r in tp if r[4] == "Lyricist"]) or ""
            composer = ", ".join([r[2] for r in tp if r[4] == "Composer"]) or ""
            arranger = ", ".join([r[2] for r in tp if r[4] == "Arranger"]) or ""

            row_cols = st.columns([1, 4, 3, 3, 3, 2, 1])
            row_cols[0].write(str(track_no))
            # 曲名 clickable: load into edit area
            if row_cols[1].button(track_title or "(無題)", key=f"select_track_{track_id}"):
                st.session_state.current_track_id = track_id
                st.rerun()
            row_cols[2].write(lyricist)
            row_cols[3].write(composer)
            row_cols[4].write(arranger)
            row_cols[5].write(duration)

            if row_cols[6].button("削除", key=f"delete_track_{track_id}"):
                delete_track(track_id)
                st.success(f"曲 {track_title} を削除しました")
                st.rerun()
    else:
        st.write("曲が登録されていません")

    st.markdown("---")

    # Bottom: 編集エリア
    st.subheader("曲編集")
    selected_id = st.session_state.get("current_track_id")

    # defaults
    if selected_id:
        tr = get_track(selected_id)
        default_track_no = tr[2] or 1
        default_title = tr[3] or ""
        default_track_kana = tr[6] or ""
        default_duration = tr[4] or ""
        default_original_release_date = None
        if tr[7]:
            try:
                default_original_release_date = dt.datetime.strptime(tr[7], "%Y-%m-%d").date()
            except ValueError:
                default_original_release_date = None
    else:
        default_track_no = 1
        default_title = ""
        default_track_kana = ""
        default_duration = ""
        default_original_release_date = None

    # アルバムがオムニバスの場合はトラックに対してアーティストを指定できる
    album_row = get_album(album_id)
    is_omnibus = bool(album_row[5]) if album_row else False
    artist_person_name = ""
    artist_person_id = None
    if selected_id:
        # try to find existing Artist for this track
        tp_existing = get_track_people(selected_id)
        for r in tp_existing:
            if r[4] == "Artist":
                artist_person_id = r[1]
                artist_person_name = r[2]
                break

    if is_omnibus:
        st.subheader("トラックアーティスト（オムニバス時のみ）")
        people = get_people()
        people_names = [p[1] for p in people]
        if artist_person_name:
            # preselect existing if present
            if artist_person_name in people_names:
                default_artist_index = people_names.index(artist_person_name) + 1
            else:
                default_artist_index = 0
        else:
            default_artist_index = 0
        selected_track_artist = st.selectbox("アーティスト", ["新規入力"] + people_names, index=default_artist_index)
        if selected_track_artist == "新規入力":
            track_artist_new = st.text_input("新規アーティスト名（トラック）", value=(artist_person_name or ""))
            track_artist_note = st.text_input("アーティスト備考（任意）", value="")
            track_artist_name_input = track_artist_new.strip()
        else:
            track_artist_name_input = selected_track_artist
            track_artist_note = ""

    track_no = st.number_input("曲番号", min_value=1, value=default_track_no)
    title = st.text_input("曲名", value=default_title)
    track_kana = st.text_input("曲名かな", value=default_track_kana)
    if track_kana and not is_full_width_kana(track_kana):
        st.error("かなは全角かなで入力してください")
    duration = st.text_input("演奏時間（例：4:32）", value=default_duration)
    original_release_date = st.date_input(
        "初回オリジナル版発売日",
        value=default_original_release_date,
        min_value=dt.date(1960, 1, 1),
        max_value=dt.datetime.today().date()
    )
    original_release_date_str = original_release_date.strftime("%Y-%m-%d") if original_release_date else ""

    col_save, col_add, col_back = st.columns([1,1,1])
    if col_save.button("更新"):
        if not selected_id:
            st.error("曲を選択してください")
        elif track_kana and not is_full_width_kana(track_kana):
            st.error("かなは全角かなで入力してください")
        else:
            # note is kept empty since edit area no longer exposes it
            update_track(selected_id, track_no, title, duration, "", track_kana.strip(), original_release_date_str)

            # handle track-level Artist for omnibus albums
            album_row_local = get_album(album_id)
            is_omnibus_local = bool(album_row_local[5]) if album_row_local else False
            if is_omnibus_local:
                role_row = get_role_by_name("Artist")
                role_id = role_row[0] if role_row else add_role("Artist")
                # determine provided artist
                provided_name = None
                if 'track_artist_name_input' in locals() or 'track_artist_name_input' in globals():
                    provided_name = track_artist_name_input.strip() if track_artist_name_input else ""
                # remove existing if empty
                conn = connect_db()
                c = conn.cursor()
                c.execute("SELECT id, person_id FROM track_people WHERE track_id = ? AND role_id = ?", (selected_id, role_id))
                row = c.fetchone()
                if provided_name:
                    # ensure person exists
                    person_row = get_person_by_name(provided_name)
                    if not person_row:
                        add_person(provided_name, track_artist_note if 'track_artist_note' in locals() else "")
                        person_row = get_person_by_name(provided_name)
                    pid = person_row[0]
                    if row:
                        # update person_id
                        c.execute("UPDATE track_people SET person_id = ? WHERE id = ?", (pid, row[0]))
                    else:
                        add_track_people(selected_id, pid, role_id, "", "")
                else:
                    if row:
                        c.execute("DELETE FROM track_people WHERE id = ?", (row[0],))
                conn.commit()
                conn.close()

            st.success("曲情報を更新しました")
            # clear selection and reset form
            st.session_state.current_track_id = None
            st.rerun()

    if col_add.button("曲を追加"):
        # Add a new track using current form values
        if not title:
            st.error("曲名は必須です")
        elif track_kana and not is_full_width_kana(track_kana):
            st.error("かなは全角かなで入力してください")
        else:
            new_tid = add_track(album_id, track_no, title, duration, "", track_kana.strip(), original_release_date_str)

            # handle track-level Artist for omnibus albums
            album_row_local = get_album(album_id)
            is_omnibus_local = bool(album_row_local[5]) if album_row_local else False
            if is_omnibus_local:
                role_row = get_role_by_name("Artist")
                role_id = role_row[0] if role_row else add_role("Artist")
                provided_name = None
                if 'track_artist_name_input' in locals() or 'track_artist_name_input' in globals():
                    provided_name = track_artist_name_input.strip() if track_artist_name_input else ""
                if provided_name:
                    person_row = get_person_by_name(provided_name)
                    if not person_row:
                        add_person(provided_name, track_artist_note if 'track_artist_note' in locals() else "")
                        person_row = get_person_by_name(provided_name)
                    pid = person_row[0]
                    add_track_people(new_tid, pid, role_id, "", "")

            st.success("曲を追加しました")
            # refresh list and clear selection/form
            st.session_state.current_track_id = None
            st.rerun()

    if col_back.button("アルバム編集画面に戻る"):
        st.session_state.view = "album_edit"
        st.rerun()

    # -----------------------------
    # 曲に紐づく人物編集（手入力、重複/類似チェック）
    # -----------------------------
    # -----------------------------
    # 上部に人物一覧を表示（曲情報入力エリアと人物編集エリアの間）
    # -----------------------------
    st.markdown("---")
    st.subheader("人物一覧（役割別）")
    selected_track_id = selected_id
    if selected_track_id:
        tp_list_top = get_track_people(selected_track_id)
        if tp_list_top:
            for tp in tp_list_top:
                tp_id = tp[0]
                person_name = tp[2]
                role_name = tp[4]
                instrument = tp[5]
                tp_note = tp[6]

                cols = st.columns([2, 2, 2, 3, 2])
                # 役割をクリックすると下の編集エリアで編集できる
                if cols[0].button(role_name, key=f"tr_select_tp_role_{tp_id}"):
                    st.session_state.current_tp_id = tp_id
                    st.rerun()
                cols[1].write(person_name)
                cols[2].write(instrument or "")
                cols[3].write(tp_note or "")

                if cols[4].button("削除", key=f"tr_delete_tp_{tp_id}"):
                    delete_track_people(tp_id)
                    if st.session_state.get("current_tp_id") == tp_id:
                        st.session_state.current_tp_id = None
                    st.success("削除しました")
                    st.rerun()
        else:
            st.write("人物が登録されていません")

        # 編集フォーム（一覧で役割をクリックするとここに表示される）
        current_tp = st.session_state.get("current_tp_id")
        if current_tp:
            sel = next((x for x in tp_list_top if x[0] == current_tp), None)
            if sel:
                sel_tp_id = sel[0]
                sel_person_id = sel[1]
                sel_person_name = sel[2]
                sel_role_id = sel[3]
                sel_role_name = sel[4]
                sel_instrument = sel[5] or ""
                sel_tp_note = sel[6] or ""

                st.subheader("人物編集（選択中）")
                roles = get_roles()
                role_names = [r[1] for r in roles]
                role_index = 0
                for i, r in enumerate(roles):
                    if r[0] == sel_role_id:
                        role_index = i
                        break
                selected_role_edit = st.selectbox("役割を編集", role_names + ["新規入力"], index=role_index, key=f"tr_edit_role_select_{sel_tp_id}")
                if selected_role_edit == "新規入力":
                    new_role_name = st.text_input("新規役割名", key=f"tr_new_role_name_{sel_tp_id}")
                    edit_role_name = new_role_name.strip()
                else:
                    edit_role_name = selected_role_edit

                people = get_people()
                people_names = [p[1] for p in people]
                person_index = next((i for i, p in enumerate(people) if p[0] == sel_person_id), None)
                default_person_index = (person_index + 1) if person_index is not None else 0
                selected_person_edit = st.selectbox("人物を編集", ["新規入力"] + people_names, index=default_person_index, key=f"tr_edit_person_select_{sel_tp_id}")
                if selected_person_edit == "新規入力":
                    new_person_name = st.text_input("新規人物名", value=sel_person_name, key=f"tr_new_person_name_{sel_tp_id}")
                    new_person_note = st.text_input("新規人物備考", key=f"tr_new_person_note_{sel_tp_id}")
                    edit_person_name = new_person_name.strip()
                else:
                    edit_person_name = selected_person_edit
                    new_person_note = ""

                edit_instrument = st.text_input("楽器", value=sel_instrument, key=f"tr_edit_instrument_{sel_tp_id}")
                edit_tp_note = st.text_input("備考", value=sel_tp_note, key=f"tr_edit_tp_note_{sel_tp_id}")

                col_upd, col_del, col_cancel = st.columns([1,1,1])
                if col_upd.button("更新", key=f"tr_update_tp_{sel_tp_id}"):
                    # ensure role exists
                    if selected_role_edit == "新規入力":
                        if not edit_role_name:
                            st.error("役割名を入力してください")
                        else:
                            rid = add_role(edit_role_name)
                    else:
                        rrow = get_role_by_name(edit_role_name)
                        rid = rrow[0] if rrow else add_role(edit_role_name)

                    # ensure person exists or create
                    if selected_person_edit == "新規入力":
                        if not edit_person_name:
                            st.error("人物名を入力してください")
                        else:
                            existing = get_person_by_name(edit_person_name)
                            if existing:
                                pid = existing[0]
                            else:
                                add_person(edit_person_name, new_person_note or "")
                                pid = get_person_by_name(edit_person_name)[0]
                    else:
                        pid = get_person_by_name(edit_person_name)[0]

                    update_track_people(sel_tp_id, pid, rid, edit_instrument, edit_tp_note)
                    st.success("更新しました")
                    st.session_state.current_tp_id = None
                    st.rerun()

                if col_del.button("削除（編集画面から）", key=f"tr_delete_tp_from_edit_{sel_tp_id}"):
                    delete_track_people(sel_tp_id)
                    st.session_state.current_tp_id = None
                    st.success("削除しました")
                    st.rerun()

                if col_cancel.button("キャンセル", key=f"tr_cancel_edit_tp_{sel_tp_id}"):
                    st.session_state.current_tp_id = None
                    st.rerun()
            else:
                st.warning("選択中の人物が見つかりませんでした。")
                st.session_state.current_tp_id = None
    else:
        st.info("上部の曲一覧から編集する曲を選択してください")

    # -----------------------------
    # 人物編集（手入力、重複/類似チェック）
    # -----------------------------
    roles = get_roles()  # [(id, role_name)]
    role_names = [r[1] for r in roles]
    selected_role = st.selectbox("役割（既存から選択／新規入力可）", role_names + ["新規入力"], key="person_role_select")
    if selected_role == "新規入力":
        role_name_input = st.text_input("新規役割名（例：Guitar, Keyboard, Drums, Chorus）")
        role_name_text = role_name_input.strip()
    else:
        role_name_text = selected_role

    # 名前の手入力（複数: カンマ/、/; 改行で区切る）
    raw_names = st.text_input("人物名（複数登録する場合はカンマや、で区切る）", value="")
    person_note = st.text_input("人物備考（新規登録時に使われます）", value="")
    # 楽器フィールドは廃止し、役割（role_name）が楽器/担当を表す
    tp_note_input = st.text_input("備考（曲での役割など）", value="")

    def find_similar_people(name):
        name_n = name.strip().lower()
        if not name_n:
            return []
        candidates = []
        for p in get_people():
            pn = (p[1] or "").lower()
            if not pn:
                continue
            if name_n in pn or pn in name_n:
                candidates.append(p)
            else:
                # prefix match first 4 chars
                if len(name_n) >= 4 and pn.startswith(name_n[:4]):
                    candidates.append(p)
                elif len(pn) >= 4 and name_n.startswith(pn[:4]):
                    candidates.append(p)
        return candidates

    import re as _re
    pending = st.session_state.get("pending_person_adds", None)

    if st.button("検査して追加（重複・類似を検出）"):
        names = [n.strip() for n in _re.split('[,、;\\n]+', raw_names) if n.strip()]
        if not names:
            st.error("人物名を入力してください")
        elif not selected_id:
            st.error("まず上部の曲一覧から編集する曲を選択してください")
        elif selected_role == "新規入力" and not role_name_text:
            st.error("新規の役割名を入力してください")
        else:
            pending_list = []
            has_similar = False
            for n in names:
                existing = get_person_by_name(n)
                if existing:
                    pending_list.append({"name": n, "person_id": existing[0], "existing": True, "similar": []})
                else:
                    sims = find_similar_people(n)
                    if sims:
                        has_similar = True
                        pending_list.append({"name": n, "person_id": None, "existing": False, "similar": sims})
                    else:
                        pending_list.append({"name": n, "person_id": None, "existing": False, "similar": []})
            st.session_state.pending_person_adds = {
                "items": pending_list,
                "role_name": role_name_text,
                "tp_note": tp_note_input,
                "person_note": person_note,
                "track_id": selected_id
            }
            if has_similar:
                st.warning("類似する既存人物が見つかりました。以下を確認してください。\n類似がない場合は「新規登録して追加」を押してください。")
            else:
                st.success("類似は見つかりませんでした。新規登録して追加します。")

    pending = st.session_state.get("pending_person_adds", None)
    if pending:
        st.subheader("検出結果 / 追加候補")
        for idx, it in enumerate(pending["items"]):
            st.write(f"・{it['name']}")
            if it["existing"]:
                st.write(f"  - 既存: id={it['person_id']}")
            if it["similar"]:
                st.write("  - 類似候補:")
                for s in it["similar"]:
                    st.write(f"    - {s[1]} (id={s[0]})")
        col_yes, col_no = st.columns([1,1])
        if col_no.button("キャンセル"):
            del st.session_state.pending_person_adds
            st.experimental_rerun()
        if col_yes.button("新規登録して追加（確認）"):
            # perform additions
            items = st.session_state.pending_person_adds["items"]
            role_name = st.session_state.pending_person_adds["role_name"]
            tp_note = st.session_state.pending_person_adds["tp_note"]
            person_note = st.session_state.pending_person_adds["person_note"]
            track_id = st.session_state.pending_person_adds["track_id"]

            # ensure role exists (create if necessary)
            role_row = get_role_by_name(role_name)
            if role_row:
                role_id = role_row[0]
            else:
                role_id = add_role(role_name)

            for it in items:
                name = it["name"]
                if it["existing"] and it.get("person_id"):
                    pid = it["person_id"]
                else:
                    # create person
                    add_person(name, person_note or "")
                    pid = get_person_by_name(name)[0]
                # avoid duplicate association
                conn = connect_db()
                c = conn.cursor()
                c.execute("""
                    SELECT id FROM track_people WHERE track_id = ? AND person_id = ? AND role_id = ?
                """, (track_id, pid, role_id))
                if not c.fetchone():
                    add_track_people(track_id, pid, role_id, "", tp_note or "")
                conn.close()

            del st.session_state.pending_person_adds
            st.success("人物を追加しました")
            st.rerun()

# -----------------------------
# 曲編集画面
# -----------------------------
elif st.session_state.view == "track_edit":
    st.header("🎵 曲編集")

    album_id = st.session_state.current_album_id
    track_id = st.session_state.current_track_id

    # 既存曲 or 新規曲
    if track_id:
        track = get_track(track_id)
        track_no = st.number_input("曲番号", value=track[2] or 1, min_value=1)
        title = st.text_input("曲名", value=track[3] or "")
        duration = st.text_input("演奏時間", value=track[4] or "")
        note = st.text_area("備考", value=track[5] or "")
        track_kana = st.text_input("かな", value=track[6] or "")
        if track_kana and not is_full_width_kana(track_kana):
            st.error("かなは全角かなで入力してください")

        original_release_date_value = None
        if track[7]:
            try:
                original_release_date_value = dt.datetime.strptime(track[7], "%Y-%m-%d").date()
            except ValueError:
                original_release_date_value = None

        original_release_date = st.date_input(
            "初回オリジナル版発売日",
            value=original_release_date_value,
            min_value=dt.date(1960, 1, 1),
            max_value=dt.datetime.today().date()
        )
        original_release_date_str = original_release_date.strftime("%Y-%m-%d") if original_release_date else ""
    else:
        track_no = st.number_input("曲番号", min_value=1, value=1)
        title = st.text_input("曲名")
        duration = st.text_input("演奏時間")
        note = st.text_area("備考")
        track_kana = st.text_input("かな")
        if track_kana and not is_full_width_kana(track_kana):
            st.error("かなは全角かなで入力してください")

        original_release_date = st.date_input(
            "初回オリジナル版発売日",
            value=None,
            min_value=dt.date(1960, 1, 1),
            max_value=dt.datetime.today().date()
        )
        original_release_date_str = original_release_date.strftime("%Y-%m-%d") if original_release_date else ""

    # -----------------------------
    # 曲情報の保存
    # -----------------------------
    if st.button("曲を保存"):
        if not title:
            st.error("曲名は必須です")
        elif track_kana and not is_full_width_kana(track_kana):
            st.error("かなは全角かなで入力してください")
        else:
            if track_id:
                update_track(track_id, track_no, title, duration, note, track_kana.strip(), original_release_date_str)
            else:
                add_track(album_id, track_no, title, duration, note, track_kana.strip(), original_release_date_str)
                track_id = get_tracks_by_album(album_id)[-1][0]
                st.session_state.current_track_id = track_id

            st.success("曲情報を保存しました")
            st.rerun()

    st.markdown("---")

    # -----------------------------
    # 曲 × 人物 × 役割 の一覧
    # -----------------------------
    st.subheader("人物一覧（役割別）")

    tp_list = get_track_people(track_id)

    if tp_list:
        for tp in tp_list:
            tp_id = tp[0]
            person_name = tp[2]
            role_name = tp[4]
            instrument = tp[5]
            tp_note = tp[6]

            cols = st.columns([2, 2, 2, 3, 2])
            # 役割名をクリックすると編集用フォームを開く
            if cols[0].button(role_name, key=f"edit_tp_role_{tp_id}"):
                st.session_state.current_tp_id = tp_id
                st.rerun()
            cols[1].write(person_name)
            cols[2].write(instrument or "")
            cols[3].write(tp_note or "")

            if cols[4].button("削除", key=f"delete_tp_{tp_id}"):
                delete_track_people(tp_id)
                # 編集中に削除した場合は選択を解除
                if st.session_state.get("current_tp_id") == tp_id:
                    st.session_state.current_tp_id = None
                st.success("削除しました")
                st.rerun()
    else:
        st.write("人物が登録されていません")

    # 編集フォーム（上部の一覧で役割をクリックするとここに表示される）
    current_tp = st.session_state.get("current_tp_id")
    if current_tp:
        # find the selected tp record from the fetched list
        selected_tp = next((x for x in tp_list if x[0] == current_tp), None)
        if selected_tp:
            sel_tp_id = selected_tp[0]
            sel_person_id = selected_tp[1]
            sel_person_name = selected_tp[2]
            sel_role_id = selected_tp[3]
            sel_role_name = selected_tp[4]
            sel_instrument = selected_tp[5] or ""
            sel_tp_note = selected_tp[6] or ""

            st.subheader("人物編集（選択中）")
            # 役割編集
            roles = get_roles()
            role_names = [r[1] for r in roles]
            # find index of current role
            role_index = 0
            for i, r in enumerate(roles):
                if r[0] == sel_role_id:
                    role_index = i
                    break
            selected_role_edit = st.selectbox("役割を編集", role_names + ["新規入力"], index=role_index, key=f"edit_role_select_{sel_tp_id}")
            if selected_role_edit == "新規入力":
                new_role_name = st.text_input("新規役割名", key=f"new_role_name_{sel_tp_id}")
                edit_role_name = new_role_name.strip()
            else:
                edit_role_name = selected_role_edit

            # 人物編集（既存選択 or 新規）
            people = get_people()
            people_names = [p[1] for p in people]
            # determine index of current person in people list
            person_index = next((i for i, p in enumerate(people) if p[0] == sel_person_id), None)
            default_person_index = (person_index + 1) if person_index is not None else 0
            selected_person_edit = st.selectbox("人物を編集", ["新規入力"] + people_names, index=default_person_index, key=f"edit_person_select_{sel_tp_id}")
            if selected_person_edit == "新規入力":
                new_person_name = st.text_input("新規人物名", value=sel_person_name, key=f"new_person_name_{sel_tp_id}")
                new_person_note = st.text_input("新規人物備考", key=f"new_person_note_{sel_tp_id}")
                edit_person_name = new_person_name.strip()
            else:
                edit_person_name = selected_person_edit
                new_person_note = ""

            edit_instrument = st.text_input("楽器", value=sel_instrument, key=f"edit_instrument_{sel_tp_id}")
            edit_tp_note = st.text_input("備考", value=sel_tp_note, key=f"edit_tp_note_{sel_tp_id}")

            col_upd, col_del, col_cancel = st.columns([1,1,1])
            if col_upd.button("更新", key=f"update_tp_{sel_tp_id}"):
                # ensure role exists
                if selected_role_edit == "新規入力":
                    if not edit_role_name:
                        st.error("役割名を入力してください")
                    else:
                        rid = add_role(edit_role_name)
                else:
                    rrow = get_role_by_name(edit_role_name)
                    rid = rrow[0] if rrow else add_role(edit_role_name)

                # ensure person exists or create
                if selected_person_edit == "新規入力":
                    if not edit_person_name:
                        st.error("人物名を入力してください")
                    else:
                        existing = get_person_by_name(edit_person_name)
                        if existing:
                            pid = existing[0]
                        else:
                            add_person(edit_person_name, new_person_note or "")
                            pid = get_person_by_name(edit_person_name)[0]
                else:
                    pid = get_person_by_name(edit_person_name)[0]

                # update the track_people row
                update_track_people(sel_tp_id, pid, rid, edit_instrument, edit_tp_note)
                st.success("更新しました")
                st.session_state.current_tp_id = None
                st.rerun()

            if col_del.button("削除（編集画面から）", key=f"delete_tp_from_edit_{sel_tp_id}"):
                delete_track_people(sel_tp_id)
                st.session_state.current_tp_id = None
                st.success("削除しました")
                st.rerun()

            if col_cancel.button("キャンセル", key=f"cancel_edit_tp_{sel_tp_id}"):
                st.session_state.current_tp_id = None
                st.rerun()
        else:
            st.warning("選択中の人物が見つかりませんでした。")
            st.session_state.current_tp_id = None

    st.markdown("---")

    # -----------------------------
    # 人物追加 UI（新構造）
    # -----------------------------
    st.subheader("人物を追加")

    # 役割選択
    roles = get_roles()  # [(id, role_name)]
    role_names = [r[1] for r in roles]
    selected_role = st.selectbox("役割", role_names)
    role_id = [r[0] for r in roles if r[1] == selected_role][0]

    # 人物選択（既存＋新規）
    people = get_people()  # [(id, name, note)]
    people_names = [p[1] for p in people]

    selected_person = st.selectbox("人物（既存）", ["新規入力"] + people_names)

    if selected_person == "新規入力":
        person_name = st.text_input("新規人物名")
        person_note = st.text_input("備考（所属バンドなど）")
    else:
        person_name = selected_person
        person_note = ""

    # 楽器（Performer の場合のみ）
    instrument = ""
    if selected_role == "Performer":
        instrument = st.text_input("楽器")

    tp_note_input = st.text_input("備考（曲での役割など）")

    # -----------------------------
    # 人物追加処理
    # -----------------------------
    if st.button("人物を曲に追加"):
        if person_name:

            # 新規人物なら登録
            if selected_person == "新規入力":
                existing = get_person_by_name(person_name)
                if existing:
                    st.error("既に登録済です")
                    st.stop()  # 追加処理を止める
                else:
                    add_person(person_name, person_note)
                    person_id = get_people()[-1][0]
            else:
                person_id = [p[0] for p in people if p[1] == person_name][0]

            # 曲 × 人物 × 役割 に追加
            add_track_people(track_id, person_id, role_id, instrument, tp_note_input)

            st.success("追加しました")
            st.rerun()
        else:
            st.error("人物名は必須です")
