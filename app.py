import re
import streamlit as st
import sqlite3
import datetime as dt

DB_NAME = "music.db"


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
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    def ensure_column(table_name, column_name, column_type):
        columns = c.execute(f"PRAGMA table_info({table_name})").fetchall()
        if not any(col[1] == column_name for col in columns):
            c.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

    # -----------------------------
    # アルバム
    # -----------------------------
    c.execute("""
        CREATE TABLE IF NOT EXISTS albums (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    c.execute("""
        CREATE TABLE IF NOT EXISTS tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    c.execute("""
        CREATE TABLE IF NOT EXISTS people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            note TEXT
        )
    """)

    # -----------------------------
    # 役割（Artist / Composer / Arranger / Lyricist / Performer）
    # -----------------------------
    c.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_name TEXT NOT NULL UNIQUE
        )
    """)

    # 初期役割データを挿入
    default_roles = ["Artist", "Composer", "Arranger", "Lyricist", "Performer"]
    for role in default_roles:
        c.execute("INSERT OR IGNORE INTO roles (role_name) VALUES (?)", (role,))

    # -----------------------------
    # アルバム × 人物 × 役割
    # -----------------------------
    c.execute("""
        CREATE TABLE IF NOT EXISTS album_people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    c.execute("""
        CREATE TABLE IF NOT EXISTS track_people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    conn = sqlite3.connect(DB_NAME)
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
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT id, catalog_no, title, year, release_date, omnibus_flag, album_type, note, album_kana, original_release_date
        FROM albums
        WHERE id = ?
    """, (album_id,))
    result = c.fetchone()
    conn.close()
    return result

def get_albums():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT id, catalog_no, title, year, release_date, omnibus_flag, album_type, note, album_kana, original_release_date
        FROM albums
        ORDER BY year, title
    """)
    result = c.fetchall()
    conn.close()
    return result

def get_albums_by_person(person_id):
    conn = sqlite3.connect(DB_NAME)
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
    conn = sqlite3.connect(DB_NAME)
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
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO tracks (album_id, track_no, title, duration, note, track_kana, original_release_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (album_id, track_no, title, duration, note, track_kana, original_release_date))
    conn.commit()
    conn.close()

def update_track(track_id, track_no, title, duration, note, track_kana="", original_release_date=""):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        UPDATE tracks
        SET track_no=?, title=?, duration=?, note=?, track_kana=?, original_release_date=?
        WHERE id=?
    """, (track_no, title, duration, note, track_kana, original_release_date, track_id))
    conn.commit()
    conn.close()

def get_tracks_by_album(album_id):
    conn = sqlite3.connect(DB_NAME)
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
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT id, album_id, track_no, title, duration, note, track_kana, original_release_date
        FROM tracks
        WHERE id = ?
    """, (track_id,))
    row = c.fetchone()
    conn.close()
    return row

def get_tracks_by_person(person_id):
    conn = sqlite3.connect(DB_NAME)
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
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO track_people (track_id, person_id, role_id, instrument, note)
        VALUES (?, ?, ?, ?, ?)
    """, (track_id, person_id, role_id, instrument, note))
    conn.commit()
    conn.close()

def get_track_people(track_id):
    conn = sqlite3.connect(DB_NAME)
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
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM track_people WHERE id = ?", (tp_id,))
    conn.commit()
    conn.close()

# -----------------------------
# DB 操作（アルバム × 役割 × 人物）
# -----------------------------
def add_album_people(album_id, person_id, role_id, instrument, note):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO album_people (album_id, person_id, role_id, instrument, note)
        VALUES (?, ?, ?, ?, ?)
    """, (album_id, person_id, role_id, instrument, note))
    conn.commit()
    conn.close()

def get_album_people(album_id):
    conn = sqlite3.connect(DB_NAME)
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
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM album_people WHERE id = ?", (ap_id,))
    conn.commit()
    conn.close()

# -----------------------------
# DB 操作（人物）
# -----------------------------
def get_people():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, name, note FROM people ORDER BY name")
    result = c.fetchall()
    conn.close()
    return result

def add_person(name, note):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO people (name, note)
        VALUES (?, ?)
    """, (name, note))
    conn.commit()
    conn.close()

def get_person(person_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, name, note FROM people WHERE id = ?", (person_id,))
    result = c.fetchone()
    conn.close()
    return result

def update_person(person_id, name, note):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        UPDATE people
        SET name = ?, note = ?
        WHERE id = ?
    """, (name, note, person_id))
    conn.commit()
    conn.close()

def get_person_by_name(name):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, name, note FROM people WHERE name = ?", (name,))
    result = c.fetchone()
    conn.close()
    return result

# -----------------------------
# DB 操作（役割）
# -----------------------------
def get_roles():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, role_name FROM roles ORDER BY role_name")
    result = c.fetchall()
    conn.close()
    return result

def get_role_by_name(role_name):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT id, role_name
        FROM roles
        WHERE role_name = ?
    """, (role_name,))
    result = c.fetchone()
    conn.close()
    return result

# -----------------------------
# Streamlit UI
# -----------------------------
st.title("🎵 CD / 曲データ管理アプリ")

init_db()

if "view" not in st.session_state:
    st.session_state.view = "album_list"
if "current_album_id" not in st.session_state:
    st.session_state.current_album_id = None
if "current_track_id" not in st.session_state:
    st.session_state.current_track_id = None
if "current_person_id" not in st.session_state:
    st.session_state.current_person_id = None

menu = st.sidebar.selectbox(
    "メニュー",
    [
        "アルバム一覧",
        "人物一覧"
    ]
)

# -----------------------------
# メニュー分岐
# -----------------------------
if menu == "アルバム一覧":
    if st.session_state.view not in ["album_view", "album_edit", "album_register", "track_edit", "track_register"]:
        st.session_state.view = "album_list"

elif menu == "人物一覧":
    if st.session_state.view != "person_edit":
        st.session_state.view = "people_list"

# -----------------------------
# 人物一覧画面
# -----------------------------
if st.session_state.view == "people_list":
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

    albums = get_albums()

    if not albums:
        st.info("登録されているアルバムはありません。")
    else:
        for a in albums:
            album_id = a[0]
            title = a[2]      # a[2] = title
            year = a[3]       # a[3] = year

            # -----------------------------
            # アーティスト名を取得（新構造）
            # -----------------------------
            ap_list = get_album_people(album_id)

            # role_name が "Artist" の人物を抽出
            artists = [ap[2] for ap in ap_list if ap[4] == "Artist"]
            # ap の構造は get_album_people() による：
            # ap[0] = album_people.id
            # ap[1] = person_id
            # ap[2] = person_name
            # ap[3] = instrument
            # ap[4] = role_name
            # ap[5] = note

            artist_text = ", ".join(artists) if artists else "（アーティスト未登録）"

            col1, col2 = st.columns([3, 2])

            # -----------------------------
            # アルバム名をクリックすると編集画面へ
            # -----------------------------
            if col1.button(title, key=f"album_{album_id}"):
                st.session_state.current_album_id = album_id
                st.session_state.view = "album_view"
                st.rerun()

            col2.write(artist_text)

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
    # 曲一覧表示
    # -----------------------------
    st.subheader("曲一覧")

    tracks = get_tracks_by_album(album_id)
    if tracks:
        for t in tracks:
            st.write(f"{t[2]}. {t[3]}")
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
    # 一覧に戻る
    # -----------------------------
    if st.button("一覧に戻る"):
        st.session_state.view = "album_list"
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
        year_input = st.number_input(
            "発売年（release_dateの年を自動設定）",
            value=release_date.year,
            min_value=1960,
            max_value=dt.datetime.today().year,
            disabled=True
        )
    else:
        year_input = st.number_input(
            "発売年",
            min_value=1960,
            max_value=dt.datetime.today().year,
            value=1960
        )

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
    # アーティスト（people）選択 UI
    # -----------------------------
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
    people_names = [p[1] for p in people]
    people_ids = [p[0] for p in people]
    # 現在のアーティストの index
    if current_artist_person_id in people_ids:
        default_index = people_ids.index(current_artist_person_id)
    else:
        default_index = 0
    # アーティスト選択（新規入力なし）
    selected_artist_name = st.selectbox(
        "アーティスト",
        people_names,
        index=default_index
    )
    selected_artist_id = people_ids[people_names.index(selected_artist_name)]
    
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
        year_input = st.number_input("発売年（release_dateの年を自動設定）", value=year, min_value=1960, max_value=dt.datetime.today().year, disabled=True)
    else:
        default_year = album[3] if album[3] is not None else 1960
        try:
            default_year = int(default_year)
        except (TypeError, ValueError):
            default_year = 1960
        year_input = st.number_input("発売年", min_value=1960, max_value=dt.datetime.today().year, value=default_year)
    
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
        add_album_people(album[0], selected_artist_id, role_id, "", "")

        st.success("アルバム情報を更新しました")
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

    tracks = get_tracks_by_album(album[0])  # [(id, album_id, track_no, title, ...)]

    if tracks:
        for t in tracks:
            track_id = t[0]
            track_no = t[2]
            track_title = t[3]

            # 曲名をクリックすると曲編集画面へ
            if st.button(f"{track_no}. {track_title}", key=f"track_{track_id}"):
                st.session_state.current_track_id = track_id
                st.session_state.view = "track_edit"
                st.rerun()
    else:
        st.write("曲が登録されていません")

    st.markdown("---")

    # 曲追加ボタン
    if st.button("＋ 曲を追加する"):
        st.session_state.view = "track_register"
        st.session_state.current_album_id = album[0]
        st.rerun()

# -----------------------------
# 曲登録画面
# -----------------------------
elif st.session_state.view == "track_register":
    st.header("🎵 曲を追加")

    album_id = st.session_state.current_album_id

    # -----------------------------
    # 曲情報入力
    # -----------------------------
    track_no = st.number_input("曲番号", min_value=1, value=1)
    title = st.text_input("曲名")
    duration = st.text_input("演奏時間（例：4:32）")
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
    # 曲登録処理
    # -----------------------------
    if st.button("登録"):
        if not title:
            st.error("曲名は必須です")
        elif track_kana and not is_full_width_kana(track_kana):
            st.error("かなは全角かなで入力してください")
        else:
            add_track(album_id, track_no, title, duration, note, track_kana.strip(), original_release_date_str)
            st.success("曲を追加しました")
            st.session_state.view = "album_edit"
            #st.rerun()

    if st.button("キャンセル"):
        st.session_state.view = "album_edit"
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
            cols[0].write(role_name)
            cols[1].write(person_name)
            cols[2].write(instrument or "")
            cols[3].write(tp_note or "")

            if cols[4].button("削除", key=f"delete_tp_{tp_id}"):
                delete_track_people(tp_id)
                st.success("削除しました")
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
