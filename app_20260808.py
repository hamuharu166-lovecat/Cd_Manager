import streamlit as st
import sqlite3
import datetime as dt

DB_NAME = "music.db"

# -----------------------------
# DB 初期化
# -----------------------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # アルバム
    c.execute("""
        CREATE TABLE IF NOT EXISTS albums (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            artist TEXT,
            year INTEGER,
            release_date TEXT,
            omnibus_flag Boolean default false
        )
    """)

    # 曲
    c.execute("""
        CREATE TABLE IF NOT EXISTS tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            album_id INTEGER,
            title TEXT NOT NULL,
            composer TEXT,
            arranger TEXT,
            lyricist TEXT,
            FOREIGN KEY(album_id) REFERENCES albums(id)
        )
    """)

    # ミュージシャン
    c.execute("""
        CREATE TABLE IF NOT EXISTS musicians (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            note TEXT
        )
    """)

    # 曲 × ミュージシャン × 楽器
    c.execute("""
        CREATE TABLE IF NOT EXISTS track_musicians (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            track_id INTEGER,
            musician_id INTEGER,
            instrument TEXT,
            FOREIGN KEY(track_id) REFERENCES tracks(id),
            FOREIGN KEY(musician_id) REFERENCES musicians(id)
        )
    """)

    conn.commit()
    conn.close()

# -----------------------------
# DB 操作（アルバム）
# -----------------------------
def add_album(title, artist, year, release_date):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO albums (title, artist, year, release_date, omnibus_flag)
        VALUES (?, ?, ?, ?, ?)
    """, (title, artist, year, release_date, False))
    conn.commit()
    conn.close()

def get_albums():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, title, artist, year, release_date, omnibus_flag FROM albums")
    rows = c.fetchall()
    conn.close()
    return rows

# -----------------------------
# DB 操作（曲）
# -----------------------------
def add_track(album_id, title, composer, arranger, lyricist):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO tracks (album_id, title, composer, arranger, lyricist)
        VALUES (?, ?, ?, ?, ?)
    """, (album_id, title, composer, arranger, lyricist))
    conn.commit()
    conn.close()

def get_tracks_by_album(album_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT id, title, composer, arranger, lyricist
        FROM tracks
        WHERE album_id = ?
    """, (album_id,))
    rows = c.fetchall()
    conn.close()
    return rows

# -----------------------------
# DB 操作（ミュージシャン）
# -----------------------------
def add_musician(name, note):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO musicians (name, note) VALUES (?, ?)", (name, note))
    conn.commit()
    conn.close()

def get_musicians():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, name, note FROM musicians")
    rows = c.fetchall()
    conn.close()
    return rows

# -----------------------------
# DB 操作（曲 × ミュージシャン）
# -----------------------------
def add_track_musician(track_id, musician_id, instrument):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO track_musicians (track_id, musician_id, instrument)
        VALUES (?, ?, ?)
    """, (track_id, musician_id, instrument))
    conn.commit()
    conn.close()

def get_track_musicians(track_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT m.name, tm.instrument
        FROM track_musicians tm
        LEFT JOIN musicians m ON tm.musician_id = m.id
        WHERE tm.track_id = ?
    """, (track_id,))
    rows = c.fetchall()
    conn.close()
    return rows

# -----------------------------
# Streamlit UI
# -----------------------------
st.title("🎵 CD / 曲データ管理アプリ")

init_db()

menu = st.sidebar.selectbox(
    "メニュー",
    [
        "アルバム登録",
        "曲登録",
        "ミュージシャン登録",
        "バックミュージシャン追加",
        "一覧表示",
        "アルバム編集",
        "曲編集",
        "ミュージシャン編集"
    ]
)

# -----------------------------
# アルバム登録
# -----------------------------
if menu == "アルバム登録":
    st.header("📀 アルバム登録")

    title = st.text_input("アルバム名")
    artist = st.text_input("アーティスト名")
    omnibus_flag = st.checkbox("オムニバスアルバム（複数アーティスト）")
    if omnibus_flag==True:
        artist = "オムニバス"
        st.text_input
    min_date = dt.date(1960, 1, 1)
    max_date = dt.datetime.today().date()
    release_date = st.date_input("発売日", min_value=min_date, max_value=max_date, value=None)
    release_date_str = release_date.strftime("%Y-%m-%d") if release_date else ""

    if release_date:
        year = release_date.year
        st.number_input("発売年（release_dateの年を自動設定）", value=year, min_value=1960, max_value=dt.datetime.today().year, disabled=True)
    else:
        year = st.number_input("発売年", min_value=1960, max_value=dt.datetime.today().year, step=1)

    if st.button("登録"):
        if title:
            add_album(title, artist, year, release_date_str)
            st.success("登録しました")
        else:
            st.error("アルバム名は必須です")

# -----------------------------
# 曲登録
# -----------------------------
elif menu == "曲登録":
    st.header("🎵 曲登録")

    albums = get_albums()
    album_dict = {f"{a[1]}（{a[2]}）": a[0] for a in albums}

    if len(album_dict) == 0:
        st.warning("先にアルバムを登録してください")
    else:
        album_name = st.selectbox("アルバム", list(album_dict.keys()))
        album_id = album_dict[album_name]

        title = st.text_input("曲名")
        composer = st.text_input("作曲")
        arranger = st.text_input("編曲")
        lyricist = st.text_input("作詞")

        if st.button("登録"):
            if title:
                add_track(album_id, title, composer, arranger, lyricist)
                st.success("登録しました")
            else:
                st.error("曲名は必須です")

# -----------------------------
# ミュージシャン登録
# -----------------------------
elif menu == "ミュージシャン登録":
    st.header("👤 ミュージシャン登録")

    name = st.text_input("名前")
    note = st.text_input("備考（所属バンドなど）")

    if st.button("登録"):
        if name:
            add_musician(name, note)
            st.success("登録しました")
        else:
            st.error("名前は必須です")

# -----------------------------
# バックミュージシャン追加
# -----------------------------
elif menu == "バックミュージシャン追加":
    st.header("🎸 バックミュージシャン追加")

    albums = get_albums()
    album_dict = {f"{a[1]}（{a[2]}）": a[0] for a in albums}

    if len(album_dict) == 0:
        st.warning("先にアルバムを登録してください")
    else:
        album_name = st.selectbox("アルバム", list(album_dict.keys()))
        album_id = album_dict[album_name]

        tracks = get_tracks_by_album(album_id)
        track_dict = {t[1]: t[0] for t in tracks}

        musicians = get_musicians()
        musician_dict = {m[1]: m[0] for m in musicians}

        if len(track_dict) == 0 or len(musician_dict) == 0:
            st.warning("曲とミュージシャンを先に登録してください")
        else:
            track_name = st.selectbox("曲", list(track_dict.keys()))
            track_id = track_dict[track_name]

            musician_name = st.selectbox("ミュージシャン", list(musician_dict.keys()))
            musician_id = musician_dict[musician_name]

            instrument = st.text_input("担当楽器（例：ギター、ベース、ドラム）")

            if st.button("追加"):
                add_track_musician(track_id, musician_id, instrument)
                st.success("追加しました")

# -----------------------------
# 一覧表示
# -----------------------------
elif menu == "一覧表示":
    st.header("📚 アルバム一覧（曲一覧付き）")

    albums = get_albums()

    for a in albums:
        album_id = a[0]
        st.markdown(f"## 📀 {a[1]}（{a[2]}）")
        st.write(f"- 発売年：{a[3]}")
        st.write(f"- 発売日：{a[4] if a[4] else '不明'}")

        tracks = get_tracks_by_album(album_id)

        if tracks:
            st.write("### 🎵 曲一覧")
            for t in tracks:
                st.markdown(f"#### {t[1]}")
                st.write(f"- 作曲：{t[2]}")
                st.write(f"- 編曲：{t[3]}")
                st.write(f"- 作詞：{t[4]}")

                musicians = get_track_musicians(t[0])
                if musicians:
                    st.write("##### 🎸 バックミュージシャン")
                    for m in musicians:
                        st.write(f"- {m[0]}（{m[1]}）")
                else:
                    st.write("バックミュージシャンなし")
        else:
            st.write("曲が登録されていません")

        st.markdown("---")

# -----------------------------
# アルバム編集
# -----------------------------
elif menu == "アルバム編集":
    st.header("📀 アルバム編集")

    albums = get_albums()
    album_dict = {f"{a[1]}（{a[2]}）": a for a in albums}

    if len(album_dict) == 0:
        st.warning("アルバムがありません")
    else:
        selected = st.selectbox("編集するアルバム", list(album_dict.keys()))
        album = album_dict[selected]

        new_title = st.text_input("アルバム名", value=album[1])
        new_artist = st.text_input("アーティスト名", value=album[2])
        new_year = st.number_input("発売年", min_value=1960, max_value=2100, value=album[3])

        release_date = st.date_input(
            "発売日（任意）",
            value=None if not album[4] else dt.datetime.strptime(album[4], "%Y-%m-%d")
        )
        release_date_str = release_date.strftime("%Y-%m-%d") if release_date else ""

        if st.button("更新"):
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("""
                UPDATE albums
                SET title=?, artist=?, year=?, release_date=?
                WHERE id=?
            """, (new_title, new_artist, new_year, release_date_str, album[0]))
            conn.commit()
            conn.close()
            st.success("更新しました")

# -----------------------------
# 曲編集
# -----------------------------
elif menu == "曲編集":
    st.header("🎵 曲編集")

    albums = get_albums()
    album_dict = {f"{a[1]}（{a[2]}）": a[0] for a in albums}

    if len(album_dict) == 0:
        st.warning("アルバムがありません")
    else:
        album_name = st.selectbox("アルバムを選択", list(album_dict.keys()))
        album_id = album_dict[album_name]

        tracks = get_tracks_by_album(album_id)
        track_dict = {t[1]: t for t in tracks}

        if len(track_dict) == 0:
            st.warning("このアルバムには曲がありません")
        else:
            selected = st.selectbox("編集する曲", list(track_dict.keys()))
            track = track_dict[selected]

            new_title = st.text_input("曲名", value=track[1])
            new_composer = st.text_input("作曲", value=track[2])
            new_arranger = st.text_input("編曲", value=track[3])
            new_lyricist = st.text_input("作詞", value=track[4])

            if st.button("更新"):
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                c.execute("""
                    UPDATE tracks
                    SET title=?, composer=?, arranger=?, lyricist=?
                    WHERE id=?
                """, (new_title, new_composer, new_arranger, new_lyricist, track[0]))
                conn.commit()
                conn.close()
                st.success("更新しました")

# -----------------------------
# ミュージシャン編集
# -----------------------------
elif menu == "ミュージシャン編集":
    st.header("👤 ミュージシャン編集")

    musicians = get_musicians()
    musician_dict = {m[1]: m for m in musicians}

    if len(musician_dict) == 0:
        st.warning("ミュージシャンが登録されていません")
    else:
        selected = st.selectbox("編集するミュージシャン", list(musician_dict.keys()))
        musician = musician_dict[selected]

        new_name = st.text_input("名前", value=musician[1])
        new_note = st.text_input("備考", value=musician[2])

        if st.button("更新"):
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("""
                UPDATE musicians
                SET name=?, note=?
                WHERE id=?
            """, (new_name, new_note, musician[0]))
            conn.commit()
            conn.close()
            st.success("更新しました")
