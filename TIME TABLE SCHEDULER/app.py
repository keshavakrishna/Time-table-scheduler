"""
Multi-Department Timetable Scheduler
=====================================
Streamlit web app using Google OR-Tools CP-SAT solver for automated,
conflict-free timetable generation across multiple departments.
"""

import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
from collections import defaultdict
import time as _time

# ═══════════════════════════════════════════════════════════════════
#  PAGE CONFIG & CONSTANTS
# ═══════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Timetable Scheduler",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded",
)

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

TIME_SLOTS = [
    "9:00 – 10:00",
    "10:00 – 11:00",
    "11:00 – 12:00",
    "1:00 – 2:00",
    "2:00 – 3:00",
    "3:00 – 4:00",
]

DEPT_STYLES = {
    "Computer Science": {"bg": "#D4E6F1", "border": "#2980B9", "icon": "💻"},
    "Mechanical":       {"bg": "#FAE5D3", "border": "#D35400", "icon": "⚙️"},
    "Electrical":       {"bg": "#D4EFDF", "border": "#1E8449", "icon": "⚡"},
}
_FALLBACK = {"bg": "#F2F3F4", "border": "#7F8C8D", "icon": "📘"}


def _sty(dept: str) -> dict:
    """Return colour/icon style dict for a department."""
    return DEPT_STYLES.get(dept, _FALLBACK)


# ═══════════════════════════════════════════════════════════════════
#  CUSTOM CSS  (injected once)
# ═══════════════════════════════════════════════════════════════════

st.markdown(
    """
<style>
/* ── timetable grid ── */
.tt{border-collapse:collapse;width:100%;font-family:'Segoe UI',system-ui,
    -apple-system,sans-serif;font-size:.84rem;margin:.6rem 0}
.tt th{background:linear-gradient(135deg,#2C3E50,#34495E);color:#ecf0f1;
    padding:11px 6px;text-align:center;font-weight:600;border:1px solid #243342;
    text-transform:uppercase;letter-spacing:.5px;font-size:.74rem}
.tt td{padding:4px;border:1px solid #e0e3e5;vertical-align:top;
    background:#fafbfc;min-width:150px}
.tt tr:nth-child(even) td{background:#f4f6f7}
.slot-hdr{background:linear-gradient(135deg,#34495E,#2C3E50)!important;
    color:#ecf0f1!important;font-weight:600;text-align:center;
    min-width:112px!important;font-size:.78rem}
.card{border-radius:7px;padding:7px 9px;margin:2px 0;line-height:1.35;
    box-shadow:0 1px 3px rgba(0,0,0,.07);transition:transform .12s ease}
.card:hover{transform:scale(1.02);box-shadow:0 2px 8px rgba(0,0,0,.14)}
.card-title{font-weight:700;font-size:.82rem;margin-bottom:2px}
.card-sub{font-size:.71rem;opacity:.82}
.empty{color:#ccd1d1;text-align:center;padding:18px 0;font-size:.78rem}
/* ── misc ── */
.legend-chip{display:inline-block;padding:3px 10px;border-radius:12px;
    margin:0 4px 4px 0;font-size:.76rem;font-weight:600}
</style>
""",
    unsafe_allow_html=True,
)


# ═══════════════════════════════════════════════════════════════════
#  SAMPLE DATA LOADER
# ═══════════════════════════════════════════════════════════════════

def load_sample_data():
    """Populate session-state with realistic demo data for 3 departments."""

    st.session_state["departments"] = [
        "Computer Science",
        "Mechanical",
        "Electrical",
    ]

    st.session_state["rooms"] = pd.DataFrame(
        [
            {"Name": "CR-101",   "Type": "Classroom", "Capacity": 60, "Department": "Shared"},
            {"Name": "CR-102",   "Type": "Classroom", "Capacity": 60, "Department": "Shared"},
            {"Name": "CR-103",   "Type": "Classroom", "Capacity": 45, "Department": "Shared"},
            {"Name": "CR-104",   "Type": "Classroom", "Capacity": 45, "Department": "Shared"},
            {"Name": "CS-Lab-1", "Type": "Lab",       "Capacity": 30, "Department": "Computer Science"},
            {"Name": "CS-Lab-2", "Type": "Lab",       "Capacity": 30, "Department": "Computer Science"},
            {"Name": "ME-Lab",   "Type": "Lab",       "Capacity": 30, "Department": "Mechanical"},
            {"Name": "EE-Lab",   "Type": "Lab",       "Capacity": 30, "Department": "Electrical"},
        ]
    )

    st.session_state["faculty"] = pd.DataFrame(
        [
            {"Name": "Dr. Sharma", "Department": "Computer Science"},
            {"Name": "Dr. Patel",  "Department": "Computer Science"},
            {"Name": "Dr. Kumar",  "Department": "Computer Science"},
            {"Name": "Dr. Singh",  "Department": "Mechanical"},
            {"Name": "Dr. Gupta",  "Department": "Mechanical"},
            {"Name": "Dr. Rao",    "Department": "Electrical"},
            {"Name": "Dr. Verma",  "Department": "Electrical"},
            {"Name": "Dr. Joshi",  "Department": "Shared"},
        ]
    )

    st.session_state["courses"] = pd.DataFrame(
        [
            # ── Computer Science ─────────────────────────────────
            {"Name": "Data Structures",   "Department": "Computer Science",
             "Hours/Week": 4, "Room Type": "Classroom", "Faculty": "Dr. Sharma"},
            {"Name": "Algorithms",        "Department": "Computer Science",
             "Hours/Week": 3, "Room Type": "Classroom", "Faculty": "Dr. Patel"},
            {"Name": "Database Systems",  "Department": "Computer Science",
             "Hours/Week": 3, "Room Type": "Classroom", "Faculty": "Dr. Kumar"},
            {"Name": "Programming Lab",   "Department": "Computer Science",
             "Hours/Week": 2, "Room Type": "Lab",       "Faculty": "Dr. Sharma"},
            {"Name": "Operating Systems", "Department": "Computer Science",
             "Hours/Week": 3, "Room Type": "Classroom", "Faculty": "Dr. Patel"},
            {"Name": "Engg. Maths I",     "Department": "Computer Science",
             "Hours/Week": 2, "Room Type": "Classroom", "Faculty": "Dr. Joshi"},
            # ── Mechanical ───────────────────────────────────────
            {"Name": "Thermodynamics",    "Department": "Mechanical",
             "Hours/Week": 4, "Room Type": "Classroom", "Faculty": "Dr. Singh"},
            {"Name": "Fluid Mechanics",   "Department": "Mechanical",
             "Hours/Week": 3, "Room Type": "Classroom", "Faculty": "Dr. Gupta"},
            {"Name": "Workshop Practice", "Department": "Mechanical",
             "Hours/Week": 2, "Room Type": "Lab",       "Faculty": "Dr. Singh"},
            {"Name": "Machine Design",    "Department": "Mechanical",
             "Hours/Week": 3, "Room Type": "Classroom", "Faculty": "Dr. Gupta"},
            {"Name": "Engg. Maths II",    "Department": "Mechanical",
             "Hours/Week": 2, "Room Type": "Classroom", "Faculty": "Dr. Joshi"},
            # ── Electrical ───────────────────────────────────────
            {"Name": "Circuit Theory",    "Department": "Electrical",
             "Hours/Week": 4, "Room Type": "Classroom", "Faculty": "Dr. Rao"},
            {"Name": "Signals & Systems", "Department": "Electrical",
             "Hours/Week": 3, "Room Type": "Classroom", "Faculty": "Dr. Verma"},
            {"Name": "Electronics Lab",   "Department": "Electrical",
             "Hours/Week": 2, "Room Type": "Lab",       "Faculty": "Dr. Rao"},
            {"Name": "Power Systems",     "Department": "Electrical",
             "Hours/Week": 3, "Room Type": "Classroom", "Faculty": "Dr. Verma"},
            {"Name": "Engg. Maths III",   "Department": "Electrical",
             "Hours/Week": 2, "Room Type": "Classroom", "Faculty": "Dr. Joshi"},
        ]
    )

    st.session_state["batches"] = pd.DataFrame(
        [
            {"Name": "CS-A", "Department": "Computer Science", "Strength": 55},
            {"Name": "CS-B", "Department": "Computer Science", "Strength": 55},
            {"Name": "ME-A", "Department": "Mechanical",       "Strength": 50},
            {"Name": "EE-A", "Department": "Electrical",       "Strength": 48},
        ]
    )

    # Purge stale widget / result state so the UI reinitialises cleanly
    for key in [
        "rooms_editor", "faculty_editor", "courses_editor", "batches_editor",
        "timetable", "solve_error", "solve_stats",
    ]:
        st.session_state.pop(key, None)


# ═══════════════════════════════════════════════════════════════════
#  CONSTRAINT SOLVER  (Google OR-Tools CP-SAT)
# ═══════════════════════════════════════════════════════════════════

def solve_timetable():
    """
    Build a CP-SAT model from the current session-state data and solve it.

    Returns
    -------
    (pd.DataFrame, dict)  on success   – (results, statistics)
    (None, str)            on failure   – (None, error message)
    """

    rooms_df   = st.session_state.get("rooms",   pd.DataFrame())
    faculty_df = st.session_state.get("faculty", pd.DataFrame())
    courses_df = st.session_state.get("courses", pd.DataFrame())
    batches_df = st.session_state.get("batches", pd.DataFrame())

    # ── input validation ─────────────────────────────────────────
    for label, df in [
        ("Rooms", rooms_df), ("Faculty", faculty_df),
        ("Courses", courses_df), ("Batches", batches_df),
    ]:
        if df.empty:
            return None, f"**{label}** data is empty. Load sample data or add entries in the sidebar."

    courses_df = courses_df.dropna(subset=["Name", "Department", "Hours/Week", "Faculty"])
    batches_df = batches_df.dropna(subset=["Name", "Department"])
    rooms_df   = rooms_df.dropna(subset=["Name", "Type"])

    if courses_df.empty:
        return None, "All course rows have missing fields. Fill in Name, Department, Hours/Week, and Faculty."
    if batches_df.empty:
        return None, "All batch rows have missing fields. Fill in Name and Department."

    # Warn about faculty mismatches (non-fatal)
    known_fac  = set(faculty_df["Name"].dropna())
    course_fac = set(courses_df["Faculty"].dropna())
    unknown    = course_fac - known_fac
    if unknown:
        st.warning(
            f"Faculty in courses but not in the faculty list: **{', '.join(unknown)}**. "
            "The solver will still run, but double-check spellings."
        )

    N_DAYS  = len(DAYS)
    N_SLOTS = len(TIME_SLOTS)

    # ── build session list ───────────────────────────────────────
    sessions = []
    for _, c in courses_df.iterrows():
        dept = c["Department"]
        matching = batches_df[batches_df["Department"] == dept]
        for _, b in matching.iterrows():
            for _ in range(int(c["Hours/Week"])):
                sessions.append(
                    {
                        "id":      len(sessions),
                        "course":  c["Name"],
                        "batch":   b["Name"],
                        "faculty": c["Faculty"],
                        "dept":    dept,
                        "rtype":   c["Room Type"],
                    }
                )

    if not sessions:
        return None, (
            "No sessions were generated. Make sure at least one course and "
            "one batch share the same department."
        )

    # ── compatible rooms per session ─────────────────────────────
    all_rooms = rooms_df.to_dict("records")
    compat: dict[int, list[dict]] = {}

    for s in sessions:
        if s["rtype"] == "Lab":
            ok = [
                r for r in all_rooms
                if r["Type"] == "Lab"
                and r.get("Department") in (s["dept"], "Shared")
            ]
        else:
            ok = [r for r in all_rooms if r["Type"] == "Classroom"]

        if not ok:
            return None, (
                f"No compatible **{s['rtype']}** room for course "
                f"*{s['course']}* (dept: {s['dept']}). Add more rooms."
            )
        compat[s["id"]] = ok

    # ── build CP-SAT model ───────────────────────────────────────
    model = cp_model.CpModel()

    # Decision variables:  x[session, day, slot, room] ∈ {0, 1}
    x: dict[tuple, object] = {}
    for s in sessions:
        for d in range(N_DAYS):
            for t in range(N_SLOTS):
                for r in compat[s["id"]]:
                    x[s["id"], d, t, r["Name"]] = model.NewBoolVar(
                        f'x_{s["id"]}_{d}_{t}_{r["Name"]}'
                    )

    # ── HARD CONSTRAINTS ─────────────────────────────────────────

    # (H1) Each session is assigned to exactly one (day, slot, room)
    for s in sessions:
        model.Add(
            sum(
                x[s["id"], d, t, r["Name"]]
                for d in range(N_DAYS)
                for t in range(N_SLOTS)
                for r in compat[s["id"]]
            )
            == 1
        )

    # (H2) No room double-booking
    for d in range(N_DAYS):
        for t in range(N_SLOTS):
            for r in all_rooms:
                vs = [
                    x[key]
                    for key in (
                        (s["id"], d, t, r["Name"]) for s in sessions
                    )
                    if key in x
                ]
                if len(vs) > 1:
                    model.Add(sum(vs) <= 1)

    # (H3) No faculty double-booking
    fac_sessions: dict[str, list] = defaultdict(list)
    for s in sessions:
        fac_sessions[s["faculty"]].append(s)

    for _f, fs in fac_sessions.items():
        for d in range(N_DAYS):
            for t in range(N_SLOTS):
                vs = [
                    x[key]
                    for s in fs
                    for r in compat[s["id"]]
                    if (key := (s["id"], d, t, r["Name"])) in x
                ]
                if len(vs) > 1:
                    model.Add(sum(vs) <= 1)

    # (H4) No student-batch double-booking
    bat_sessions: dict[str, list] = defaultdict(list)
    for s in sessions:
        bat_sessions[s["batch"]].append(s)

    for _b, bs in bat_sessions.items():
        for d in range(N_DAYS):
            for t in range(N_SLOTS):
                vs = [
                    x[key]
                    for s in bs
                    for r in compat[s["id"]]
                    if (key := (s["id"], d, t, r["Name"])) in x
                ]
                if len(vs) > 1:
                    model.Add(sum(vs) <= 1)

    # ── SOFT CONSTRAINTS (optimisation) ──────────────────────────
    penalties = []

    # (S1) Even daily load per batch
    for _b, bs in bat_sessions.items():
        ideal_max = -(-len(bs) // N_DAYS)  # ceil division
        for d in range(N_DAYS):
            cnt = model.NewIntVar(0, N_SLOTS, f"bcnt_{_b}_{d}")
            model.Add(
                cnt
                == sum(
                    x[key]
                    for s in bs
                    for t in range(N_SLOTS)
                    for r in compat[s["id"]]
                    if (key := (s["id"], d, t, r["Name"])) in x
                )
            )
            exc = model.NewIntVar(0, N_SLOTS, f"bexc_{_b}_{d}")
            model.Add(exc >= cnt - ideal_max)
            penalties.append(exc)

    # (S2) Even daily load per faculty
    for _f, fs in fac_sessions.items():
        ideal_max = -(-len(fs) // N_DAYS)
        for d in range(N_DAYS):
            cnt = model.NewIntVar(0, N_SLOTS, f"fcnt_{_f}_{d}")
            model.Add(
                cnt
                == sum(
                    x[key]
                    for s in fs
                    for t in range(N_SLOTS)
                    for r in compat[s["id"]]
                    if (key := (s["id"], d, t, r["Name"])) in x
                )
            )
            exc = model.NewIntVar(0, N_SLOTS, f"fexc_{_f}_{d}")
            model.Add(exc >= cnt - ideal_max)
            penalties.append(exc)

    has_objective = bool(penalties)
    if has_objective:
        model.Minimize(sum(penalties))

    # ── solve ────────────────────────────────────────────────────
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30

    t0 = _time.perf_counter()
    status = solver.Solve(model)
    elapsed = _time.perf_counter() - t0

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        tips = "\n".join(
            [
                "• Reduce **Hours/Week** for some courses.",
                "• Add more classrooms or labs.",
                "• Split large batches into smaller groups.",
                "• Reassign shared faculty who may be overloaded.",
                "• Temporarily remove a department to reduce contention.",
            ]
        )
        return None, (
            "**⚠️ No feasible timetable found** — the constraints are too tight.\n\n"
            f"**Suggestions to resolve:**\n{tips}"
        )

    # ── extract solution ─────────────────────────────────────────
    rows = []
    for s in sessions:
        for d in range(N_DAYS):
            for t in range(N_SLOTS):
                for r in compat[s["id"]]:
                    key = (s["id"], d, t, r["Name"])
                    if key in x and solver.Value(x[key]):
                        rows.append(
                            {
                                "Department": s["dept"],
                                "Course":     s["course"],
                                "Batch":      s["batch"],
                                "Faculty":    s["faculty"],
                                "Day":        DAYS[d],
                                "Time Slot":  TIME_SLOTS[t],
                                "Room":       r["Name"],
                                "day_i":      d,
                                "slot_i":     t,
                            }
                        )

    result_df = pd.DataFrame(rows)
    stats = {
        "sessions": len(result_df),
        "status":   "Optimal" if status == cp_model.OPTIMAL else "Feasible",
        "time":     round(elapsed, 2),
        "penalty":  int(solver.ObjectiveValue()) if has_objective else 0,
    }
    return result_df, stats


# ═══════════════════════════════════════════════════════════════════
#  TIMETABLE GRID RENDERER
# ═══════════════════════════════════════════════════════════════════

def render_grid(df: pd.DataFrame) -> None:
    """Render a colour-coded weekly HTML grid from the timetable DataFrame."""
    if df.empty:
        st.info("No sessions match this filter.")
        return

    html = '<table class="tt"><tr><th style="min-width:112px">Time ╲ Day</th>'
    for day in DAYS:
        html += f"<th>{day}</th>"
    html += "</tr>"

    for si, slot in enumerate(TIME_SLOTS):
        html += f'<tr><td class="slot-hdr">{slot}</td>'
        for di in range(len(DAYS)):
            cell = df[(df["day_i"] == di) & (df["slot_i"] == si)]
            if cell.empty:
                html += '<td><div class="empty">—</div></td>'
            else:
                html += "<td>"
                for _, row in cell.iterrows():
                    s = _sty(row["Department"])
                    html += (
                        f'<div class="card" style="background:{s["bg"]};'
                        f'border-left:4px solid {s["border"]}">'
                        f'<div class="card-title">{s["icon"]} {row["Course"]}</div>'
                        f'<div class="card-sub">👥 {row["Batch"]}  ·  🏫 {row["Room"]}</div>'
                        f'<div class="card-sub">👤 {row["Faculty"]}</div>'
                        "</div>"
                    )
                html += "</td>"
        html += "</tr>"

    html += "</table>"
    st.markdown(html, unsafe_allow_html=True)


def render_legend() -> None:
    """Show a small department colour legend."""
    chips = ""
    for dept, s in DEPT_STYLES.items():
        chips += (
            f'<span class="legend-chip" style="background:{s["bg"]};'
            f'border:1px solid {s["border"]};color:{s["border"]}">'
            f'{s["icon"]} {dept}</span>'
        )
    st.markdown(chips, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
#  SIDEBAR  (input data management)
# ═══════════════════════════════════════════════════════════════════

def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")

        # ── action buttons ───────────────────────────────────────
        if st.button("📋  Load Sample Data", use_container_width=True, type="primary"):
            load_sample_data()
            st.rerun()

        if st.button("🗑️  Reset All Data", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

        st.divider()

        dept_opts = st.session_state.get("departments", [])

        # ── departments ──────────────────────────────────────────
        with st.expander("🏛️ Departments", expanded=False):
            if dept_opts:
                for dept in dept_opts:
                    c1, c2 = st.columns([5, 1])
                    c1.markdown(f"**{dept}**")
                    if c2.button("✕", key=f"del_dept_{dept}"):
                        dept_opts.remove(dept)
                        st.session_state["departments"] = dept_opts
                        st.rerun()
            else:
                st.caption("No departments yet.")

            new_dept = st.text_input("New department name", key="inp_new_dept")
            if st.button("➕ Add Department", key="btn_add_dept"):
                if new_dept and new_dept not in dept_opts:
                    dept_opts.append(new_dept)
                    st.session_state["departments"] = dept_opts
                    st.rerun()

        # ── rooms & labs ─────────────────────────────────────────
        with st.expander("🏫 Rooms & Labs", expanded=False):
            rdf = st.session_state.get(
                "rooms",
                pd.DataFrame(columns=["Name", "Type", "Capacity", "Department"]),
            )
            edited = st.data_editor(
                rdf,
                num_rows="dynamic",
                key="rooms_editor",
                use_container_width=True,
                column_config={
                    "Type": st.column_config.SelectboxColumn(
                        options=["Classroom", "Lab"]
                    ),
                    "Department": st.column_config.SelectboxColumn(
                        options=["Shared"] + dept_opts
                    ),
                    "Capacity": st.column_config.NumberColumn(
                        min_value=1, max_value=500, step=1
                    ),
                },
            )
            st.session_state["rooms"] = edited

        # ── faculty ──────────────────────────────────────────────
        with st.expander("👤 Faculty", expanded=False):
            fdf = st.session_state.get(
                "faculty",
                pd.DataFrame(columns=["Name", "Department"]),
            )
            edited = st.data_editor(
                fdf,
                num_rows="dynamic",
                key="faculty_editor",
                use_container_width=True,
                column_config={
                    "Department": st.column_config.SelectboxColumn(
                        options=["Shared"] + dept_opts
                    ),
                },
            )
            st.session_state["faculty"] = edited

        # ── courses ──────────────────────────────────────────────
        with st.expander("📚 Courses", expanded=False):
            cdf = st.session_state.get(
                "courses",
                pd.DataFrame(
                    columns=["Name", "Department", "Hours/Week", "Room Type", "Faculty"]
                ),
            )
            fac_names = list(
                st.session_state.get("faculty", pd.DataFrame())
                .get("Name", pd.Series(dtype=str))
                .dropna()
            )
            edited = st.data_editor(
                cdf,
                num_rows="dynamic",
                key="courses_editor",
                use_container_width=True,
                column_config={
                    "Department": st.column_config.SelectboxColumn(
                        options=dept_opts
                    ),
                    "Room Type": st.column_config.SelectboxColumn(
                        options=["Classroom", "Lab"]
                    ),
                    "Faculty": st.column_config.SelectboxColumn(
                        options=fac_names
                    ),
                    "Hours/Week": st.column_config.NumberColumn(
                        min_value=1, max_value=6, step=1
                    ),
                },
            )
            st.session_state["courses"] = edited

        # ── batches ──────────────────────────────────────────────
        with st.expander("👥 Batches", expanded=False):
            bdf = st.session_state.get(
                "batches",
                pd.DataFrame(columns=["Name", "Department", "Strength"]),
            )
            edited = st.data_editor(
                bdf,
                num_rows="dynamic",
                key="batches_editor",
                use_container_width=True,
                column_config={
                    "Department": st.column_config.SelectboxColumn(
                        options=dept_opts
                    ),
                    "Strength": st.column_config.NumberColumn(
                        min_value=1, max_value=300, step=1
                    ),
                },
            )
            st.session_state["batches"] = edited

        # ── summary stats ────────────────────────────────────────
        if dept_opts:
            st.divider()
            st.markdown("### 📊 Data Summary")
            n_rooms   = len(st.session_state.get("rooms",   pd.DataFrame()))
            n_fac     = len(st.session_state.get("faculty", pd.DataFrame()))
            n_courses = len(st.session_state.get("courses", pd.DataFrame()))
            n_batches = len(st.session_state.get("batches", pd.DataFrame()))
            st.markdown(
                f"**{len(dept_opts)}** departments  ·  **{n_rooms}** rooms  ·  "
                f"**{n_fac}** faculty\n\n"
                f"**{n_courses}** courses  ·  **{n_batches}** batches"
            )


# ═══════════════════════════════════════════════════════════════════
#  MAIN PAGE
# ═══════════════════════════════════════════════════════════════════

def main():
    render_sidebar()

    # ── header ───────────────────────────────────────────────────
    st.markdown("# 📅 Multi-Department Timetable Scheduler")
    st.caption(
        "Constraint-based scheduling powered by **Google OR-Tools CP-SAT**.  "
        "Configure data in the sidebar ➜ click **Generate Timetable**."
    )

    # ── generate button ──────────────────────────────────────────
    if st.button("🚀  Generate Timetable", type="primary"):
        with st.spinner("Building model & solving constraints … this may take up to 30 s"):
            try:
                result, info = solve_timetable()
            except Exception as exc:
                result, info = None, f"**Unexpected solver error:** `{exc}`"

        if isinstance(info, str):
            # error path
            st.session_state.pop("timetable", None)
            st.session_state.pop("solve_stats", None)
            st.session_state["solve_error"] = info
        else:
            # success path
            st.session_state["timetable"]   = result
            st.session_state["solve_stats"] = info
            st.session_state.pop("solve_error", None)
            st.toast("✅ Timetable generated!", icon="🎉")

    # ── error banner ─────────────────────────────────────────────
    if "solve_error" in st.session_state:
        st.error(st.session_state["solve_error"])

    # ── nothing generated yet ────────────────────────────────────
    if "timetable" not in st.session_state:
        st.info(
            "👈 **Step 1:** Click *Load Sample Data* in the sidebar.  \n"
            "**Step 2:** Click *Generate Timetable* above."
        )
        return

    df    = st.session_state["timetable"]
    stats = st.session_state.get("solve_stats", {})

    # ── solver metrics ───────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Sessions Scheduled", stats.get("sessions", len(df)))
    m2.metric("Solver Status",      stats.get("status", "—"))
    m3.metric("Solve Time",         f'{stats.get("time", 0):.2f} s')
    m4.metric("Soft Penalty",       stats.get("penalty", 0))

    st.divider()

    # ── colour legend ────────────────────────────────────────────
    render_legend()

    # ── filter controls ──────────────────────────────────────────
    view = st.radio(
        "📋 View timetable by",
        ["Department", "Batch", "Faculty", "Room / Lab"],
        horizontal=True,
    )

    if view == "Department":
        opts = sorted(df["Department"].unique())
        sel  = st.selectbox("Select department", opts)
        render_grid(df[df["Department"] == sel])

    elif view == "Batch":
        opts = sorted(df["Batch"].unique())
        sel  = st.selectbox("Select student batch", opts)
        render_grid(df[df["Batch"] == sel])

    elif view == "Faculty":
        opts = sorted(df["Faculty"].unique())
        sel  = st.selectbox("Select faculty member", opts)
        render_grid(df[df["Faculty"] == sel])

    else:  # Room / Lab
        opts = sorted(df["Room"].unique())
        sel  = st.selectbox("Select room / lab", opts)
        render_grid(df[df["Room"] == sel])

    # ── CSV export ───────────────────────────────────────────────
    st.divider()
    export_df = df.drop(columns=["day_i", "slot_i"])
    csv_data  = export_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="📥  Download Full Timetable (CSV)",
        data=csv_data,
        file_name="timetable.csv",
        mime="text/csv",
    )

    # ── raw data preview ─────────────────────────────────────────
    with st.expander("🔍 Raw Data Preview", expanded=False):
        st.dataframe(export_df, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    main()
