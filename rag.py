from pathlib import Path
import sqlite3

from database import DB_PATH


DOCUMENT_PATH = (
    Path(__file__).resolve().parent
    / "documents"
    / "workplace_policy.txt"
)


def read_policy():

    if not DOCUMENT_PATH.exists():
        return ""

    return DOCUMENT_PATH.read_text(
        encoding="utf-8"
    )


def get_database_context(user_id):

    if user_id is None:
        return ""

    context_parts = []

    with sqlite3.connect(DB_PATH) as conn:

        conn.row_factory = sqlite3.Row

        user = conn.execute(
            """
            SELECT
                employee_code,
                full_name,
                email,
                role
            FROM users
            WHERE id = ?
            """,
            (int(user_id),)
        ).fetchone()

        if user:
            context_parts.append(
                f"""
User:
Name: {user['full_name']}
Employee Code: {user['employee_code']}
Role: {user['role']}
Email: {user['email']}
"""
            )

        schedules = conn.execute(
            """
            SELECT *
            FROM work_schedule
            WHERE user_id = ?
            ORDER BY work_date DESC
            LIMIT 5
            """,
            (int(user_id),)
        ).fetchall()

        if schedules:

            context_parts.append(
                "Recent work schedules:"
            )

            for row in schedules:

                context_parts.append(
                    f"""
Date: {row['work_date']}
Mode: {row['work_mode']}
Shift: {row['shift_start']} - {row['shift_end']}
"""
                )

        tasks = conn.execute(
            """
            SELECT *
            FROM tasks
            WHERE employee_id = ?
            ORDER BY id DESC
            LIMIT 10
            """,
            (int(user_id),)
        ).fetchall()

        if tasks:

            context_parts.append(
                "Current tasks:"
            )

            for row in tasks:

                context_parts.append(
                    f"""
Task: {row['title']}
Status: {row['status']}
Due: {row['due_date']}
"""
                )

    return "\n".join(context_parts)


def retrieve_context(user_id, question):

    policy = read_policy()

    database_context = get_database_context(
        user_id
    )

    return f"""
WORKPLACE POLICY

{policy}

LIVE USER DATA

{database_context}

USER QUESTION

{question}
"""