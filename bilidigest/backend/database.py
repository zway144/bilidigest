import sqlite3
from pathlib import Path
from config import settings

_CREATE_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    title TEXT DEFAULT '',
    author TEXT DEFAULT '',
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    duration INTEGER DEFAULT 0,
    thumbnail_url TEXT DEFAULT '',
    status TEXT DEFAULT 'pending'
        CHECK(status IN ('pending','downloading','transcribing','extracting_frames','analyzing','ready','partial','failed')),
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    text TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'subtitle'
        CHECK(source IN ('subtitle','whisper'))
);
CREATE INDEX IF NOT EXISTS idx_transcripts_asset ON transcripts(asset_id);
CREATE INDEX IF NOT EXISTS idx_transcripts_time ON transcripts(asset_id, start_time);

CREATE VIRTUAL TABLE IF NOT EXISTS transcripts_fts USING fts5(
    text,
    content='transcripts',
    content_rowid='id',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS transcripts_ai AFTER INSERT ON transcripts BEGIN
    INSERT INTO transcripts_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS transcripts_ad AFTER DELETE ON transcripts BEGIN
    INSERT INTO transcripts_fts(transcripts_fts, rowid, text) VALUES('delete', old.id, old.text);
END;
CREATE TRIGGER IF NOT EXISTS transcripts_au AFTER UPDATE ON transcripts BEGIN
    INSERT INTO transcripts_fts(transcripts_fts, rowid, text) VALUES('delete', old.id, old.text);
    INSERT INTO transcripts_fts(rowid, text) VALUES (new.id, new.text);
END;

CREATE TABLE IF NOT EXISTS keyframes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    timestamp REAL NOT NULL,
    file_path TEXT NOT NULL,
    ocr_text TEXT,
    description TEXT
);
CREATE INDEX IF NOT EXISTS idx_keyframes_asset ON keyframes(asset_id);
CREATE INDEX IF NOT EXISTS idx_keyframes_time ON keyframes(asset_id, timestamp);

CREATE TABLE IF NOT EXISTS structured_knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    knowledge_type TEXT NOT NULL
        CHECK(knowledge_type IN ('arguments','timeline','concepts','conclusions')),
    content TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_knowledge_asset ON structured_knowledge(asset_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_type ON structured_knowledge(asset_id, knowledge_type);

CREATE TABLE IF NOT EXISTS generation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_ids TEXT NOT NULL,
    mode TEXT NOT NULL
        CHECK(mode IN ('summary','cards','xiaohongshu','mindmap')),
    user_prompt TEXT,
    output_content TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""


def get_db() -> sqlite3.Connection:
    db_path = settings.db_path
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrate_db(conn: sqlite3.Connection):
    """数据库迁移：处理 schema 变更"""
    # 迁移1：generation_history.mode 添加 mindmap 支持
    # SQLite 不支持 ALTER CHECK，需要重建表
    try:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='generation_history'"
        ).fetchone()
        if row and 'mindmap' not in row[0]:
            conn.executescript("""
                ALTER TABLE generation_history RENAME TO _generation_history_old;
                CREATE TABLE generation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_ids TEXT NOT NULL,
                    mode TEXT NOT NULL
                        CHECK(mode IN ('summary','cards','xiaohongshu','mindmap')),
                    user_prompt TEXT,
                    output_content TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                INSERT INTO generation_history SELECT * FROM _generation_history_old;
                DROP TABLE _generation_history_old;
            """)
    except Exception:
        pass  # 表不存在或已迁移


def init_db():
    """首次启动时执行建表语句，并清理上次遗留的卡死任务"""
    db_path = settings.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(_CREATE_SQL)
        _migrate_db(conn)
        # 服务重启时，将所有处于处理中状态的资产标记为 failed，防止永久卡死
        processing_states = ('pending', 'downloading', 'transcribing', 'extracting_frames', 'analyzing')
        conn.execute(
            f"UPDATE assets SET status='failed', error_message='服务重启，处理中断，请重新处理', updated_at=CURRENT_TIMESTAMP "
            f"WHERE status IN ({','.join('?' * len(processing_states))})",
            processing_states,
        )
        conn.commit()
    finally:
        conn.close()
