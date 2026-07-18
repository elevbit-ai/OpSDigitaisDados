"""
SQLite internal database for OpS Digitais Dados.
Author: Joaquim Pedro de Morais Filho
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class User:
    id: int
    full_name: str
    document_id: str
    email: str
    phone: str
    notes: str
    created_at: str
    updated_at: str
    fingerprint_count: int = 0


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name TEXT NOT NULL,
                    document_id TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL DEFAULT '',
                    phone TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS fingerprints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    finger_label TEXT NOT NULL DEFAULT 'indicador_direito',
                    template BLOB NOT NULL,
                    preview_path TEXT NOT NULL DEFAULT '',
                    quality REAL NOT NULL DEFAULT 0,
                    keypoints INTEGER NOT NULL DEFAULT 0,
                    enrolled_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    details TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_fp_user ON fingerprints(user_id);
                CREATE INDEX IF NOT EXISTS idx_users_name ON users(full_name);
                """
            )

    def log(self, action: str, details: str = "") -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO audit_log(action, details, created_at) VALUES (?,?,?)",
                (action, details, utc_now()),
            )

    def add_user(
        self,
        full_name: str,
        document_id: str = "",
        email: str = "",
        phone: str = "",
        notes: str = "",
    ) -> int:
        now = utc_now()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO users(full_name, document_id, email, phone, notes, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?)
                """,
                (full_name.strip(), document_id.strip(), email.strip(), phone.strip(), notes.strip(), now, now),
            )
            user_id = int(cur.lastrowid)
        self.log("user_create", f"id={user_id}; name={full_name}")
        return user_id

    def update_user(
        self,
        user_id: int,
        full_name: str,
        document_id: str = "",
        email: str = "",
        phone: str = "",
        notes: str = "",
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE users
                SET full_name=?, document_id=?, email=?, phone=?, notes=?, updated_at=?
                WHERE id=?
                """,
                (full_name.strip(), document_id.strip(), email.strip(), phone.strip(), notes.strip(), utc_now(), user_id),
            )
        self.log("user_update", f"id={user_id}")

    def delete_user(self, user_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        self.log("user_delete", f"id={user_id}")

    def list_users(self, search: str = "") -> list[User]:
        q = """
            SELECT u.*,
                   (SELECT COUNT(*) FROM fingerprints f WHERE f.user_id = u.id) AS fingerprint_count
            FROM users u
        """
        params: tuple[Any, ...] = ()
        if search.strip():
            q += " WHERE u.full_name LIKE ? OR u.document_id LIKE ? OR u.email LIKE ?"
            like = f"%{search.strip()}%"
            params = (like, like, like)
        q += " ORDER BY u.full_name COLLATE NOCASE"
        with self.connect() as conn:
            rows = conn.execute(q, params).fetchall()
        return [
            User(
                id=int(r["id"]),
                full_name=r["full_name"],
                document_id=r["document_id"],
                email=r["email"],
                phone=r["phone"],
                notes=r["notes"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
                fingerprint_count=int(r["fingerprint_count"]),
            )
            for r in rows
        ]

    def get_user(self, user_id: int) -> Optional[User]:
        users = [u for u in self.list_users() if u.id == user_id]
        return users[0] if users else None

    def add_fingerprint(
        self,
        user_id: int,
        template: bytes,
        finger_label: str,
        preview_path: str,
        quality: float,
        keypoints: int,
    ) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO fingerprints(user_id, finger_label, template, preview_path, quality, keypoints, enrolled_at)
                VALUES (?,?,?,?,?,?,?)
                """,
                (user_id, finger_label, template, preview_path, quality, keypoints, utc_now()),
            )
            fp_id = int(cur.lastrowid)
            conn.execute("UPDATE users SET updated_at=? WHERE id=?", (utc_now(), user_id))
        self.log("fingerprint_enroll", f"user={user_id}; fp={fp_id}; label={finger_label}")
        return fp_id

    def list_fingerprints(self, user_id: Optional[int] = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if user_id is None:
                rows = conn.execute(
                    """
                    SELECT f.*, u.full_name
                    FROM fingerprints f
                    JOIN users u ON u.id = f.user_id
                    ORDER BY f.enrolled_at DESC
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT f.*, u.full_name
                    FROM fingerprints f
                    JOIN users u ON u.id = f.user_id
                    WHERE f.user_id=?
                    ORDER BY f.enrolled_at DESC
                    """,
                    (user_id,),
                ).fetchall()
        return [dict(r) for r in rows]

    def delete_fingerprint(self, fp_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM fingerprints WHERE id=?", (fp_id,))
        self.log("fingerprint_delete", f"fp={fp_id}")

    def all_templates(self) -> list[tuple[int, int, str, bytes]]:
        """Return (fp_id, user_id, full_name, template_blob)."""
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT f.id, f.user_id, u.full_name, f.template
                FROM fingerprints f
                JOIN users u ON u.id = f.user_id
                """
            ).fetchall()
        return [(int(r["id"]), int(r["user_id"]), r["full_name"], r["template"]) for r in rows]

    def stats(self) -> dict[str, int]:
        with self.connect() as conn:
            users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
            fps = conn.execute("SELECT COUNT(*) AS c FROM fingerprints").fetchone()["c"]
            logs = conn.execute("SELECT COUNT(*) AS c FROM audit_log").fetchone()["c"]
        return {"users": int(users), "fingerprints": int(fps), "audit_events": int(logs)}

    def recent_audit(self, limit: int = 30) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
