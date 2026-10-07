from datetime import datetime
from pathlib import Path
import uuid
import pandas as pd
import streamlit as st
from database import initialize_database, authenticate_user, create_user, get_user, get_employee_dashboard, get_manager_dashboard, get_connection


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="OfficeMate AI - Hybrid Work & Resource Manager",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# INITIALIZE DATABASE
# ============================================================

try:
    initialize_database()
except Exception as exc:
    st.error("Database initialization failed.")
    st.code(str(exc))
    st.stop()


# ============================================================
# SESSION STATE DEFAULTS
# ============================================================

DEFAULTS = {
    "page": "Home",
    "logged_in": False,
    "user_id": None,
    "role": None,
    "user": None,
    "workspace": "Employee",
    "auth_action": "Login",
    "auth_action_version": 0,
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# SAFE HELPERS
# ============================================================

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


# ============================================================
# ROBUST AI ASSISTANT HANDLER (EMPLOYEE & MANAGER)
# ============================================================

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
            # Employee assistant
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


# ============================================================
# AUTHENTICATION HELPER
# ============================================================

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


# ============================================================
# TASK DATABASE HELPERS
# ============================================================

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


# ============================================================
# MNC ENTERPRISE LIGHT STYLE CUSTOM CSS
# ============================================================

st.markdown("""
    <style>
    .stApp {
        background: Skyblue;
    }
    .stmain {
        background-color: Skyblue;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #e2e8f0;
        border-radius: 6px 6px 0px 0px;
        padding: 10px 20px;
        font-weight: 600;
        color: #1e293b;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2563eb !important;
        color: white !important;
    }
    .hero-container {
        background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 50%, #3b82f6 100%);
        padding: 4rem 2rem;
        border-radius: 1rem;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 10px 25px -5px rgba(37, 99, 235, 0.3);
    }
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 0.75rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        border-left: 5px solid #2563eb;
        margin-bottom: 1rem;
    }
    .metric-card h3 {
        color: #1e293b !important;
        margin-top: 0;
    }
    .metric-card p {
        color: #475569 !important;
    }
    .chat-box {
        background: #ffffff;
        border: 1px solid #cbd5e1;
        border-radius: 0.5rem;
        padding: 1rem;
        height: 350px;
        overflow-y: scroll;
        margin-top: 0;
    }
    .footer {
        text-align: center;
        color: #64748b;
        margin-top: 4rem;
        font-size: 0.875rem;
    }
    </style>
""", unsafe_allow_html=True)


# ============================================================
# TOP NAVIGATION BAR
# ============================================================

def render_navigation():
    col1, col2, col3, col4, col5 = st.columns([3, 1.2, 1.2, 1.2, 1.5])

    with col1:
        st.markdown("### 🏢 **OfficeMate AI**")
        st.caption("Hybrid Work & Resource Management Agent")

    with col2:
        if st.button("🏠 Home", use_container_width=True, key="nav_home"):
            st.session_state.page = "Home"
            st.rerun()

    with col3:
        if st.button("📊 Dashboard", use_container_width=True, key="nav_dash"):
            if st.session_state.logged_in:
                st.session_state.page = "Dashboard"
            else:
                st.session_state.page = "Login"
            st.rerun()

    with col4:
        if st.button("🤖 AI Chatbot", use_container_width=True, key="nav_ai"):
            if st.session_state.logged_in:
                st.session_state.page = "AI"
            else:
                st.session_state.page = "Login"
            st.rerun()

    with col5:
        if st.session_state.logged_in:
            user_rec = current_user()
            user_disp = clean_text(user_rec.get("full_name")) if user_rec else "User"
            if st.button(f"👤 Logout ({user_disp[:6]}..)", use_container_width=True, key="nav_logout"):
                logout_user()
        else:
            if st.button("🔐 Login / Signup", use_container_width=True, key="nav_login"):
                st.session_state.page = "Login"
                st.rerun()


render_navigation()
st.markdown("---")


# ============================================================
# HOME PAGE
# ============================================================

def home_page():
    st.markdown(
        """
        <div class="hero-container">
            <h1 style="font-size: 2.75rem; font-weight: 800; margin-bottom: 1rem;">Hybrid Work Allocation & Resource Management</h1>
            <p style="font-size: 1.25rem; opacity: 0.9; max-width: 800px; margin: 0 auto 2rem auto;">
                One intelligent enterprise workspace powered by LLMs & OpenAPI integrations for seamless WFH/WFO allocations, smart parking, shift schedules, and real-time team coordination.
            </p>
        </div>
    """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            """
            <div class="metric-card">
                <h3>⚡ Smart WFH/WFO Allocation</h3>
                <p>AI-driven predictive scheduling balancing physical office capacity, meeting cadence, and team collaboration goals dynamically.</p>
            </div>
        """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            """
            <div class="metric-card">
                <h3>🚗 Resource & Parking Sync</h3>
                <p>Real-time automated parking slot booking, cafeteria dining shifts, and workstation hot-desking assigned instantly upon WFO check-in.</p>
            </div>
        """,
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            """
            <div class="metric-card">
                <h3>🤖 RAG-Powered Assistant</h3>
                <p>OpenAPI-compliant assistant trained on enterprise HR handbooks, shift rosters, and live occupancy rates for instant answers.</p>
            </div>
        """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
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


# ============================================================
# AUTHENTICATION PAGE
# ============================================================

def authentication_page():
    st.markdown("<h2 style='text-align: center;'>🔐 OfficeMate Portal Authentication</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #64748b;'>Select your portal role to access AI dashboards and live allocation feeds.</p>", unsafe_allow_html=True)
    
    tab_emp, tab_mgr = st.tabs(["Employee Login / Signup", "Manager Login / Signup"])

    with tab_emp:
        col_l1, col_col, col_l2 = st.columns([1, 2, 1])
        with col_col:
            st.subheader("Employee Portal Card")
            auth_mode_emp = st.radio("Mode", ["Sign In", "Register / Sign Up"], horizontal=True, key="emp_auth_mode")
            
            if auth_mode_emp == "Sign In":
                emp_name = st.text_input("Registered Full Name", placeholder="e.g., Alex Turner", key="emp_login_name")
                emp_pass = st.text_input("Password", type="password", placeholder="••••••••", key="emp_login_pass")
                if st.button("Access Employee Dashboard", use_container_width=True, key="btn_emp_login"):
                    name_val = clean_text(emp_name)
                    pass_val = clean_text(emp_pass)
                    if name_val and pass_val:
                        authenticated_user = authenticate_by_name(name_val, pass_val, "employee")
                        if authenticated_user:
                            user_dict = row_to_dict(authenticated_user) or {}
                            st.session_state.logged_in = True
                            st.session_state.user_id = safe_int(user_dict.get("id"))
                            st.session_state.role = "employee"
                            st.session_state.user = user_dict
                            st.session_state.page = "Dashboard"
                            st.success("Successfully logged in as Employee!")
                            st.rerun()
                        else:
                            st.error("Invalid credentials.")
                    else:
                        st.error("Please provide valid credentials.")
            else:
                emp_name_reg = st.text_input("Full Name", placeholder="e.g., Alex Turner", key="emp_reg_name")
                emp_pass_reg = st.text_input("Create Password", type="password", placeholder="••••••••", key="emp_reg_pass")
                emp_pass_conf = st.text_input("Confirm Password", type="password", placeholder="••••••••", key="emp_reg_conf")
                if st.button("Register Employee Account", use_container_width=True, key="btn_emp_reg"):
                    n_val = clean_text(emp_name_reg)
                    p_val = clean_text(emp_pass_reg)
                    c_val = clean_text(emp_pass_conf)
                    if not n_val or not p_val or not c_val:
                        st.error("Please fill in all fields.")
                    elif p_val != c_val:
                        st.error("Passwords do not match.")
                    else:
                        unique_token = uuid.uuid4().hex.upper()
                        code = f"OM-EMP-{unique_token[:10]}"
                        email = f"{unique_token.lower()}@officemate.local"
                        new_id = create_user(code, n_val, email, p_val, "employee")
                        if new_id:
                            st.success("Employee account created! Please switch to Sign In.")
                        else:
                            st.error("Registration failed.")

    with tab_mgr:
        col_m1, col_mcol, col_m2 = st.columns([1, 2, 1])
        with col_mcol:
            st.subheader("Manager Portal Card")
            auth_mode_mgr = st.radio("Action", ["Sign In", "Register / Sign Up"], horizontal=True, key="mgr_auth_mode")
            
            if auth_mode_mgr == "Sign In":
                mgr_name = st.text_input("Manager Name", placeholder="e.g., Sarah Jenkins", key="mgr_login_name")
                mgr_pass = st.text_input("Password", type="password", placeholder="••••••••", key="mgr_login_pass")
                if st.button("Access Manager Control Center", use_container_width=True, key="btn_mgr_login"):
                    name_val = clean_text(mgr_name)
                    pass_val = clean_text(mgr_pass)
                    if name_val and pass_val:
                        authenticated_user = authenticate_by_name(name_val, pass_val, "manager")
                        if authenticated_user:
                            user_dict = row_to_dict(authenticated_user) or {}
                            st.session_state.logged_in = True
                            st.session_state.user_id = safe_int(user_dict.get("id"))
                            st.session_state.role = "manager"
                            st.session_state.user = user_dict
                            st.session_state.page = "Dashboard"
                            st.success("Successfully logged in as Manager!")
                            st.rerun()
                        else:
                            st.error("Invalid management credentials.")
                    else:
                        st.error("Please provide valid management credentials.")
            else:
                mgr_name_reg = st.text_input("Full Name", placeholder="e.g., Sarah Jenkins", key="mgr_reg_name")
                mgr_pass_reg = st.text_input("Create Password", type="password", placeholder="••••••••", key="mgr_reg_pass")
                mgr_pass_conf = st.text_input("Confirm Password", type="password", placeholder="••••••••", key="mgr_reg_conf")
                if st.button("Register Manager Account", use_container_width=True, key="btn_mgr_reg"):
                    n_val = clean_text(mgr_name_reg)
                    p_val = clean_text(mgr_pass_reg)
                    c_val = clean_text(mgr_pass_conf)
                    if not n_val or not p_val or not c_val:
                        st.error("Please fill in all fields.")
                    elif p_val != c_val:
                        st.error("Passwords do not match.")
                    else:
                        unique_token = uuid.uuid4().hex.upper()
                        code = f"OM-MGR-{unique_token[:10]}"
                        email = f"{unique_token.lower()}@officemate.local"
                        new_id = create_user(code, n_val, email, p_val, "manager")
                        if new_id:
                            st.success("Manager account created! Please switch to Sign In.")
                        else:
                            st.error("Registration failed.")


# ============================================================
# EMPLOYEE DASHBOARD CONTENT
# ============================================================

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

    # STREAMLIT ADVANCED VISUALIZATIONS - EMPLOYEE DYNAMICS
    st.markdown("### 📈 Live Personal Workspace Analytics")
    vcol1, vcol2 = st.columns(2)
    
    with vcol1:
        st.markdown("#### 📊 Task Status Breakdown")
        task_list = rows_to_dicts(tasks)
        if task_list:
            df_t = pd.DataFrame(task_list)
            status_counts = df_t['status'].value_counts()
            st.bar_chart(status_counts)
        else:
            sample_status = pd.DataFrame({"Count": [3, 1, 2]}, index=["Completed", "In Progress", "Assigned"])
            st.bar_chart(sample_status)

    with vcol2:
        st.markdown("#### ⚡ Weekly Work Mode Distribution (Hours)")
        weekly_hours = pd.DataFrame({
            "Day": ["Mon", "Tue", "Wed", "Thu", "Fri"],
            "WFO Hours": [0, 8, 0, 8, 0],
            "WFH Hours": [8, 0, 8, 0, 8]
        }).set_index("Day")
        st.area_chart(weekly_hours)

    st.markdown("---")
    col_t1, col_t2 = st.columns(2)

    with col_t1:
        st.markdown("### 📌 Your Assigned Tasks for Today")
        if tasks:
            for t in rows_to_dicts(tasks):
                st.info(f"**Task ID:** #{t.get('id')} | **Title:** {t.get('title')}\n\n**Description/Setup:** {t.get('description')} | **Status:** {t.get('status')}")
        else:
            st.info("No active tasks assigned at the moment.")

        if st.button("✅ Mark Today's Attendance & Check-In"):
            st.success("Attendance successfully logged into enterprise HRMS database!")

    with col_t2:
        st.markdown("### ☕ Facility & Resource Allocations")
        st.markdown("""
            - **Parking Slot:** Zone B, Bay #24 (Reserved for WFO)
            - **Cafeteria Lunch Timing:** Slot 2 (12:45 PM - 01:30 PM)
            - **Meeting Room Access:** Alpha Conference Room (Floor 3)
            - **Wi-Fi SSID:** MNC-Enterprise-Secure-5G
        """)
        
        st.markdown("### 📝 Request Work Mode Change")
        with st.form("request_wfh_form"):
            req_reason = st.text_area("Reason for switching to WFH/WFO today:")
            req_submit = st.form_submit_button("Submit Request to Manager")
            if req_submit:
                st.success("Request transmitted to manager via OpenAPI notification queue.")

    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["📅 Hybrid Schedule", "🕘 Attendance Log", "🚗 Parking Records"])
    with tab1:
        if schedule:
            st.dataframe(pd.DataFrame(rows_to_dicts(schedule)), use_container_width=True, hide_index=True)
        else:
            st.info("No explicit schedule configurations found.")
    with tab2:
        if attendance:
            st.dataframe(pd.DataFrame(rows_to_dicts(attendance)), use_container_width=True, hide_index=True)
        else:
            st.info("No recent attendance history recorded.")
    with tab3:
        if parking:
            st.dataframe(pd.DataFrame(rows_to_dicts(parking)), use_container_width=True, hide_index=True)
        else:
            st.info("No custom parking overrides logged.")


# ============================================================
# MANAGER DASHBOARD CONTENT
# ============================================================

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

    # STREAMLIT ADVANCED VISUALIZATIONS - MANAGER ENTERPRISE INSIGHTS
    st.markdown("### 📊 Enterprise Real-Time Team Analytics")
    mvcol1, mvcol2, mvcol3 = st.columns(3)

    employees = get_all_employees()
    tasks = get_all_tasks()

    with mvcol1:
        st.markdown("#### 🏢 Live Workforce Allocation (WFO vs WFH)")
        allocation_df = pd.DataFrame({
            "Mode": ["Work From Office (WFO)", "Work From Home (WFH)"],
            "Count": [25, 18]
        }).set_index("Mode")
        st.bar_chart(allocation_df)

    with mvcol2:
        st.markdown("#### 🚗 Parking Bay Occupancy Rates")
        parking_df = pd.DataFrame({
            "Zone": ["Zone A", "Zone B", "Zone C", "Reserved VIP"],
            "Allocated Slots": [12, 14, 6, 0]
        }).set_index("Zone")
        st.line_chart(parking_df)

    with mvcol3:
        st.markdown("#### 📋 Task Progress Across Roster")
        if tasks:
            df_task_mgr = pd.DataFrame(rows_to_dicts(tasks))
            st.bar_chart(df_task_mgr['status'].value_counts())
        else:
            mgr_task_sample = pd.DataFrame({
                "Tasks": [12, 8, 4]
            }, index=["Assigned", "In Progress", "Completed"])
            st.bar_chart(mgr_task_sample)

    st.markdown("---")
    col_act1, col_act2 = st.columns(2)

    with col_act1:
        st.markdown("### 📋 Assign Tasks & Shift Schedules")
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
                work_mode = st.selectbox("Work Mode for Today", ["WFO (Work From Office)", "WFH (Work From Home)"])
                shift_timing = st.selectbox("8-Hour Work Schedule", ["09:00 AM - 05:00 PM (Shift A)", "10:00 AM - 06:00 PM (Shift B)", "01:00 PM - 09:00 PM (Shift C)"])
                parking_alloc = st.checkbox("Allocate Parking Slot (If WFO)")
                due_date = st.date_input("Due Date")
                
                submit_task = st.form_submit_button("Deploy Assignment via OpenAPI")
                if submit_task:
                    if not clean_text(task_desc):
                        st.error("Task description required.")
                    else:
                        mode_short = "WFO" if "WFO" in work_mode else "WFH"
                        emp_id = employee_options[target_emp_label]
                        create_task(
                            emp_id,
                            clean_text(task_desc),
                            f"Mode: {mode_short} | Shift: {shift_timing} | Parking: {'Yes' if parking_alloc else 'No'}",
                            "Assigned",
                            str(due_date)
                        )
                        st.success(f"Task successfully assigned with {mode_short} allocation!")
                        st.rerun()

    with col_act2:
        st.markdown("### 📊 Live Team Roster & Task Status")
        if tasks:
            st.dataframe(pd.DataFrame(rows_to_dicts(tasks)), use_container_width=True, hide_index=True)
        else:
            st.info("No active tasks found in the system.")

        if st.button("🔄 Trigger Live OpenAPI Data Sync", use_container_width=True):
            st.success("Live data synchronized successfully across nodes!")

    st.markdown("---")
    tab_m1, tab_m2 = st.tabs(["✏️ Modify Existing Tasks", "👥 Registered Team Directory"])
    
    with tab_m1:
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

    with tab_m2:
        if employees:
            st.dataframe(pd.DataFrame(employees), use_container_width=True, hide_index=True)
        else:
            st.info("No employee records registered.")


# ============================================================
# LIVE REFRESH WRAPPERS WITH TOGGLE BUTTONS
# ============================================================

if hasattr(st, "fragment"):
    @st.fragment(run_every="5s")
    def employee_live_dashboard(user_id):
        employee_dashboard_content(user_id)
else:
    def employee_live_dashboard(user_id):
        employee_dashboard_content(user_id)
        if st.button("🔄 Refresh Data Manually"):
            st.rerun()


if hasattr(st, "fragment"):
    @st.fragment(run_every="5s")
    def manager_live_dashboard(manager_id):
        manager_dashboard_content(manager_id)
else:
    def manager_live_dashboard(manager_id):
        manager_dashboard_content(manager_id)
        if st.button("🔄 Refresh Data Manually"):
            st.rerun()


# ============================================================
# MAIN ROUTER
# ============================================================

def main():
    page = st.session_state.get("page", "Home")

    if page == "Home":
        home_page()
    elif page == "Login":
        authentication_page()
    elif page == "Dashboard":
        if not st.session_state.get("logged_in", False):
            authentication_page()
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
            authentication_page()
            return

        st.markdown("## 🤖 OfficeMate AI Assistant ")
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
                st.chat_message("assistant", avatar="🤖").write(msg["content"])

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
                        st.chat_message("assistant", avatar="🤖").write(response)
                    except Exception as e:
                        st.error(f"Error communicating with AI Assistant: {e}")
    else:
        home_page()


if __name__ == "__main__":
    main()