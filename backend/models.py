from __future__ import annotations
import sqlite3
from typing import Optional


# ── Users ─────────────────────────────────────────────────────────────────────

def create_user(conn: sqlite3.Connection, email: str, password_hash: str, display_name: str) -> dict:
    cur = conn.execute(
        "INSERT INTO users (email, password_hash, display_name) VALUES (?, ?, ?)",
        (email, password_hash, display_name),
    )
    return get_user_by_id(conn, cur.lastrowid)


def get_user_by_email(conn: sqlite3.Connection, email: str) -> Optional[dict]:
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return dict(row) if row else None


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> Optional[dict]:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


# ── Stories ────────────────────────────────────────────────────────────────────

def create_story(conn: sqlite3.Connection, title: str, created_by: int) -> dict:
    cur = conn.execute(
        "INSERT INTO stories (title, created_by) VALUES (?, ?)",
        (title, created_by),
    )
    story_id = cur.lastrowid
    # Creator is automatically a contributor
    conn.execute(
        "INSERT OR IGNORE INTO story_contributors (story_id, user_id) VALUES (?, ?)",
        (story_id, created_by),
    )
    return get_story_by_id(conn, story_id, created_by)


def get_story_by_id(conn: sqlite3.Connection, story_id: int, viewer_id: int) -> Optional[dict]:
    row = conn.execute("SELECT * FROM stories WHERE id = ?", (story_id,)).fetchone()
    if not row:
        return None
    story = dict(row)
    story["contributors"] = get_story_contributors(conn, story_id)
    story["commit_count"] = conn.execute(
        "SELECT COUNT(*) FROM commits WHERE story_id = ?", (story_id,)
    ).fetchone()[0]
    latest_commit = conn.execute(
        "SELECT id, created_at, author_id FROM commits WHERE story_id = ? ORDER BY id DESC LIMIT 1",
        (story_id,),
    ).fetchone()
    story["latest_commit_id"] = latest_commit["id"] if latest_commit else None
    story["latest_commit_at"] = latest_commit["created_at"] if latest_commit else story["created_at"]
    story["latest_content"] = get_latest_content(conn, story_id)
    return story


def get_stories_for_user(conn: sqlite3.Connection, user_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT DISTINCT s.*
        FROM stories s
        JOIN story_contributors sc ON sc.story_id = s.id
        WHERE sc.user_id = ?
        ORDER BY s.created_at DESC
        """,
        (user_id,),
    ).fetchall()
    return [get_story_by_id(conn, r["id"], user_id) for r in rows]


def delete_story(conn: sqlite3.Connection, story_id: int):
    conn.execute("DELETE FROM stories WHERE id = ?", (story_id,))


def update_story_title(conn: sqlite3.Connection, story_id: int, title: str):
    conn.execute("UPDATE stories SET title = ? WHERE id = ?", (title, story_id))


# ── Contributors ───────────────────────────────────────────────────────────────

def get_story_contributors(conn: sqlite3.Connection, story_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT u.id, u.display_name, u.email, sc.added_at
        FROM story_contributors sc
        JOIN users u ON u.id = sc.user_id
        WHERE sc.story_id = ?
        ORDER BY sc.added_at
        """,
        (story_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def add_contributor(conn: sqlite3.Connection, story_id: int, user_id: int):
    conn.execute(
        "INSERT OR IGNORE INTO story_contributors (story_id, user_id) VALUES (?, ?)",
        (story_id, user_id),
    )


def remove_contributor(conn: sqlite3.Connection, story_id: int, user_id: int):
    conn.execute(
        "DELETE FROM story_contributors WHERE story_id = ? AND user_id = ?",
        (story_id, user_id),
    )


def is_contributor(conn: sqlite3.Connection, story_id: int, user_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM story_contributors WHERE story_id = ? AND user_id = ?",
        (story_id, user_id),
    ).fetchone()
    return row is not None


# ── Commits ────────────────────────────────────────────────────────────────────

def get_latest_content(conn: sqlite3.Connection, story_id: int) -> str:
    row = conn.execute(
        "SELECT content FROM commits WHERE story_id = ? ORDER BY id DESC LIMIT 1",
        (story_id,),
    ).fetchone()
    return row["content"] if row else ""


def create_commit(conn: sqlite3.Connection, story_id: int, author_id: int, content: str) -> dict:
    cur = conn.execute(
        "INSERT INTO commits (story_id, author_id, content) VALUES (?, ?, ?)",
        (story_id, author_id, content),
    )
    row = conn.execute("SELECT * FROM commits WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def get_commits(conn: sqlite3.Connection, story_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT c.*, u.display_name as author_name
        FROM commits c
        JOIN users u ON u.id = c.author_id
        WHERE c.story_id = ?
        ORDER BY c.id DESC
        """,
        (story_id,),
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["preview"] = d["content"][:80]
        result.append(d)
    return result


def get_latest_commit_id(conn: sqlite3.Connection, story_id: int) -> Optional[int]:
    row = conn.execute(
        "SELECT id FROM commits WHERE story_id = ? ORDER BY id DESC LIMIT 1",
        (story_id,),
    ).fetchone()
    return row["id"] if row else None


# ── Edit Locks ─────────────────────────────────────────────────────────────────

def acquire_lock(conn: sqlite3.Connection, story_id: int, user_id: int):
    conn.execute(
        """
        INSERT INTO edit_locks (story_id, user_id, locked_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(story_id) DO UPDATE SET user_id = excluded.user_id, locked_at = excluded.locked_at
        """,
        (story_id, user_id),
    )


def release_lock(conn: sqlite3.Connection, story_id: int, user_id: int):
    conn.execute(
        "DELETE FROM edit_locks WHERE story_id = ? AND user_id = ?",
        (story_id, user_id),
    )


def get_lock(conn: sqlite3.Connection, story_id: int) -> Optional[dict]:
    row = conn.execute(
        """
        SELECT el.*, u.display_name as holder_name
        FROM edit_locks el
        JOIN users u ON u.id = el.user_id
        WHERE el.story_id = ?
        """,
        (story_id,),
    ).fetchone()
    return dict(row) if row else None
