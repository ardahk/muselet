"""Local SQLite storage for long-term memory."""

from __future__ import annotations

import os
import re
import sqlite3
import threading
import time
from pathlib import Path


DEFAULT_DB = Path.home() / "Library/Application Support/Muselet/memory.db"
TYPES = {"person", "preference", "fact", "correction", "episode", "workflow"}
IMPORTANCE = {
    "correction": 1.0,
    "person": 1.0,
    "preference": 0.8,
    "fact": 0.7,
    "workflow": 0.6,
    "episode": 0.4,
}
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "for", "from",
    "how", "i", "in", "is", "it", "me", "my", "of", "on", "or", "that",
    "the", "this", "to", "was", "we", "what", "when", "where", "which",
    "who", "with", "you",
}
_TOKEN = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _tokens(text: str) -> list[str]:
    return [token.casefold() for token in _TOKEN.findall(str(text or ""))
            if len(token) >= 2 and token.casefold() not in _STOPWORDS]


class MemoryStore:
    def __init__(self, path=None, *, fts: bool = True):
        configured = os.environ.get("MUSELET_MEMORY_DB")
        self.path = (Path(path) if path is not None and
                     str(path) != ":memory:" else path)
        if self.path is None:
            self.path = Path(configured) if configured else DEFAULT_DB
        if self.path != ":memory:":
            self.path = Path(self.path).expanduser()
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(self.path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY,
                type TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                importance REAL NOT NULL,
                created REAL NOT NULL,
                used REAL,
                superseded REAL
            )
        """)
        self._db.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS memories_live_key
            ON memories(type, key) WHERE superseded IS NULL
        """)
        self._db.commit()
        self._fts_enabled = False
        if fts:
            try:
                self._db.executescript("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                        key, value, content='memories', content_rowid='id'
                    );
                    INSERT INTO memories_fts(memories_fts) VALUES ('rebuild');
                    CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                        INSERT INTO memories_fts(rowid, key, value)
                        VALUES (new.id, new.key, new.value);
                    END;
                    CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                        INSERT INTO memories_fts(memories_fts, rowid, key, value)
                        VALUES ('delete', old.id, old.key, old.value);
                    END;
                    CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                        INSERT INTO memories_fts(memories_fts, rowid, key, value)
                        VALUES ('delete', old.id, old.key, old.value);
                        INSERT INTO memories_fts(rowid, key, value)
                        VALUES (new.id, new.key, new.value);
                    END;
                """)
                self._db.commit()
                self._fts_enabled = True
            except sqlite3.OperationalError:
                self._db.rollback()

    def close(self):
        with self._lock:
            self._db.close()

    @staticmethod
    def _row(row) -> dict:
        return dict(row) if row is not None else {}

    def upsert(self, type: str, key: str, value: str,
               now: float | None = None) -> dict:
        type = str(type).casefold().strip()
        key = " ".join(str(key).casefold().split())
        value = " ".join(str(value).split())
        if type not in TYPES:
            raise ValueError(f"unsupported memory type: {type}")
        if not key or not value:
            raise ValueError("memory key and value must be non-empty")
        from .policy import allowed_value
        if not allowed_value(key) or not allowed_value(value):
            raise ValueError("memory content rejected by privacy policy")
        stamp = float(time.time() if now is None else now)
        with self._lock, self._db:
            current = self._db.execute(
                "SELECT * FROM memories WHERE type=? AND key=? "
                "AND superseded IS NULL",
                (type, key)).fetchone()
            if current and current["value"] == value:
                row = self._row(current)
                row["action"] = "NOOP"
                return row
            action = "ADD"
            if current:
                action = "UPDATE"
                self._db.execute(
                    "UPDATE memories SET superseded=? WHERE id=?",
                    (stamp, current["id"]))
            cursor = self._db.execute(
                "INSERT INTO memories(type, key, value, importance, created) "
                "VALUES (?, ?, ?, ?, ?)",
                (type, key, value, IMPORTANCE[type], stamp))
            row = self._db.execute(
                "SELECT * FROM memories WHERE id=?", (cursor.lastrowid,)
            ).fetchone()
            result = self._row(row)
            result["action"] = action
            return result

    def delete(self, id: int) -> dict | None:
        with self._lock, self._db:
            row = self._db.execute(
                "SELECT * FROM memories WHERE id=?", (int(id),)
            ).fetchone()
            if row is None:
                return None
            result = self._row(row)
            self._db.execute("DELETE FROM memories WHERE id=?", (int(id),))
            return result

    def clear(self) -> int:
        with self._lock, self._db:
            count = self._db.execute(
                "SELECT count(*) FROM memories").fetchone()[0]
            self._db.execute("DELETE FROM memories")
            return int(count)

    def list(self, type: str | None = None, limit: int = 100) -> list[dict]:
        sql = "SELECT * FROM memories WHERE superseded IS NULL"
        params: list = []
        if type is not None:
            sql += " AND type=?"
            params.append(str(type).casefold())
        sql += " ORDER BY created DESC, id DESC LIMIT ?"
        params.append(max(0, int(limit)))
        with self._lock:
            rows = self._db.execute(sql, params).fetchall()
        return [self._row(row) for row in rows]

    def forget(self, query: str, k: int = 3,
               now: float | None = None) -> list[dict]:
        return self.search(query, k=k, now=now)

    def search(self, text: str, k: int = 3,
               now: float | None = None) -> list[dict]:
        tokens = _tokens(text)
        if not tokens or k <= 0:
            return []
        stamp = float(time.time() if now is None else now)
        candidates = self._search_fts(tokens) if self._fts_enabled else \
            self._search_like(tokens)
        if not candidates:
            return []
        max_relevance = max((max(0.0, item[1]) for item in candidates),
                            default=0.0)
        scored = []
        for row, raw_relevance in candidates:
            relevance = raw_relevance / max_relevance if max_relevance else 1.0
            age_hours = max(0.0, stamp - float(row["used"] or row["created"])) / 3600
            score = (float(row["importance"]) *
                     (0.995 ** age_hours) * relevance)
            scored.append((score, self._row(row)))
        scored.sort(key=lambda item: (-item[0], item[1]["id"]))
        selected = [row for _, row in scored[:min(int(k), 20)]]
        while selected and sum(
                len(line.split()) * 1.3 for line in render(selected)) > 150:
            selected.pop()
        if not selected:
            return []
        with self._lock, self._db:
            self._db.executemany(
                "UPDATE memories SET used=? WHERE id=?",
                [(stamp, row["id"]) for row in selected])
        for row in selected:
            row["used"] = stamp
        return selected

    def _search_fts(self, tokens: list[str]) -> list[tuple[sqlite3.Row, float]]:
        query = " OR ".join(f'"{token.replace(chr(34), chr(34) * 2)}"'
                            for token in tokens)
        try:
            with self._lock:
                rows = self._db.execute(
                    "SELECT memories.*, bm25(memories_fts) AS rank "
                    "FROM memories_fts JOIN memories "
                    "ON memories.id=memories_fts.rowid "
                    "WHERE memories_fts MATCH ? AND memories.superseded IS NULL "
                    "ORDER BY rank LIMIT 20", (query,)).fetchall()
        except sqlite3.OperationalError:
            self._fts_enabled = False
            return self._search_like(tokens)
        return [(row, max(0.0, -float(row["rank"]))) for row in rows]

    def _search_like(self, tokens: list[str]) -> list[tuple[sqlite3.Row, float]]:
        conditions = " OR ".join(
            "(lower(key) LIKE ? OR lower(value) LIKE ?)" for _ in tokens)
        params = [part for token in tokens for part in
                  (f"%{token}%", f"%{token}%")]
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM memories WHERE superseded IS NULL AND (" +
                conditions + ") ORDER BY created DESC LIMIT 20",
                params).fetchall()
        result = []
        for row in rows:
            haystack = f'{row["key"]} {row["value"]}'.casefold()
            relevance = sum(token in haystack for token in tokens)
            result.append((row, float(relevance)))
        return result


def render(rows: list[dict]) -> list[str]:
    return [
        f"Memory: {row['type']} {row['key']} = {row['value']}"[:80]
        for row in rows
    ]
