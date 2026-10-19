
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "knowledge.db"

ALLOWED_STATUSES = {"pending", "approved", "rejected", "all"}


def initialize_review_queue() -> None:
    """Create the review table without modifying existing tables."""
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS expert_review_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                approved_answer TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def create_review_task(question: str, reason: str) -> dict:
    """Create a pending task, avoiding duplicate pending questions."""
    initialize_review_queue()

    question = question.strip()
    if not question:
        raise ValueError("Question cannot be empty.")

    reason = reason.strip() or "No reason provided."
    now = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row

        existing = connection.execute(
            """
            SELECT id, question, reason, status, approved_answer,
                   created_at, updated_at
            FROM expert_review_tasks
            WHERE status = 'pending'
              AND LOWER(TRIM(question)) = LOWER(TRIM(?))
            ORDER BY id DESC
            LIMIT 1
            """,
            (question,),
        ).fetchone()

        if existing:
            return dict(existing)

        cursor = connection.execute(
            """
            INSERT INTO expert_review_tasks (
                question, reason, status, created_at, updated_at
            )
            VALUES (?, ?, 'pending', ?, ?)
            """,
            (question, reason, now, now),
        )

        row = connection.execute(
            """
            SELECT id, question, reason, status, approved_answer,
                   created_at, updated_at
            FROM expert_review_tasks
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

        return dict(row)


def get_approved_answer(question: str) -> dict | None:
    """Return an answer approved for this exact normalized question."""
    initialize_review_queue()

    normalized_question = " ".join(question.casefold().split())
    if not normalized_question:
        return None

    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, question, approved_answer, updated_at
            FROM expert_review_tasks
            WHERE status = 'approved'
              AND approved_answer IS NOT NULL
              AND TRIM(approved_answer) != ''
            ORDER BY updated_at DESC, id DESC
            """
        ).fetchall()

    for row in rows:
        saved_question = " ".join(row["question"].casefold().split())
        if saved_question == normalized_question:
            return dict(row)

    return None


def list_review_tasks(status: str = "pending") -> list[dict]:
    """List review tasks filtered by status, or all tasks."""
    initialize_review_queue()

    if status not in ALLOWED_STATUSES:
        raise ValueError(
            "Status must be pending, approved, rejected, or all."
        )

    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row

        if status == "all":
            rows = connection.execute(
                """
                SELECT id, question, reason, status, approved_answer,
                       created_at, updated_at
                FROM expert_review_tasks
                ORDER BY id DESC
                """
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT id, question, reason, status, approved_answer,
                       created_at, updated_at
                FROM expert_review_tasks
                WHERE status = ?
                ORDER BY id DESC
                """,
                (status,),
            ).fetchall()

    return [dict(row) for row in rows]


def approve_review_task(task_id: int, approved_answer: str) -> dict:
    """Approve a pending task and save the expert's answer."""
    initialize_review_queue()

    if task_id < 1:
        raise ValueError("Task ID must be a positive integer.")

    approved_answer = approved_answer.strip()
    if not approved_answer:
        raise ValueError("Approved answer cannot be empty.")

    now = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        cursor = connection.execute(
            """
            UPDATE expert_review_tasks
            SET status = 'approved',
                approved_answer = ?,
                updated_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (approved_answer, now, task_id),
        )

        if cursor.rowcount == 0:
            existing = connection.execute(
                "SELECT id, status FROM expert_review_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()

            if existing is None:
                raise ValueError(f"Review task {task_id} was not found.")

            raise ValueError(
                f"Review task {task_id} is already {existing['status']}."
            )

        row = connection.execute(
            """
            SELECT id, question, reason, status, approved_answer,
                   created_at, updated_at
            FROM expert_review_tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()

        return dict(row)


def reject_review_task(task_id: int, reason: str = "") -> dict:
    """Reject a pending task and optionally record the reason."""
    initialize_review_queue()

    if task_id < 1:
        raise ValueError("Task ID must be a positive integer.")

    now = datetime.now(timezone.utc).isoformat()
    reason = reason.strip()

    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row

        if reason:
            cursor = connection.execute(
                """
                UPDATE expert_review_tasks
                SET status = 'rejected',
                    reason = reason || ' | Rejection: ' || ?,
                    updated_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (reason, now, task_id),
            )
        else:
            cursor = connection.execute(
                """
                UPDATE expert_review_tasks
                SET status = 'rejected',
                    updated_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (now, task_id),
            )

        if cursor.rowcount == 0:
            existing = connection.execute(
                "SELECT id, status FROM expert_review_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()

            if existing is None:
                raise ValueError(f"Review task {task_id} was not found.")

            raise ValueError(
                f"Review task {task_id} is already {existing['status']}."
            )

        row = connection.execute(
            """
            SELECT id, question, reason, status, approved_answer,
                   created_at, updated_at
            FROM expert_review_tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()

        return dict(row)
