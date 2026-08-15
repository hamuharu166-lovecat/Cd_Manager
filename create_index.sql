-- アルバム名や曲名のあいまい検索・一致検索用
CREATE INDEX idx_albums_title ON albums(title);
CREATE INDEX idx_tracks_title ON tracks(title);
CREATE INDEX idx_people_name ON people(name);

-- JOINや中間テーブルの結合用
CREATE INDEX idx_tracks_album_id ON tracks(album_id);
CREATE INDEX idx_album_person_role ON album_people(album_id, person_id);