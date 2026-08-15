-- 1) 拡張を有効化（既に有効ならスキップ）
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 2) トライグラム GIN インデックス（title, people.name, tracks.title）
CREATE INDEX IF NOT EXISTS idx_albums_title_trgm ON albums USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_people_name_trgm ON people USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_tracks_title_trgm ON tracks USING gin (title gin_trgm_ops);