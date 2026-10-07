from pathlib import Path
import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "officemate.db"


def get_connection():
    connection = sqlite3.connect(
        DB_PATH,
        timeout=30,
        check_same_thread=False
    )

    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        120000
    )

    return (
        salt.hex()
        + ":"
        + password_hash.hex()
    )


def verify_password(password: str, stored_password: str) -> bool:
    try:
        salt_hex, hash_hex = stored_password.split(":")

        salt = bytes.fromhex(salt_hex)

        calculated = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            120000
        )

        return hmac.compare_digest(
            calculated.hex(),
            hash_hex
        )

    except (ValueError, TypeError):
        return False


def initialize_database():

    with get_connection() as conn:

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_code TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL
                    CHECK(role IN ('employee', 'manager')),
                manager_id INTEGER,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS work_schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                work_date TEXT NOT NULL,
                work_mode TEXT NOT NULL
                    CHECK(work_mode IN ('WFH', 'WFO', 'HYBRID')),
                shift_start TEXT,
                shift_end TEXT,
                FOREIGN KEY(user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'Assigned',
                due_date TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(employee_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                attendance_date TEXT NOT NULL,
                status TEXT NOT NULL,
                check_in TEXT,
                check_out TEXT,
                FOREIGN KEY(employee_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS parking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER,
                parking_zone TEXT NOT NULL,
                slot_number TEXT NOT NULL,
                parking_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Available',
                FOREIGN KEY(employee_id)
                    REFERENCES users(id)
                    ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS cafeteria (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot_name TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                capacity INTEGER NOT NULL,
                booked_count INTEGER NOT NULL DEFAULT 0,
                cafeteria_date TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chat_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id)
                    REFERENCES chat_sessions(id)
                    ON DELETE CASCADE
            );
            """
        )

        conn.commit()


def create_user(
    employee_code,
    full_name,
    email,
    password,
    role,
    manager_id=None
):
    initialize_database()

    password_hash = hash_password(password)

    try:
        with get_connection() as conn:

            cursor = conn.execute(
                """
                INSERT INTO users
                (
                    employee_code,
                    full_name,
                    email,
                    password_hash,
                    role,
                    manager_id,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    employee_code,
                    full_name,
                    email,
                    password_hash,
                    role,
                    manager_id,
                    datetime.now().isoformat()
                )
            )

            conn.commit()

            return cursor.lastrowid

    except sqlite3.IntegrityError:
        return None


def authenticate_user(identifier, password, role):

    initialize_database()

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE
                (employee_code = ? OR email = ?)
                AND role = ?
            """,
            (
                identifier,
                identifier,
                role
            )
        ).fetchone()

    if row is None:
        return None

    if not verify_password(
        password,
        row["password_hash"]
    ):
        return None

    return dict(row)


def get_user(user_id):

    if user_id is None:
        return None

    initialize_database()

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE id = ?
            """,
            (int(user_id),)
        ).fetchone()

    return dict(row) if row else None


def get_employee_dashboard(user_id):

    if user_id is None:
        return {
            "schedule": [],
            "tasks": [],
            "attendance": [],
            "parking": [],
            "cafeteria": []
        }

    initialize_database()

    user_id = int(user_id)

    with get_connection() as conn:

        schedule = conn.execute(
            """
            SELECT *
            FROM work_schedule
            WHERE user_id = ?
            ORDER BY work_date DESC
            LIMIT 10
            """,
            (user_id,)
        ).fetchall()

        tasks = conn.execute(
            """
            SELECT *
            FROM tasks
            WHERE employee_id = ?
            ORDER BY id DESC
            LIMIT 20
            """,
            (user_id,)
        ).fetchall()

        attendance = conn.execute(
            """
            SELECT *
            FROM attendance
            WHERE employee_id = ?
            ORDER BY attendance_date DESC
            LIMIT 10
            """,
            (user_id,)
        ).fetchall()

        parking = conn.execute(
            """
            SELECT *
            FROM parking
            WHERE employee_id = ?
            ORDER BY parking_date DESC
            LIMIT 10
            """,
            (user_id,)
        ).fetchall()

        cafeteria = conn.execute(
            """
            SELECT *
            FROM cafeteria
            ORDER BY cafeteria_date DESC
            LIMIT 10
            """
        ).fetchall()

    return {
        "schedule": [dict(x) for x in schedule],
        "tasks": [dict(x) for x in tasks],
        "attendance": [dict(x) for x in attendance],
        "parking": [dict(x) for x in parking],
        "cafeteria": [dict(x) for x in cafeteria]
    }


def get_manager_dashboard(manager_id):

    if manager_id is None:
        return {
            "employees": [],
            "tasks": [],
            "schedule": [],
            "attendance": [],
            "parking": []
        }

    initialize_database()

    manager_id = int(manager_id)

    with get_connection() as conn:

        employees = conn.execute(
            """
            SELECT
                id,
                employee_code,
                full_name,
                email,
                role
            FROM users
            WHERE manager_id = ?
            ORDER BY full_name
            """,
            (manager_id,)
        ).fetchall()

        tasks = conn.execute(
            """
            SELECT
                t.id,
                t.title,
                t.description,
                t.status,
                t.due_date,
                u.full_name
            FROM tasks t
            JOIN users u
                ON u.id = t.employee_id
            WHERE u.manager_id = ?
            ORDER BY t.id DESC
            """,
            (manager_id,)
        ).fetchall()

        schedule = conn.execute(
            """
            SELECT
                ws.*,
                u.full_name
            FROM work_schedule ws
            JOIN users u
                ON u.id = ws.user_id
            WHERE u.manager_id = ?
            ORDER BY ws.work_date DESC
            """,
            (manager_id,)
        ).fetchall()

        attendance = conn.execute(
            """
            SELECT
                a.*,
                u.full_name
            FROM attendance a
            JOIN users u
                ON u.id = a.employee_id
            WHERE u.manager_id = ?
            ORDER BY a.attendance_date DESC
            """,
            (manager_id,)
        ).fetchall()

        parking = conn.execute(
            """
            SELECT
                p.*,
                u.full_name
            FROM parking p
            LEFT JOIN users u
                ON u.id = p.employee_id
            WHERE u.manager_id = ?
            ORDER BY p.parking_date DESC
            """,
            (manager_id,)
        ).fetchall()

    return {
        "employees": [dict(x) for x in employees],
        "tasks": [dict(x) for x in tasks],
        "schedule": [dict(x) for x in schedule],
        "attendance": [dict(x) for x in attendance],
        "parking": [dict(x) for x in parking]
    }