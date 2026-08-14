import csv
import io
import sqlite3
import urllib.request
from urllib.error import URLError

DB_NAME = "music.db"
CSV_URL = "https://docs.google.com/spreadsheets/d/1dp-T7LHlR34Af-eLgm-vR6M9ojeziTf6-zbsCljViZU/export?format=csv&gid=592093507"

# まずは少数件だけをテストしたい場合はここを小さくします。
# 例: LIMIT = 5
LIMIT = None

conn = sqlite3.connect(DB_NAME)
cur = conn.cursor()


def clear_import_tables():
    # SQLite does not support TRUNCATE, so delete rows in dependency-safe order.
    tables = ["track_people", "album_people", "tracks", "albums", "people", "roles"]
    for table in tables:
        cur.execute(f"DELETE FROM {table}")
        cur.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'sqlite_sequence'")
        if cur.fetchone():
            cur.execute("DELETE FROM sqlite_sequence WHERE name = ?", (table,))
    conn.commit()


def get_or_create_person(name):
    name = (name or "").strip()
    if not name:
        return None
    cur.execute("SELECT id FROM people WHERE name = ?", (name,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute("INSERT INTO people (name, note) VALUES (?, ?)", (name, ""))
    return cur.lastrowid


def get_or_create_role(role_name):
    role_name = (role_name or "").strip()
    if not role_name:
        return None
    cur.execute("SELECT id FROM roles WHERE role_name = ?", (role_name,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute("INSERT INTO roles (role_name) VALUES (?)", (role_name,))
    return cur.lastrowid


def normalize_album_type(value):
    v = (value or "").strip()
    v_upper = v.upper()
    if v_upper in ("AL", "ALBUM", "アルバム"):
        return "アルバム"
    if v_upper in ("SG", "SINGLE", "シングル"):
        return "シングル"
    return "アルバム"


def split_people(value):
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    items = []
    for chunk in text.replace(";", ",").replace("、", ",").split(","):
        name = chunk.strip()
        if name:
            items.append(name)
    return items


def upsert_track_people(track_id, person_name, role_name):
    person_id = get_or_create_person(person_name)
    role_id = get_or_create_role(role_name)
    if person_id is None or role_id is None:
        return

    cur.execute(
        "SELECT id FROM track_people WHERE track_id = ? AND person_id = ? AND role_id = ?",
        (track_id, person_id, role_id),
    )
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO track_people (track_id, person_id, role_id, instrument, note) VALUES (?, ?, ?, ?, ?)",
            (track_id, person_id, role_id, "", ""),
        )


def upsert_album_people(album_id, person_name, role_name):
    person_id = get_or_create_person(person_name)
    role_id = get_or_create_role(role_name)
    if person_id is None or role_id is None:
        return

    cur.execute(
        "SELECT id FROM album_people WHERE album_id = ? AND person_id = ? AND role_id = ?",
        (album_id, person_id, role_id),
    )
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO album_people (album_id, person_id, role_id, instrument, note) VALUES (?, ?, ?, ?, ?)",
            (album_id, person_id, role_id, "", ""),
        )


# 既存データを一括削除してから再importする
clear_import_tables()

# CSV を取得
try:
    with urllib.request.urlopen(CSV_URL) as resp:
        raw = resp.read()
except URLError as e:
    raise RuntimeError(f"CSV取得失敗: {e}")

text = raw.decode("utf-8-sig")
reader = csv.DictReader(io.StringIO(text))

album_cache = {}
count = 0

for row in reader:
    if LIMIT is not None and count >= LIMIT:
        break

    album_title = (row.get("メディアタイトル") or "").strip()
    if not album_title:
        continue

    media_artist = (row.get("メディアアーティスト") or "").strip()
    album_key = (album_title, media_artist)
    if album_key not in album_cache:
        release_date = (row.get("発売日") or "").strip()
        album_type = normalize_album_type(row.get("AL/SG"))
        note = (row.get("備考") or "").strip()
        original_release_date = (row.get("オリジナル発売日") or "").strip()

        cur.execute(
            """
            INSERT INTO albums (
                catalog_no, title, year, release_date, omnibus_flag,
                album_type, note, album_kana, original_release_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("", album_title, None, release_date, 0, album_type, note, "", original_release_date),
        )
        album_id = cur.lastrowid
        album_cache[album_key] = album_id

        if media_artist:
            for person_name in split_people(media_artist):
                upsert_album_people(album_id, person_name, "Artist")

    album_id = album_cache[album_key]

    track_no_raw = row.get("曲順") or row.get("順２") or "1"
    try:
        track_no = int(track_no_raw)
    except ValueError:
        track_no = 1

    track_title = (row.get("曲名") or "").strip()
    if not track_title:
        continue

    duration = (row.get("時間") or "").strip()
    track_original_release_date = (row.get("オリジナル発売日") or "").strip()

    cur.execute(
        "SELECT id FROM tracks WHERE album_id = ? AND track_no = ? AND title = ?",
        (album_id, track_no, track_title),
    )
    existing = cur.fetchone()
    if existing:
        track_id = existing[0]
    else:
        cur.execute(
            """
            INSERT INTO tracks (
                album_id, track_no, title, duration, note, track_kana, original_release_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (album_id, track_no, track_title, duration, "", "", track_original_release_date),
        )
        track_id = cur.lastrowid

    for col_name, role_name in [
        ("作詞者", "Lyricist"),
        ("作曲者", "Composer"),
        ("編曲者", "Arranger"),
        ("演奏者", "Performer"),
        ("コーラスアレンジ", "Chorus Arrangement"),
        ("ストレングスアレンジ", "Strength Arrangement"),
        ("その他アレンジ", "Other Arrangement"),
    ]:
        value = row.get(col_name) or ""
        for person in split_people(value):
            upsert_track_people(track_id, person, role_name)

    track_artist = (row.get("曲アーティスト") or "").strip()
    if track_artist:
        for person in split_people(track_artist):
            upsert_track_people(track_id, person, "Artist")

    count += 1

conn.commit()
print(f"import completed. processed rows={count}")
conn.close()
