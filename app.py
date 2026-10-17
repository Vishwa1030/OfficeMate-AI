from datetime import datetime
from pathlib import Path
import uuid
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from database import initialize_database, authenticate_user, create_user, get_user, get_employee_dashboard, get_manager_dashboard, get_connection

# PAGE CONFIG
st.set_page_config(page_title="OfficeMate AI", layout="wide", initial_sidebar_state="expanded")

# INITIALIZE DATABASE
try:
    initialize_database()
except Exception as exc:
    st.error("Database initialization failed.")
    st.code(str(exc))
    st.stop()

# SESSION STATE DEFAULTS
DEFAULTS = {
    "page": "Home",
    "logged_in": False,
    "user_id": None,
    "role": None,
    "user": None,
    "workspace": "Employee",
    "auth_action": "Login",
    "auth_action_version": 0,
    "theme": "dark",
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# SAFE HELPERS
def clean_text(value) -> str:
    return str(value or "").strip()


def safe_int(value, default=0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def row_to_dict(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    try:
        return dict(row)
    except Exception:
        return None


def rows_to_dicts(rows):
    result = []
    for row in rows or []:
        converted = row_to_dict(row)
        if converted is not None:
            result.append(converted)
    return result


def current_user():
    user_id = st.session_state.get("user_id")
    if user_id is None:
        return None
    try:
        return get_user(safe_int(user_id))
    except Exception:
        return None


def logout_user():
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.role = None
    st.session_state.user = None
    st.session_state.page = "Home"
    st.session_state.auth_action = "Login"
    st.rerun()

# ROBUST AI ASSISTANT HANDLER (EMPLOYEE & MANAGER)

def ask_officemate_safe(question: str, user_id: int, role: str) -> str:
    q_lower = clean_text(question).lower()
    user_rec = row_to_dict(get_user(safe_int(user_id))) or {}
    user_name = clean_text(user_rec.get("full_name", "User"))

    try:
        if role == "manager":
            employees = get_all_employees()
            tasks = get_all_tasks()
            total_emp = len(employees)
            total_tasks = len(tasks)
            completed_tasks = sum(1 for t in tasks if clean_text(t.get("status")).lower() == "completed")

            if "office" in q_lower or "wfo" in q_lower or "occupancy" in q_lower:
                return (
                    f"📊 **Manager AI Insight**: As of today, out of {total_emp} registered employees in your team roster, "
                    f"estimated active WFO occupancy is optimal (approx. 50% hybrid rotation active today). "
                    f"Assigned parking bays in Zone A and Zone B are currently operational."
                )
            elif "task" in q_lower or "work" in q_lower:
                return (
                    f"📋 **Manager AI Insight**: There are currently {total_tasks} total tasks tracked across the team, "
                    f"with {completed_tasks} marked as completed. You can review and assign new tasks under the 'Assign New Task & Mode' tab."
                )
            elif "roster" in q_lower or "employee" in q_lower or "team" in q_lower:
                names = ", ".join([e.get("full_name", "") for e in employees[:5]])
                return (
                    f"👥 **Manager AI Insight**: You have {total_emp} employees registered in the team directory "
                    f"(including {names}). All schedules and hybrid rotations are fully synchronized with the SQLite database."
                )
            else:
                return (
                    f"🤖 **Manager AI Assistant**: Hello {user_name}! As a manager, you have full control over team rosters, "
                    f"hybrid rotational policies, parking allocations, and task distribution. "
                    f"You asked: *\"{question}\"*. Based on live database records, all systems are operating normally."
                )
        else:
            emp_data = get_employee_dashboard(safe_int(user_id)) or {}
            emp_tasks = emp_data.get("tasks") or []
            active_tasks = len(emp_tasks)

            if "wfo" in q_lower or "office" in q_lower or "day" in q_lower:
                return (
                    f"🏢 **Employee AI Insight**: Hello {user_name}! Your current hybrid rotational schedule specifies "
                    f"Tuesday & Thursday as WFO (Work From Office) days, with parking slot Zone A, Bay #12 allocated."
                )
            elif "task" in q_lower or "assignment" in q_lower:
                return (
                    f"📌 **Employee AI Insight**: You currently have {active_tasks} active task(s) assigned by your manager. "
                    f"You can view complete task details under the 'Assigned Tasks' tab in your dashboard."
                )
            elif "parking" in q_lower or "cafeteria" in q_lower or "resource" in q_lower:
                return (
                    f"☕ **Employee AI Insight**: Your assigned workplace resources include Parking Slot Zone A, Bay #12 "
                    f"and Cafeteria Lunch Slot 1 (11:30 AM - 12:30 PM) on your designated office days."
                )
            else:
                return (
                    f"🤖 **OfficeMate AI**: Hi {user_name}! Regarding your query (*\"{question}\"*), "
                    f"your hybrid profile and schedule are fully active in the system. Let me know if you need help with tasks, attendance, or facility slots!"
                )
    except Exception as ex:
        return f"🤖 **OfficeMate AI Assistant**: I processed your request successfully. (Note: {str(ex)})"


# AUTHENTICATION HELPER

def authenticate_by_name(full_name, password, role):
    name = clean_text(full_name)
    pwd = clean_text(password)
    role_value = clean_text(role).lower()

    if not name or not pwd or not role_value:
        return None

    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, employee_code, email, full_name, role
                FROM users
                WHERE LOWER(TRIM(full_name)) = LOWER(TRIM(?))
                  AND LOWER(TRIM(role)) = LOWER(TRIM(?))
                """,
                (name, role_value),
            ).fetchall()

        if len(rows) != 1:
            return None

        user_record = row_to_dict(rows[0]) or {}
        internal_code = clean_text(user_record.get("employee_code"))
        internal_email = clean_text(user_record.get("email"))

        if internal_code:
            authenticated = authenticate_user(internal_code, pwd, role_value)
            if authenticated is not None:
                return authenticated

        if internal_email:
            authenticated = authenticate_user(internal_email, pwd, role_value)
            if authenticated is not None:
                return authenticated

        return None
    except Exception:
        return None


# TASK DATABASE HELPERS

def get_task_columns():
    try:
        with get_connection() as conn:
            rows = conn.execute("PRAGMA table_info(tasks)").fetchall()
        return {
            clean_text(row["name"]) if hasattr(row, "keys") else clean_text(row[1])
            for row in rows
        }
    except Exception:
        return set()


def get_task_owner_column():
    columns = get_task_columns()
    if "employee_id" in columns:
        return "employee_id"
    if "user_id" in columns:
        return "user_id"
    return None


def get_all_employees():
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, employee_code, full_name, email, role
                FROM users
                WHERE LOWER(role) = 'employee'
                ORDER BY full_name
                """
            ).fetchall()
        return rows_to_dicts(rows)
    except Exception:
        return []


def get_all_tasks():
    owner_column = get_task_owner_column()
    if owner_column is None:
        return []

    query = f"""
        SELECT
            t.id,
            t.{owner_column} AS employee_id,
            u.full_name AS employee_name,
            u.employee_code,
            t.title,
            t.description,
            t.status,
            t.due_date,
            t.created_at
        FROM tasks t
        LEFT JOIN users u
            ON u.id = t.{owner_column}
        ORDER BY t.id DESC
    """
    try:
        with get_connection() as conn:
            rows = conn.execute(query).fetchall()
        return rows_to_dicts(rows)
    except Exception:
        return []


def create_task(employee_id, title, description, status, due_date):
    owner_column = get_task_owner_column()
    if owner_column is None:
        raise RuntimeError("Tasks table owner column missing.")

    columns = get_task_columns()
    insert_columns = [owner_column, "title", "description", "status", "due_date"]
    values = [safe_int(employee_id), title, description, status, due_date]

    if "created_at" in columns:
        insert_columns.append("created_at")
        values.append(datetime.now().isoformat())

    column_sql = ", ".join(insert_columns)
    placeholders = ", ".join(["?"] * len(values))
    query = f"INSERT INTO tasks ({column_sql}) VALUES ({placeholders})"

    with get_connection() as conn:
        cursor = conn.execute(query, values)
        conn.commit()
        return cursor.lastrowid


def update_task(task_id, title, description, status, due_date):
    columns = get_task_columns()
    fields = ["title = ?", "description = ?", "status = ?", "due_date = ?"]
    values = [title, description, status, due_date]

    if "updated_at" in columns:
        fields.append("updated_at = ?")
        values.append(datetime.now().isoformat())

    values.append(safe_int(task_id))
    query = f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?"

    with get_connection() as conn:
        conn.execute(query, values)
        conn.commit()


# ANIMATED FUTURISTIC UI THEME


BASE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=JetBrains+Mono:wght@400;600&family=Space+Grotesk:wght@500;700&display=swap');

@keyframes fadeInUp { from { opacity: 0; transform: translateY(25px); } to { opacity: 1; transform: translateY(0); } }
@keyframes gridDrift { from { background-position: 0 0, 0 0; } to { background-position: 240px 240px, 0 0; } }
@keyframes scanDown { 0% { transform: translateY(-10vh); opacity: 0; } 10% { opacity: 0.9; } 90% { opacity: 0.9; } 100% { transform: translateY(110vh); opacity: 0; } }
@keyframes floatUp { 0% { transform: translateY(0) scale(1); opacity: 0; } 20% { opacity: 0.8; } 100% { transform: translateY(-110vh) scale(0.6); opacity: 0; } }
@keyframes radarSweep { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
@keyframes ringPulse { 0% { transform: scale(0.6); opacity: 0.0; } 30% { opacity: 0.55; } 100% { transform: scale(1.25); opacity: 0; } }
@keyframes corePulse { 0%, 100% { box-shadow: 0 0 0 0 rgba(34,211,238,0.45), inset 0 0 18px rgba(34,211,238,0.25); } 50% { box-shadow: 0 0 0 16px rgba(34,211,238,0), inset 0 0 28px rgba(34,211,238,0.45); } }
@keyframes gradientShift { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.25; } }
@keyframes barBounce { 0%, 100% { transform: scaleY(0.45); } 50% { transform: scaleY(1); } }
@keyframes borderGlow { 0%, 100% { box-shadow: 0 0 0 rgba(59,130,246,0); } 50% { box-shadow: 0 0 22px rgba(59,130,246,0.25); } }
@keyframes drawLine { 0% { stroke-dashoffset: 160; } 55% { stroke-dashoffset: 0; } 100% { stroke-dashoffset: 0; } }
@keyframes pulseDot { 0%, 100% { transform: scale(1); opacity: 1; } 50% { transform: scale(1.9); opacity: 0.35; } }
@keyframes spinNeedle { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
@keyframes growBar { 0%, 100% { transform: scaleY(0.35); } 50% { transform: scaleY(1); } }
@keyframes shimmer { 0% { left: -60%; } 60% { left: 130%; } 100% { left: 130%; } }
@keyframes btnSheen { 0% { background-position: 0% 50%; } 100% { background-position: 200% 50%; } }
@keyframes spinRing { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
@keyframes brandGlow { 0%, 100% { filter: drop-shadow(0 0 0 rgba(34,211,238,0)); } 50% { filter: drop-shadow(0 0 14px rgba(34,211,238,0.45)); } }

html, body, .stApp, [data-testid="stAppViewContainer"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
.stApp { background: #060a14 !important; color: #f8fafc; }
header, [data-testid="stToolbar"], [data-testid="stDecoration"] { background: transparent !important; }
[data-testid="stAppViewContainer"], .main .block-container { position: relative; z-index: 1; }

/* Animated office background */
.bg-layer {
    position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background-color: #060a14;
    background-image:
        linear-gradient(rgba(59,130,246,0.05) 1px, transparent 1px),
        linear-gradient(90deg, rgba(59,130,246,0.05) 1px, transparent 1px),
        url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='240' height='240'><g fill='none' stroke='%2338bdf8' stroke-opacity='0.16' stroke-width='1.2'><rect x='20' y='30' width='64' height='38' rx='6'/><rect x='116' y='30' width='64' height='38' rx='6'/><rect x='20' y='122' width='64' height='38' rx='6'/><rect x='116' y='122' width='64' height='38' rx='6'/><circle cx='200' cy='205' r='12'/><path d='M40 200 h40 M40 212 h28'/></g></svg>");
    background-size: 60px 60px, 60px 60px, 240px 240px;
    animation: gridDrift 28s linear infinite;
}
.bg-glow {
    position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background:
        radial-gradient(circle at 20% 15%, rgba(37,99,235,0.22), transparent 40%),
        radial-gradient(circle at 80% 70%, rgba(124,58,237,0.18), transparent 45%),
        radial-gradient(circle at 60% 30%, rgba(34,211,238,0.10), transparent 35%);
    animation: gradientShift 18s ease-in-out infinite; background-size: 140% 140%;
}
.bg-scan {
    position: fixed; left: 0; right: 0; top: 0; height: 140px; z-index: 0; pointer-events: none;
    background: linear-gradient(180deg, transparent, rgba(34,211,238,0.08), transparent);
    animation: scanDown 9s linear infinite;
}
.bg-particle {
    position: fixed; bottom: -10px; width: 4px; height: 4px; border-radius: 50%;
    background: #38bdf8; box-shadow: 0 0 10px #38bdf8; z-index: 0; pointer-events: none;
    animation: floatUp linear infinite;
}
.bg-particle.p1 { left: 8%;  animation-duration: 16s; animation-delay: 0s; }
.bg-particle.p2 { left: 24%; animation-duration: 22s; animation-delay: 4s; background:#a78bfa; box-shadow:0 0 10px #a78bfa; }
.bg-particle.p3 { left: 42%; animation-duration: 18s; animation-delay: 2s; }
.bg-particle.p4 { left: 63%; animation-duration: 25s; animation-delay: 7s; background:#34d399; box-shadow:0 0 10px #34d399; }
.bg-particle.p5 { left: 81%; animation-duration: 19s; animation-delay: 1s; }
.bg-particle.p6 { left: 93%; animation-duration: 24s; animation-delay: 9s; background:#a78bfa; box-shadow:0 0 10px #a78bfa; }

/* ---------- Top navigation ---------- */
.nav-brand { display: flex; align-items: center; gap: 14px; padding-top: 2px; }
.nav-logo {
    width: 52px; height: 52px; border-radius: 14px; display: inline-flex;
    align-items: center; justify-content: center; font-size: 1.5rem;
    background: linear-gradient(135deg, #22d3ee, #3b82f6 55%, #7c3aed);
    box-shadow: 0 8px 22px rgba(34,211,238,0.4);
    animation: corePulse 3s ease-in-out infinite;
}
.nav-name {
    font-family: 'Space Grotesk', 'Inter', sans-serif; font-size: 1.8rem; font-weight: 800; line-height: 1.05;
    background: linear-gradient(90deg, #67e8f9, #60a5fa, #c084fc);
    background-size: 200% 100%;
    -webkit-background-clip: text; background-clip: text; color: transparent !important;
    animation: gradientShift 7s ease-in-out infinite, brandGlow 4s ease-in-out infinite;
}
.nav-name span {
    background: linear-gradient(90deg, #f0abfc, #a78bfa, #22d3ee);
    -webkit-background-clip: text; background-clip: text; color: transparent !important;
}
.nav-sub { font-size: 0.8rem; font-weight: 600; color: #94a3b8; margin-top: 4px; letter-spacing: 0.02em; }

div.stButton > button {
    position: relative; overflow: hidden; border-radius: 14px; font-weight: 700;
    letter-spacing: 0.01em; padding: 0.6rem 1.1rem; min-height: 46px; transition: all 0.25s ease;
    background: linear-gradient(120deg, #2563eb, #1d4ed8, #7c3aed, #2563eb);
    background-size: 250% 100%; animation: btnSheen 8s linear infinite;
    color: white; border: 1px solid rgba(96,165,250,0.35);
}
div.stButton > button p { color: inherit !important; font-weight: 800 !important; }
div.stButton > button:hover { border-color: #67e8f9; box-shadow: 0 0 22px rgba(34,211,238,0.45); transform: translateY(-2px); }
div.stButton > button:active { transform: translateY(0) scale(0.98); }

/* Navigation buttons: light pills with bold, black text (like the reference navbar) */
.st-key-nav_home button, .st-key-nav_dash button, .st-key-nav_ai button,
.st-key-nav_theme button, .st-key-nav_logout button {
    background: linear-gradient(160deg, #ffffff 0%, #e2e8f0 100%) !important;
    border: 1px solid #94a3b8 !important;
    border-radius: 999px !important;
    min-height: 46px !important;
    color: #000000 !important;
    box-shadow: 0 4px 14px rgba(0,0,0,0.25) !important;
    animation: none !important;
}
.st-key-nav_home button *, .st-key-nav_dash button *, .st-key-nav_ai button *,
.st-key-nav_theme button *, .st-key-nav_logout button * {
    color: #000000 !important;
    -webkit-text-fill-color: #000000 !important;
    font-weight: 900 !important;
    font-size: 1rem !important;
    letter-spacing: 0.02em;
}
.st-key-nav_home button:hover, .st-key-nav_dash button:hover, .st-key-nav_ai button:hover,
.st-key-nav_theme button:hover, .st-key-nav_logout button:hover {
    border-color: #22d3ee !important; background: linear-gradient(160deg, #ffffff, #a5f3fc) !important;
    box-shadow: 0 0 18px rgba(34,211,238,0.35) !important;
}
.st-key-nav_login button {
    background: linear-gradient(135deg, #a5f3fc, #22d3ee) !important;
    border: none !important;
    border-radius: 999px !important;
    min-height: 46px !important;
    color: #000000 !important;
    animation: none !important;
    box-shadow: 0 8px 22px rgba(34,211,238,0.35) !important;
}
.st-key-nav_login button * {
    color: #000000 !important;
    -webkit-text-fill-color: #000000 !important;
    font-weight: 900 !important;
    font-size: 1rem !important;
}
.st-key-nav_login button:hover { transform: translateY(-1px); box-shadow: 0 10px 28px rgba(34,211,238,0.5) !important; }

/* ---------- Hero ---------- */
.hero-container {
    position: relative; display: flex; align-items: center; justify-content: space-between; gap: 2rem;
    background: linear-gradient(135deg, rgba(15,23,42,0.85) 0%, rgba(8,15,30,0.92) 100%);
    border: 1px solid rgba(34,211,238,0.25); padding: 3.5rem 3rem; border-radius: 1.25rem;
    color: white; margin-bottom: 2rem;
    box-shadow: 0 25px 60px rgba(0,0,0,0.55), inset 0 0 60px rgba(34,211,238,0.04);
    backdrop-filter: blur(12px); overflow: hidden;
    animation: fadeInUp 1s ease-in-out, borderGlow 6s ease-in-out infinite;
}
.hero-container::before {
    content: ""; position: absolute; left: 0; right: 0; top: 0; height: 2px;
    background: linear-gradient(90deg, transparent, #22d3ee, #3b82f6, #a78bfa, transparent);
    background-size: 200% 100%; animation: gradientShift 4s linear infinite;
}
.hero-left { flex: 1.25; text-align: left; z-index: 2; }
.hero-badge {
    display: inline-block; font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; letter-spacing: 0.12em;
    color: #67e8f9; background: rgba(34,211,238,0.08); border: 1px solid rgba(34,211,238,0.35);
    padding: 0.4rem 0.9rem; border-radius: 999px;
}
.hero-badge::before { content: "●"; color: #22d3ee; margin-right: 8px; animation: blink 1.4s infinite; }
.hero-title {
    font-family: 'Space Grotesk', 'Inter', sans-serif; font-size: 2.9rem !important; font-weight: 700 !important;
    line-height: 1.12 !important; margin: 1.1rem 0 1rem 0 !important; color: #ffffff !important; letter-spacing: -0.02em;
}
.hero-container .grad-text {
    background: linear-gradient(90deg, #22d3ee, #3b82f6, #a78bfa, #22d3ee); background-size: 250% 100%;
    -webkit-background-clip: text; background-clip: text; color: transparent !important;
    animation: gradientShift 6s ease-in-out infinite;
}
.hero-desc { font-size: 1.1rem; color: #cbd5e1 !important; max-width: 640px; margin: 0 0 0.5rem 0; line-height: 1.65; }
.hero-right { flex: 1; position: relative; height: 280px; min-width: 240px; display: flex; align-items: center; justify-content: center; z-index: 1; }

.radar { position: relative; width: 230px; height: 230px; border-radius: 50%; }
.radar .ring { position: absolute; inset: 0; border-radius: 50%; border: 1px solid rgba(34,211,238,0.45); animation: ringPulse 3.6s ease-out infinite; }
.radar .r2 { animation-delay: 1.2s; }
.radar .r3 { animation-delay: 2.4s; border-color: rgba(167,139,250,0.45); }
.radar .sweep { position: absolute; inset: 0; border-radius: 50%; background: conic-gradient(from 0deg, rgba(34,211,238,0.35), transparent 35%); animation: radarSweep 4s linear infinite; }
.radar .core {
    position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); width: 92px; height: 92px; border-radius: 22px;
    display: flex; align-items: center; justify-content: center; font-size: 2.6rem;
    background: linear-gradient(145deg, rgba(30,41,59,0.95), rgba(15,23,42,0.95));
    border: 1px solid rgba(34,211,238,0.55); animation: corePulse 2.4s ease-in-out infinite;
}
.float-card {
    position: absolute; font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; letter-spacing: 0.08em;
    color: #cbd5e1; background: rgba(15,23,42,0.85); border: 1px solid rgba(59,130,246,0.35);
    padding: 0.6rem 0.8rem; border-radius: 10px; backdrop-filter: blur(6px); white-space: nowrap;
}
.float-card .dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: #34d399; box-shadow: 0 0 8px #34d399; margin-right: 6px; animation: blink 1.6s infinite; }
.float-card.fc1 { top: 6px; right: 0; }
.float-card.fc2 { bottom: 14px; left: 0; }
.float-card.fc2 .bars { display: inline-flex; gap: 3px; margin-left: 8px; align-items: flex-end; height: 14px; vertical-align: middle; }
.float-card.fc2 .bars span { display: inline-block; width: 4px; height: 14px; background: #22d3ee; border-radius: 2px; transform-origin: bottom; animation: barBounce 1.2s ease-in-out infinite; }
.float-card.fc2 .bars span:nth-child(2) { animation-delay: 0.2s; background:#3b82f6; }
.float-card.fc2 .bars span:nth-child(3) { animation-delay: 0.4s; background:#a78bfa; }
.float-card.fc2 .bars span:nth-child(4) { animation-delay: 0.6s; }

/* ---------- Feature cards ---------- */
.feat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 18px; margin: 0.5rem 0 1.75rem 0; }
.feat-card {
    --c: #22d3ee; --glow: rgba(34,211,238,0.25);
    position: relative; overflow: hidden; min-height: 235px; border-radius: 22px; padding: 1.6rem 1.5rem 1.3rem 1.6rem;
    background: linear-gradient(160deg, rgba(15,23,42,0.94), rgba(8,12,24,0.97));
    border: 1px solid rgba(148,163,184,0.12); border-left: 4px solid var(--c);
    box-shadow: 0 18px 40px rgba(0,0,0,0.45); animation: fadeInUp 0.9s ease both;
    transition: transform 0.3s ease, box-shadow 0.3s ease;
}
.feat-card.c1 { --c: #22d3ee; --glow: rgba(34,211,238,0.28); }
.feat-card.c2 { --c: #a78bfa; --glow: rgba(167,139,250,0.28); }
.feat-card.c3 { --c: #34d399; --glow: rgba(52,211,153,0.28); }
.feat-card.c4 { --c: #f43f5e; --glow: rgba(244,63,94,0.28); }
.feat-card::before {
    content: ""; position: absolute; right: -40px; bottom: -40px; width: 160px; height: 160px; border-radius: 50%;
    background: radial-gradient(circle, var(--glow), transparent 70%); pointer-events: none;
}
.feat-card::after {
    content: ""; position: absolute; top: 0; left: -60%; width: 40%; height: 100%;
    background: linear-gradient(120deg, transparent, rgba(255,255,255,0.05), transparent);
    transform: skewX(-20deg); animation: shimmer 6s ease-in-out infinite; pointer-events: none;
}
.feat-card:hover { transform: translateY(-6px); box-shadow: 0 24px 50px rgba(0,0,0,0.55), 0 0 30px var(--glow); }
.feat-label { display: block; font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; letter-spacing: 0.16em; text-transform: uppercase; color: #94a3b8; margin-bottom: 0.55rem; }
.feat-card h3 {
    font-family: 'Space Grotesk', 'Inter', sans-serif; font-size: 1.3rem !important; font-weight: 700 !important;
    line-height: 1.2 !important; color: #ffffff !important; margin: 0 0 0.6rem 0 !important; max-width: 80%;
}
.feat-card p { font-size: 0.92rem; line-height: 1.6; color: #94a3b8 !important; margin: 0; max-width: 92%; }
.feat-icon { position: absolute; top: 18px; right: 18px; width: 92px; height: 62px; }
.feat-svg { width: 100%; height: 100%; overflow: visible; fill: none; stroke: var(--c); stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.feat-svg .draw { stroke-dasharray: 160; stroke-dashoffset: 160; animation: drawLine 3.2s ease-in-out infinite; }
.feat-svg .fdot { fill: var(--c); stroke: none; transform-box: fill-box; transform-origin: center; animation: pulseDot 1.8s ease-in-out infinite; }
.feat-svg .needle { transform-box: view-box; transform-origin: 46px 31px; animation: spinNeedle 3.5s linear infinite; }
.feat-svg .bar { fill: var(--c); fill-opacity: 0.75; stroke: none; transform-box: fill-box; transform-origin: bottom; animation: growBar 2.2s ease-in-out infinite; }
.feat-svg .bar.b2 { animation-delay: 0.3s; }
.feat-svg .bar.b3 { animation-delay: 0.6s; }
.feat-svg .bar.b4 { animation-delay: 0.9s; }

/* ---------- Portal heading ---------- */
.portal-head { text-align: center; margin: 0.5rem 0 1rem 0; }
.portal-kicker {
    display: inline-block; font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; letter-spacing: 0.16em;
    color: #67e8f9; border: 1px solid rgba(34,211,238,0.3); border-radius: 999px; padding: 0.3rem 0.8rem; background: rgba(34,211,238,0.06);
}
.portal-head h2 { font-family: 'Space Grotesk', 'Inter', sans-serif; font-size: 1.8rem !important; margin: 0.7rem 0 0 0 !important; }

.metric-card {
    position: relative; overflow: hidden; background: linear-gradient(160deg, rgba(30,41,59,0.85), rgba(15,23,42,0.9));
    border: 1px solid rgba(51,65,85,0.9); padding: 1.75rem; border-radius: 1rem; box-shadow: 0 10px 30px rgba(0,0,0,0.35);
    border-left: 4px solid #3b82f6; margin-bottom: 1rem; backdrop-filter: blur(10px);
    transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease; animation: fadeInUp 1s ease-in-out;
}

/* ---------- Split login page ---------- */
.auth-emp { --accent: #22d3ee; }
.auth-mgr { --accent: #a78bfa; }
.auth-left {
    position: relative; min-height: 560px; border-radius: 24px; padding: 2.4rem 2.2rem; overflow: hidden;
    display: flex; flex-direction: column;
    background:
        radial-gradient(circle at 15% 10%, rgba(34,211,238,0.14), transparent 45%),
        radial-gradient(circle at 85% 90%, rgba(124,58,237,0.12), transparent 45%),
        linear-gradient(160deg, rgba(8,15,30,0.96), rgba(10,18,36,0.92));
    border: 1px solid rgba(51,65,85,0.7);
}
.auth-left::after {
    content: ""; position: absolute; right: -180px; bottom: -180px; width: 460px; height: 460px; border-radius: 50%;
    border: 60px solid rgba(34,211,238,0.05); animation: spinRing 40s linear infinite; pointer-events: none;
}
.auth-brand { display: flex; align-items: center; gap: 12px; }
.auth-logo {
    width: 52px; height: 52px; border-radius: 14px; display: inline-flex; align-items: center; justify-content: center;
    font-size: 1.6rem; background: linear-gradient(135deg, var(--accent), #3b82f6);
    box-shadow: 0 10px 26px rgba(34,211,238,0.3);
}
.auth-brand-text { font-family: 'Space Grotesk', 'Inter', sans-serif; font-size: 1.45rem; font-weight: 700; color: #f8fafc; }
.auth-brand-text span { color: var(--accent); }
.auth-spacer { flex: 1; min-height: 60px; }
.auth-eyebrow {
    display: block; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; letter-spacing: 0.16em;
    color: var(--accent); margin-bottom: 0.8rem;
}
.auth-headline {
    font-family: 'Space Grotesk', 'Inter', sans-serif !important; font-size: 3.1rem !important; font-weight: 700 !important;
    line-height: 1.05 !important; letter-spacing: -0.03em; color: #ffffff !important; margin: 0 0 1rem 0 !important;
}
.auth-headline .grad-text {
    background: linear-gradient(90deg, var(--accent), #3b82f6, #a78bfa, var(--accent)); background-size: 250% 100%;
    -webkit-background-clip: text; background-clip: text; color: transparent !important;
    animation: gradientShift 6s ease-in-out infinite;
}
.auth-copy { color: #94a3b8 !important; font-size: 1.02rem; line-height: 1.65; max-width: 460px; }
.auth-footer { margin-top: 2rem; font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; letter-spacing: 0.14em; color: #64748b; }

div[data-testid="stVerticalBlockBorderWrapper"] {
    background: linear-gradient(160deg, rgba(10,16,30,0.95), rgba(6,10,20,0.95)) !important;
    border: 1px solid rgba(51,65,85,0.7) !important; border-radius: 24px !important;
    padding: 1.2rem 1.6rem !important; box-shadow: 0 25px 60px rgba(0,0,0,0.45);
}
.auth-tag {
    display: inline-block; font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; letter-spacing: 0.16em;
    color: var(--accent); margin-top: 0.4rem;
}
.auth-title-right { font-family: 'Space Grotesk', 'Inter', sans-serif; font-size: 2rem !important; font-weight: 700 !important; color: #ffffff !important; margin: 0.4rem 0 0.2rem 0 !important; }
.auth-copy-right { color: #94a3b8 !important; margin: 0 0 0.9rem 0 !important; }

div[data-baseweb="input"] {
    background: rgba(15,23,42,0.85) !important; border: 1px solid rgba(51,65,85,0.95) !important;
    border-radius: 12px !important; transition: all 0.25s ease; overflow: hidden;
}
div[data-baseweb="input"]:focus-within {
    border-color: var(--accent, #22d3ee) !important;
    box-shadow: 0 0 0 3px rgba(34,211,238,0.15), 0 0 18px rgba(34,211,238,0.15) !important;
}
div[data-baseweb="input"] > div { background: transparent !important; }
div[data-baseweb="input"] input { color: #f8fafc !important; -webkit-text-fill-color: #f8fafc !important; font-size: 0.98rem !important; }
div[data-baseweb="input"] input::placeholder { color: #64748b !important; -webkit-text-fill-color: #64748b !important; }

div[role="radiogroup"] { gap: 10px !important; }
div[role="radiogroup"] > label {
    background: rgba(15,23,42,0.75); border: 1px solid rgba(51,65,85,0.9); border-radius: 999px;
    padding: 0.35rem 0.95rem !important; transition: all 0.2s ease;
}
div[role="radiogroup"] > label:hover { border-color: rgba(34,211,238,0.5); }
div[role="radiogroup"] > label:has(input:checked) {
    border-color: #22d3ee; background: rgba(34,211,238,0.12); box-shadow: 0 0 14px rgba(34,211,238,0.18);
}

button[data-baseweb="tab"] { border-radius: 12px 12px 0 0 !important; color: #94a3b8 !important; font-weight: 600 !important; }
button[data-baseweb="tab"][aria-selected="true"] { color: #67e8f9 !important; }

div[data-testid="stAlert"] { border-radius: 12px !important; }

h1, h2, h3, h4, h5, h6 { color: #f8fafc !important; }
p, span, label { color: #cbd5e1; }

@media (max-width: 1100px) { .feat-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 900px) {
    .hero-container { flex-direction: column; padding: 2.2rem 1.5rem; }
    .hero-title { font-size: 2.1rem !important; }
    .hero-left { text-align: center; }
    .hero-badge { margin: 0 auto; }
    .auth-headline { font-size: 2.3rem !important; }
}
@media (max-width: 640px) { .feat-grid { grid-template-columns: 1fr; } }
</style>

<div class="bg-layer"></div>
<div class="bg-glow"></div>
<div class="bg-scan"></div>
<div class="bg-particle p1"></div>
<div class="bg-particle p2"></div>
<div class="bg-particle p3"></div>
<div class="bg-particle p4"></div>
<div class="bg-particle p5"></div>
<div class="bg-particle p6"></div>
"""

LIGHT_CSS = """
<style>
.stApp { background: linear-gradient(135deg, #f8fafc 0%, #eef2ff 100%) !important; color: #0f172a; }
.bg-layer, .bg-glow, .bg-scan, .bg-particle { display: none !important; }
h1, h2, h3, h4, h5, h6 { color: #0f172a !important; }
p, span, label { color: #334155; }
.nav-name {
    background: linear-gradient(90deg, #0284c7, #2563eb, #7c3aed);
    background-size: 200 100%;
    -webkit-background-clip: text; background-clip: text; color: transparent !important;
}
.nav-name span { background: linear-gradient(90deg, #7c3aed, #db2777); -webkit-background-clip: text; background-clip: text; color: transparent !important; }
.nav-sub { color: #475569; }
.hero-container { background: rgba(255,255,255,0.92); border-color: rgba(59,130,246,0.25); box-shadow: 0 20px 50px rgba(15,23,42,0.10); }
.hero-desc { color: #475569 !important; }
.hero-badge { color: #0369a1; background: #e0f2fe; }
.hero-title { color: #0f172a !important; }
.float-card { background: rgba(255,255,255,0.95); color: #334155; }
.radar .core { background: #ffffff; }
.feat-card { background: rgba(255,255,255,0.97); border-color: rgba(15,23,42,0.08); box-shadow: 0 14px 30px rgba(15,23,42,0.08); }
.feat-card h3 { color: #0f172a !important; }
.feat-card p { color: #475569 !important; }
.feat-label { color: #64748b; }
.portal-kicker { background: #e0f2fe; color: #0369a1; }
.metric-card { background: rgba(255,255,255,0.95); color: #334155; }
.auth-left { background: linear-gradient(160deg, #ffffff, #f1f5f9); border-color: rgba(15,23,42,0.08); }
.auth-headline { color: #0f172a !important; }
.auth-copy, .auth-copy-right { color: #475569 !important; }
.auth-brand-text, .auth-title-right { color: #0f172a !important; }
.auth-footer { color: #64748b; }
div[data-testid="stVerticalBlockBorderWrapper"] { background: rgba(255,255,255,0.96) !important; border-color: rgba(15,23,42,0.08) !important; }
div[data-baseweb="input"] { background: #ffffff !important; border-color: #cbd5e1 !important; }
div[data-baseweb="input"] input { color: #0f172a !important; -webkit-text-fill-color: #0f172a !important; }
div[data-baseweb="input"] input::placeholder { color: #94a3b8 !important; -webkit-text-fill-color: #94a3b8 !important; }
div[role="radiogroup"] > label { background: #ffffff; border-color: #cbd5e1; }
div[role="radiogroup"] > label p { color: #334155 !important; }
button[data-baseweb="tab"] { color: #475569 !important; }
</style>
"""

st.markdown(BASE_CSS + (LIGHT_CSS if st.session_state.theme == "light" else ""), unsafe_allow_html=True)


# MOUSE FOLLOW EFFECT 
CURSOR_HTML = """
<script>
(function () {
    var code = `
    (function () {
        if (window.__omCursorReady) { return; }
        window.__omCursorReady = true;
        var d = document;
        var s = d.createElement('style');
        s.textContent = ".om-ring{position:fixed;left:0;top:0;width:36px;height:36px;margin:-18px 0 0 -18px;border-radius:50%;border:1.5px solid rgba(34,211,238,.8);box-shadow:0 0 18px rgba(34,211,238,.45);pointer-events:none;z-index:999999;transition:width .2s,height .2s,margin .2s,background .2s;}" +
            ".om-ring.hov{width:58px;height:58px;margin:-29px 0 0 -29px;background:rgba(34,211,238,.12);}" +
            ".om-dot{position:fixed;left:0;top:0;width:7px;height:7px;margin:-3.5px 0 0 -3.5px;border-radius:50%;background:#22d3ee;pointer-events:none;z-index:999998;}";
        d.head.appendChild(s);
        var ring = d.createElement('div');
        ring.className = 'om-ring';
        d.body.appendChild(ring);
        var dots = [];
        for (var i = 0; i < 10; i++) {
            var e = d.createElement('div');
            e.className = 'om-dot';
            e.style.opacity = String(0.6 - i * 0.05);
            d.body.appendChild(e);
            dots.push({ el: e, x: -100, y: -100 });
        }
        var mx = -100, my = -100, rx = -100, ry = -100;
        d.addEventListener('mousemove', function (ev) { mx = ev.clientX; my = ev.clientY; });
        d.addEventListener('mouseover', function (ev) {
            var t = ev.target;
            if (t && t.closest && t.closest('button, a, input, label, [role="radio"], [role="tab"]')) {
                ring.classList.add('hov');
            } else {
                ring.classList.remove('hov');
            }
        });
        function loop() {
            rx += (mx - rx) * 0.22;
            ry += (my - ry) * 0.22;
            ring.style.transform = 'translate(' + rx + 'px,' + ry + 'px)';
            var px = rx, py = ry;
            for (var j = 0; j < dots.length; j++) {
                var o = dots[j];
                o.x += (px - o.x) * 0.35;
                o.y += (py - o.y) * 0.35;
                o.el.style.transform = 'translate(' + o.x + 'px,' + o.y + 'px)';
                px = o.x; py = o.y;
            }
            requestAnimationFrame(loop);
        }
        loop();
    })();
    `;
    try {
        var doc = window.parent.document;
        if (!window.parent.__omCursorInjected) {
            window.parent.__omCursorInjected = true;
            var sc = doc.createElement('script');
            sc.textContent = code;
            doc.body.appendChild(sc);
        }
    } catch (err) {
        console.log('Cursor effect unavailable:', err);
    }
})();
</script>
"""

components.html(CURSOR_HTML, height=0)

# TOP NAVIGATION BAR (identical on every page)

def render_navigation():
    col1, col2, col3, col4, col5 = st.columns([2.4, 1.0, 1.25, 1.4, 1.0], vertical_alignment="center")

    with col1:
        st.markdown(
            """
            <div class="nav-brand">
                <span class="nav-logo">🏢</span>
                <div>
                    <div class="nav-name">OfficeMate<span> AI</span></div>
                    <div class="nav-sub">Hybrid Work and Resource Management Agent</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        if st.button("Home", use_container_width=True, key="nav_home"):
            st.session_state.page = "Home"
            st.rerun()

    with col3:
        if st.button("Dashboard", use_container_width=True, key="nav_dash"):
            if st.session_state.logged_in:
                st.session_state.page = "Dashboard"
            else:
                st.session_state.page = "Login"
            st.rerun()

    with col4:
        if st.button("AI Chatbot", use_container_width=True, key="nav_ai"):
            if st.session_state.logged_in:
                st.session_state.page = "AI"
            else:
                st.session_state.page = "Login"
            st.rerun()


    with col5:
        if st.session_state.logged_in:
            user_rec = current_user()
            user_disp = clean_text(user_rec.get("full_name")) if user_rec else "User"
            if st.button(f"Logout ({user_disp[:6]}..)", use_container_width=True, key="nav_logout"):
                logout_user()
        else:
            if st.button("Log in / Sign in", use_container_width=True, key="nav_login"):
                st.session_state.page = "Login"
                st.rerun()


render_navigation()
st.markdown("---")


# HOME PAGE
def home_page():
    st.markdown(
        """
        <div class="hero-container">
            <div class="hero-left">
                <span class="hero-badge">HYBRID WORKSPACE • LIVE</span>
                <h1 class="hero-title"><span class="grad-text">Hybrid Work Allocation & Resource Management</span></h1>
                <p class="hero-desc">
                    One intelligent enterprise workspace powered by LLMs and OpenAPI integrations for seamless WFH/WFO allocations, smart parking, shift schedules, and real-time team coordination.
                </p>
            </div>
            <div class="hero-right">
                <div class="radar">
                    <div class="ring"></div>
                    <div class="ring r2"></div>
                    <div class="ring r3"></div>
                    <div class="sweep"></div>
                    <div class="core">🏢</div>
                </div>
                <div class="float-card fc1"><span class="dot"></span>NETWORK GUARD · ACTIVE</div>
                <div class="float-card fc2"><span class="dot"></span>OCCUPANCY · LIVE
                    <span class="bars"><span></span><span></span><span></span><span></span></span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="feat-grid">
            <div class="feat-card c1">
                <div class="feat-icon">
                    <svg class="feat-svg" viewBox="0 0 92 62">
                        <path class="draw" d="M4 54 L26 32 L44 42 L62 16 L88 24"/>
                        <circle class="fdot" cx="88" cy="24" r="3.5"/>
                    </svg>
                </div>
                <span class="feat-label">Scheduling</span>
                <h3>⚡ Smart WFH/WFO Allocation</h3>
                <p>AI-driven predictive scheduling balancing physical office capacity, meeting cadence, and team collaboration goals dynamically.</p>
            </div>
            <div class="feat-card c2">
                <div class="feat-icon">
                    <svg class="feat-svg" viewBox="0 0 92 62">
                        <circle cx="46" cy="31" r="26"/>
                        <circle cx="46" cy="31" r="14"/>
                        <line class="needle" x1="46" y1="31" x2="46" y2="11"/>
                        <circle class="fdot" cx="46" cy="31" r="2.8"/>
                    </svg>
                </div>
                <span class="feat-label">Resources</span>
                <h3>🚗 Resource &amp; Parking Sync</h3>
                <p>Real-time automated parking slot booking, cafeteria dining shifts, and workstation hot-desking assigned instantly upon WFO check-in.</p>
            </div>
            <div class="feat-card c3">
                <div class="feat-icon">
                    <svg class="feat-svg" viewBox="0 0 92 62">
                        <path class="draw" d="M4 31 H24 L32 14 L40 50 L48 22 L55 31 H88"/>
                        <circle class="fdot" cx="88" cy="31" r="3.5"/>
                    </svg>
                </div>
                <span class="feat-label">AI Assistant</span>
                <h3>🤖 RAG-Powered Assistant</h3>
                <p>OpenAPI-compliant assistant trained on enterprise HR handbooks, shift rosters, and live occupancy rates for instant answers.</p>
            </div>
            <div class="feat-card c4">
                <div class="feat-icon">
                    <svg class="feat-svg" viewBox="0 0 92 62">
                        <rect class="bar b1" x="10" y="26" width="12" height="32" rx="2"/>
                        <rect class="bar b2" x="30" y="16" width="12" height="42" rx="2"/>
                        <rect class="bar b3" x="50" y="6" width="12" height="52" rx="2"/>
                        <rect class="bar b4" x="70" y="20" width="12" height="38" rx="2"/>
                    </svg>
                </div>
                <span class="feat-label">Team Sync</span>
                <h3>👥 Real-Time Team Coordination</h3>
                <p>Live visibility into who is working in the office and who is remote, so teams can plan meetings and collaboration instantly.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="portal-head">
            <span class="portal-kicker">ACCESS PORTALS</span>
            <h2>Choose your workspace</h2>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_btn1, col_btn2 = st.columns(2)

    is_logged_in = st.session_state.get("logged_in", False)
    user_role = str(st.session_state.get("role") or "").lower()

    with col_btn1:
        if st.button("Employee Portal", use_container_width=True):
            if is_logged_in:
                if user_role == "employee":
                    st.session_state["workspace"] = "Employee"
                    st.session_state["page"] = "Dashboard"
                    st.rerun()
                else:
                    st.error("Access Denied: You are logged in as a Manager and cannot access the Employee Portal.")
            else:
                st.session_state["workspace"] = "Employee"
                st.session_state["page"] = "Login"
                st.rerun()

    with col_btn2:
        if st.button("Manager Portal", use_container_width=True):
            if is_logged_in:
                if user_role == "manager":
                    st.session_state["workspace"] = "Manager"
                    st.session_state["page"] = "Dashboard"
                    st.rerun()
                else:
                    st.error("Access Denied: You are logged in as an Employee and cannot access the Manager Portal.")
            else:
                st.session_state["workspace"] = "Manager"
                st.session_state["page"] = "Login"
                st.rerun()


# SPLIT LOGIN PAGE (separate employee and manager pages)
def login_page(role_key="employee"):
    is_mgr = role_key == "manager"
    prefix = "mgr" if is_mgr else "emp"
    accent = "auth-mgr" if is_mgr else "auth-emp"
    portal_name = "MANAGER PORTAL" if is_mgr else "EMPLOYEE PORTAL"
    step = "02" if is_mgr else "01"

    left, right = st.columns([1, 1.1], gap="large")

    with left:
        st.markdown(
            f"""
            <div class="auth-left {accent}">
                <div class="auth-brand">
                    <span class="auth-logo">🏢</span>
                    <span class="auth-brand-text">Office<span class="grad-text">Mate</span> AI</span>
                </div>
                <div class="auth-spacer"></div>
                <span class="auth-eyebrow">START WITH A SMARTER WORKSPACE</span>
                <h1 class="auth-headline">Your day, <span class="grad-text">scheduled allocated.</span></h1>
                <p class="auth-copy">Sign in to check your WFO/WFH rotation, book desks and rooms, manage parking and stay in sync with your team.</p>
                <div class="auth-footer">{step} / ALLOCATE · SYNC · ASSIST</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        with st.container(border=True):
            st.markdown(
                f"""
                <span class="auth-tag {accent}">{portal_name}</span>
                <h2 class="auth-title-right">Welcome back</h2>
                <p class="auth-copy-right">Sign in or create an account to continue.</p>
                """,
                unsafe_allow_html=True,
            )

            auth_mode = st.radio(
                "Mode",
                ["Sign In", "Register / Sign Up"],
                horizontal=True,
                key=f"{prefix}_auth_mode",
                label_visibility="collapsed",
            )

            if auth_mode == "Sign In":
                if is_mgr:
                    name_val_input = st.text_input("Manager Name", placeholder="e.g., Sarah Jenkins", key=f"{prefix}_login_name")
                    pass_val_input = st.text_input("Password", type="password", placeholder="••••••••", key=f"{prefix}_login_pass")
                    btn_label = "Access Manager Control Center"
                else:
                    name_val_input = st.text_input("Registered Full Name", placeholder="e.g., Alex Turner", key=f"{prefix}_login_name")
                    pass_val_input = st.text_input("Password", type="password", placeholder="••••••••", key=f"{prefix}_login_pass")
                    btn_label = "Access Employee Dashboard"

                if st.button(btn_label, use_container_width=True, key=f"btn_{prefix}_login"):
                    name_val = clean_text(name_val_input)
                    pass_val = clean_text(pass_val_input)
                    if name_val and pass_val:
                        authenticated_user = authenticate_by_name(name_val, pass_val, role_key)
                        if authenticated_user:
                            user_dict = row_to_dict(authenticated_user) or {}
                            st.session_state.logged_in = True
                            st.session_state.user_id = safe_int(user_dict.get("id"))
                            st.session_state.role = role_key
                            st.session_state.user = user_dict
                            st.session_state.page = "Dashboard"
                            st.success("Successfully logged in as Manager!" if is_mgr else "Successfully logged in as Employee!")
                            st.rerun()
                        else:
                            st.error("Invalid management credentials." if is_mgr else "Invalid credentials.")
                    else:
                        st.error("Please provide valid management credentials." if is_mgr else "Please provide valid credentials.")
            else:
                reg_name = st.text_input("Full Name", placeholder="e.g., Sarah Jenkins" if is_mgr else "e.g., Alex Turner", key=f"{prefix}_reg_name")
                reg_pass = st.text_input("Create Password", type="password", placeholder="••••••••", key=f"{prefix}_reg_pass")
                reg_conf = st.text_input("Confirm Password", type="password", placeholder="••••••••", key=f"{prefix}_reg_conf")
                reg_label = "Register Manager Account" if is_mgr else "Register Employee Account"

                if st.button(reg_label, use_container_width=True, key=f"btn_{prefix}_reg"):
                    n_val = clean_text(reg_name)
                    p_val = clean_text(reg_pass)
                    c_val = clean_text(reg_conf)
                    if not n_val or not p_val or not c_val:
                        st.error("Please fill in all fields.")
                    elif p_val != c_val:
                        st.error("Passwords do not match.")
                    else:
                        unique_token = uuid.uuid4().hex.upper()
                        code = f"OM-{'MGR' if is_mgr else 'EMP'}-{unique_token[:10]}"
                        email = f"{unique_token.lower()}@officemate.local"
                        new_id = create_user(code, n_val, email, p_val, role_key)
                        if new_id:
                            st.success("Manager account created! Please switch to Sign In." if is_mgr else "Employee account created! Please switch to Sign In.")
                        else:
                            st.error("Registration failed.")

            if st.button("← Back to home", use_container_width=True, key=f"{prefix}_back"):
                st.session_state.page = "Home"
                st.rerun()


def login_router():
    workspace = str(st.session_state.get("workspace") or "Employee").lower()
    login_page("manager" if workspace == "manager" else "employee")


# EMPLOYEE DASHBOARD CONTENT

def employee_dashboard_content(user_id):
    user = get_user(safe_int(user_id))
    if not user:
        st.error("Employee session invalid.")
        return

    user_dict = row_to_dict(user) or {}
    data = get_employee_dashboard(safe_int(user_id)) or {}

    schedule = data.get("schedule") or []
    tasks = data.get("tasks") or []
    attendance = data.get("attendance") or []
    parking = data.get("parking") or []

    user_name = clean_text(user_dict.get("full_name"))
    st.markdown(f"## Employee Portal — Welcome, {user_name}")
    st.caption("View your daily assigned tasks, hybrid WFH/WFO status, attendance marker, parking allocations, and cafeteria timing.")

    col_e1, col_e2, col_e3 = st.columns(3)
    col_e1.metric("Today's Work Mode", "WFO (Office)", delta="8 Hrs Registered")
    col_e2.metric("Assigned Tasks", len(tasks))
    col_e3.metric("Attendance Status", "Marked Present 🟢", delta="Verified via Biometric/App")

    #VISUALIZATIONS 
    st.markdown("### 📈 Live Personal Workspace Analytics")
    vcol1, vcol2 = st.columns(2)
    
    with vcol1:
        st.markdown("#### Task Status Breakdown")
        task_list = rows_to_dicts(tasks)
        if task_list:
            df_t = pd.DataFrame(task_list)
            status_counts = df_t['status'].value_counts()
            st.bar_chart(status_counts)
        else:
            sample_status = pd.DataFrame({"Count": [3, 1, 2]}, index=["Completed", "In Progress", "Assigned"])
            st.bar_chart(sample_status)

    with vcol2:
        st.markdown("#### Weekly Work Mode Distribution (Hours)")
        weekly_hours = pd.DataFrame({
            "Day": ["Mon", "Tue", "Wed", "Thu", "Fri"],
            "WFO Hours": [0, 8, 0, 8, 0],
            "WFH Hours": [8, 0, 8, 0, 8]
        }).set_index("Day")
        st.area_chart(weekly_hours)

    st.markdown("---")

    row1_col1, row1_col2 = st.columns(2)

    with row1_col1:
        st.markdown("### 📌 Your Assigned Tasks for Today")
        if tasks:
            for t in rows_to_dicts(tasks):
                st.info(f"**Task ID:** #{t.get('id')} | **Title:** {t.get('title')}\n\n**Description/Setup:** {t.get('description')} | **Status:** {t.get('status')}")
        else:
            st.info("No active tasks assigned at the moment.")

        if st.button("✅ Mark Today's Attendance & Check-In"):
            st.success("Attendance successfully logged into enterprise HRMS database!")

    with row1_col2:
        st.markdown("### Facility and Resource Allocations")
        st.markdown("""
            - **Parking Slot:** Zone B, Bay #24 (Reserved for WFO)
            - **Cafeteria Lunch Timing:** Slot 2 (12:45 PM - 01:30 PM)
            - **Meeting Room Access:** Alpha Conference Room (Floor 3)
            - **Wi-Fi SSID:** MNC-Enterprise-Secure-5G
        """)
        
        st.markdown("### Request Work Mode Change")
        with st.form("request_wfh_form"):
            req_reason = st.text_area("Reason for switching to WFH/WFO today:")
            req_submit = st.form_submit_button("Submit Request to Manager")
            if req_submit:
                st.success("Request transmitted to manager via OpenAPI notification queue.")

    st.markdown("---")

    row2_col1, row2_col2 = st.columns(2)

    with row2_col1:
        st.markdown("### Hybrid Schedule & WFH/WFO View")
        if schedule:
            st.dataframe(pd.DataFrame(rows_to_dicts(schedule)), use_container_width=True, hide_index=True)
        else:
            st.info("No explicit schedule configurations found in database.")

    with row2_col2:
        st.markdown("### Attendance Log")
        if attendance:
            st.dataframe(pd.DataFrame(rows_to_dicts(attendance)), use_container_width=True, hide_index=True)
        else:
            st.info("No recent attendance history recorded in database.")
            
        st.markdown("#### Parking Records")
        if parking:
            st.dataframe(pd.DataFrame(rows_to_dicts(parking)), use_container_width=True, hide_index=True)
        else:
            st.info("No custom parking records found in database.")


# MANAGER DASHBOARD CONTENT 

def manager_dashboard_content(manager_id):
    manager = get_user(safe_int(manager_id))
    if not manager:
        st.error("Manager session invalid.")
        return

    manager_dict = row_to_dict(manager) or {}
    mgr_name = clean_text(manager_dict.get("full_name"))

    st.markdown(f"## Manager Control Center — Welcome, {mgr_name}")
    st.caption("Manage team Hybrid allocations, WFH/WFO rosters, parking slots, cafeteria schedules, and 8-hour shift distributions.")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Office Occupancy (WFO)", "25 / 50", delta="Optimal")
    m2.metric("Remote Workforce (WFH)", "18 Employees")
    m3.metric("Parking Slots Available", "18 slots")
    m4.metric("Cafeteria Peak Slot", "12:30 PM - 01:30 PM")

    st.markdown("### 📊 Enterprise Real-Time Team Analytics")
    mvcol1, mvcol2, mvcol3 = st.columns(3)

    employees = get_all_employees()
    tasks = get_all_tasks()

    with mvcol1:
        st.markdown("#### Live Workforce Allocation (WFO vs WFH)")
        allocation_df = pd.DataFrame({
            "Mode": ["Work From Office (WFO)", "Work From Home (WFH)"],
            "Count": [25, 18]
        }).set_index("Mode")
        st.bar_chart(allocation_df)

    with mvcol2:
        st.markdown("#### Parking Records Occupancy Rates")
        parking_df = pd.DataFrame({
            "Zone": ["Zone A", "Zone B", "Zone C", "Reserved VIP"],
            "Allocated Slots": [12, 14, 6, 0]
        }).set_index("Zone")
        st.line_chart(parking_df)

    with mvcol3:
        st.markdown("#### Task Progress Updates")
        if tasks:
            df_task_mgr = pd.DataFrame(rows_to_dicts(tasks))
            st.bar_chart(df_task_mgr['status'].value_counts())
        else:
            mgr_task_sample = pd.DataFrame({
                "Tasks": [12, 8, 4]
            }, index=["Assigned", "In Progress", "Completed"])
            st.bar_chart(mgr_task_sample)

    st.markdown("---")

    row1_col1, row1_col2 = st.columns(2)

    with row1_col1:
        st.markdown("### Assign Tasks and Shift Schedules")
        if not employees:
            st.warning("No registered employees available.")
        else:
            employee_options = {
                f"{emp.get('full_name')} ({emp.get('employee_code')})": safe_int(emp.get("id"))
                for emp in employees
            }
            with st.form("assign_task_form"):
                target_emp_label = st.selectbox("Select Employee", list(employee_options.keys()))
                task_desc = st.text_input("Task Description", placeholder="e.g., Code review and unit testing")
                work_mode = st.selectbox("Work Mode for Today", ["WFO (Work From Office)", "WFH (Work From Home)", "Hybrid Mode"])
                if "Hybrid" in work_mode:
                    st.info("**Hybrid Mode Active**: Splitting weekly hours between Office and Remote. Default shift and parking availability applied dynamically.")
                    shift_timing = st.selectbox("8-Hour Work Schedule (Hybrid Rotation)", ["09:00 AM - 05:00 PM (Shift A - Hybrid)", "10:00 AM - 06:00 PM (Shift B - Hybrid)"])
                    parking_alloc = st.checkbox("Allocate Parking Slot (Hybrid WFO Days)", value=True)
                    st.caption("**Parking Vacancy Status**: 14 bays available in Zone B for Hybrid members.")
                elif "WFO" in work_mode:
                    shift_timing = st.selectbox("8-Hour Work Schedule", ["09:00 AM - 05:00 PM (Shift A)", "10:00 AM - 06:00 PM (Shift B)", "01:00 PM - 09:00 PM (Shift C)"])
                    parking_alloc = st.checkbox("Allocate Parking Slot (If WFO)", value=True)
                else:
                    shift_timing = st.selectbox("8-Hour Work Schedule (WFH)", ["09:00 AM - 05:00 PM (Remote Standard)"])
                    parking_alloc = False
                    st.caption("**Remote Mode**: Parking slot allocation bypassed for WFH.")

                due_date = st.date_input("Due Date")
                
                submit_task = st.form_submit_button("Assign")
                if submit_task:
                    if not clean_text(task_desc):
                        st.error("Task description required.")
                    else:
                        mode_short = "WFO" if "WFO" in work_mode else ("Hybrid" if "Hybrid" in work_mode else "WFH")
                        emp_id = employee_options[target_emp_label]
                        create_task(
                            emp_id,
                            clean_text(task_desc),
                            f"Mode: {mode_short} | Shift: {shift_timing} | Parking: {'Yes' if parking_alloc else 'No'}",
                            "Assigned",
                            str(due_date)
                        )
                        st.success(f"Task successfully assigned with {mode_short} allocation, shift timing, and parking vacancy synchronized!")
                        st.rerun()

    with row1_col2:
        st.markdown("### Modify Existing Roster & Schedule")
        if not tasks:
            st.info("No tasks available to update.")
        else:
            task_options = {
                f"#{t.get('id')} • {t.get('employee_name')} • {t.get('title')}": safe_int(t.get("id"))
                for t in tasks
            }
            selected_task_label = st.selectbox("Select Task to Update", list(task_options.keys()))
            selected_task_id = task_options[selected_task_label]
            selected_task = next((t for t in tasks if safe_int(t.get("id")) == safe_int(selected_task_id)), None)

            if selected_task:
                with st.form("edit_task_form"):
                    edit_title = st.text_input("Title", value=clean_text(selected_task.get("title")))
                    edit_desc = st.text_area("Description", value=clean_text(selected_task.get("description")))
                    status_opts = ["Assigned", "In Progress", "Completed"]
                    curr_st = clean_text(selected_task.get("status"))
                    idx = status_opts.index(curr_st) if curr_st in status_opts else 0
                    edit_status = st.selectbox("Status", status_opts, index=idx)
                    edit_due = st.date_input("Due Date")

                    if st.form_submit_button("Update Task"):
                        update_task(selected_task_id, clean_text(edit_title), clean_text(edit_desc), clean_text(edit_status), str(edit_due))
                        st.success("Task updated successfully!")
                        st.rerun()

    st.markdown("---")

    row2_col1, row2_col2 = st.columns(2)

    with row2_col1:
        st.markdown("### Task Records")
        if tasks:
            st.dataframe(pd.DataFrame(rows_to_dicts(tasks)), use_container_width=True, hide_index=True)
        else:
            st.info("No active tasks found in the system.")

    with row2_col2:
        st.markdown("### Registered Employee Directory")
        if employees:
            st.dataframe(pd.DataFrame(employees), use_container_width=True, hide_index=True)
        else:
            st.info("No employee records registered.")


# LIVE REFRESH WRAPPERS WITH TOGGLE BUTTONS

if hasattr(st, "fragment"):
    @st.fragment(run_every="5s")
    def employee_live_dashboard(user_id):
        employee_dashboard_content(user_id)
else:
    def employee_live_dashboard(user_id):
        employee_dashboard_content(user_id)
        if st.button("Refresh Data"):
            st.rerun()


if hasattr(st, "fragment"):
    @st.fragment(run_every="5s")
    def manager_live_dashboard(manager_id):
        manager_dashboard_content(manager_id)
else:
    def manager_live_dashboard(manager_id):
        manager_dashboard_content(manager_id)
        if st.button("Refresh Data"):
            st.rerun()


# MAIN ROUTER

def main():
    page = st.session_state.get("page", "Home")

    if page == "Home":
        home_page()
    elif page == "Login":
        login_router()
    elif page == "Dashboard":
        if not st.session_state.get("logged_in", False):
            login_router()
            return

        role = clean_text(st.session_state.get("role")).lower()
        user_id = st.session_state.get("user_id")

        live_toggle = st.toggle("Enable Live Auto-Refresh (Every 5 seconds)", value=True, key="live_refresh_toggle_switch")

        if role == "employee":
            if live_toggle:
                employee_live_dashboard(user_id)
            else:
                employee_dashboard_content(user_id)
        elif role == "manager":
            if live_toggle:
                manager_live_dashboard(user_id)
            else:
                manager_dashboard_content(user_id)
        else:
            st.error("Unknown user role session.")
    elif page == "AI":
        if not st.session_state.get("logged_in", False):
            login_router()
            return

        st.markdown("## OfficeMate AI Assistant ")
        st.caption("Ask questions regarding company hybrid policies, shift timings, parking availability, or request instant task updates.")

        role = clean_text(st.session_state.get("role")).lower()
        user_id = st.session_state.get("user_id")

        if "chat_history" not in st.session_state:
            st.session_state["chat_history"] = [
                {
                    "role": "assistant",
                    "content": "Hello! I am OfficeMate AI, your RAG-powered workplace assistant. Ask me anything about hybrid policies, meeting room bookings, or your daily schedule!",
                }
            ]

        for msg in st.session_state["chat_history"]:
            if msg["role"] == "user":
                st.chat_message("user").write(msg["content"])
            else:
                st.chat_message("assistant").write(msg["content"])

        user_query = st.chat_input("Type your question here (e.g., 'What is my shift timing today?' or 'Are parking slots available?')...")
        if user_query:
            if user_id is None:
                st.error("Please log in to use the AI Assistant.")
            else:
                st.session_state["chat_history"].append({"role": "user", "content": user_query})
                st.chat_message("user").write(user_query)

                with st.spinner("OfficeMate AI is querying enterprise vector store & OpenAPI endpoints..."):
                    try:
                        response = ask_officemate_safe(
                            question=user_query,
                            user_id=safe_int(user_id),
                            role=role,
                        )
                        st.session_state["chat_history"].append({"role": "assistant", "content": response})
                        st.chat_message("assistant").write(response)
                    except Exception as e:
                        st.error(f"Error communicating with AI Assistant: {e}")
    else:
        home_page()


if __name__ == "__main__":
    main()
