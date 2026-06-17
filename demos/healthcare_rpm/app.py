"""
Patient Risk Monitor - ask a question in plain English, get the SQL that answers
it plus the result table. One script per question (multiple questions ->
multiple scripts). Scripts are saved and reusable; reusing one re-runs the SQL
live (no AI tokens).

Run from the repo root:
    streamlit run demos/healthcare_rpm/app.py
"""
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import datetime  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from demos.healthcare_rpm.config import DEFAULT_GOAL, EXAMPLES, SCHEMA  # noqa: E402
from src.core.agent import answer, replay_scripts  # noqa: E402
from src.core.db import get_client  # noqa: E402
from src.core.saved_queries import SavedQueries  # noqa: E402

ASSETS = ROOT / "assets"
LOGO = str(ASSETS / "insights_titan_logo.png")
ICON = str(ASSETS / "insights_titan_icon.png")
NAVY, TEAL, PURPLE, INK = "#003366", "#00BFA6", "#AB63FF", "#333333"

st.set_page_config(page_title="Patient Risk Monitor", page_icon=ICON, layout="wide")
if hasattr(st, "logo"):
    try:
        st.logo(LOGO, icon_image=ICON, size="large")
    except TypeError:
        st.logo(LOGO, icon_image=ICON)

STORE = SavedQueries(ROOT / "demos" / "healthcare_rpm" / "saved_queries.json")

st.markdown(
    f"""
    <style>
      .block-container {{padding-top: 2rem; max-width: 1120px;}}
      [data-testid="stMetricValue"] {{font-size: 1.5rem; color: {TEAL};}}
      [data-testid="stMetricLabel"] {{color: #6b7b82;}}
      h1, h2, h3, h4, h5 {{color: {NAVY};}}
      .stCodeBlock {{font-size: 0.8rem;}}
      div[data-testid="stExpander"] details {{border-radius: 8px; border-color: #E3EAEC;}}
      /* let button labels wrap instead of truncating */
      .stButton button {{white-space: normal !important; height: auto !important;
                         padding-top: 0.5rem; padding-bottom: 0.5rem; line-height: 1.3;}}
      .stButton button[kind="secondary"] {{text-align: left;}}
      .stButton button[kind="primary"] {{background-color: {NAVY}; border-color: {NAVY};}}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner=False)
def client():
    return get_client()


@st.cache_data(show_spinner=False)
def tables_overview():
    try:
        names = [r[0] for r in client().query("SHOW TABLES").result_rows]
    except Exception:
        return []
    out = []
    for t in names:
        try:
            rows = client().query(f"SELECT count() FROM `{t}`").result_rows[0][0]
        except Exception:
            rows = 0
        try:
            cols = [r[0] for r in client().query(f"DESCRIBE TABLE `{t}`").result_rows]
        except Exception:
            cols = []
        out.append({"name": t, "rows": rows, "columns": cols})
    return out


@st.cache_data(show_spinner=False)
def headline_counts():
    def c(sql):
        try:
            return client().query(sql).result_rows[0][0]
        except Exception:
            return 0
    return c("SELECT count() FROM patients"), c("SELECT count() FROM vitals")


def render_data(ev):
    """One query: its result table (the precise data), with the SQL tucked under it."""
    title = ev.get("title") or "Result"
    if ev["error"]:
        st.markdown(f"**{title}**")
        st.error(f"Query failed: {ev['error']}")
        with st.expander("SQL"):
            st.code(ev["sql"], language="sql")
        return
    st.markdown(f"**{title}**")
    if ev["rows"]:
        df = pd.DataFrame(ev["rows"], columns=list(ev["cols"]))
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.caption("No rows returned.")
    with st.expander("SQL (saved and reusable)"):
        st.code(ev["sql"], language="sql")


# --------------------------------------------------------------------------- #
# Header
# --------------------------------------------------------------------------- #
st.title("Patient Risk Monitor")
st.caption(
    "Ask a question in plain English. You get the SQL that answers it, plus the "
    "result table. Powered by ClickHouse. Synthetic data only - no PHI."
)

tables = tables_overview()
patients, vitals = headline_counts()
model_short = os.getenv("AGENT_MODEL", "claude-sonnet-4-6").replace("claude-", "")

# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.subheader("Data sources")
    if tables:
        for t in tables:
            st.markdown(f"**{t['name']}**  ·  {t['rows']:,} rows")
            if t["columns"]:
                st.caption(", ".join(t["columns"]))
    else:
        st.caption("No tables found.")

    st.divider()
    st.subheader("Saved questions")
    st.caption("Re-runs the saved SQL live - no AI tokens.")
    saved_list = STORE.list_questions()
    if saved_list:
        for i, q in enumerate(saved_list):
            row = st.columns([6, 1])
            if row[0].button(q, key=f"hist_{i}", use_container_width=True):
                st.session_state.question = q
                st.rerun()
            if row[1].button("x", key=f"del_{i}", help="Delete this saved question"):
                STORE.delete(q)
                st.rerun()
    else:
        st.caption("None yet. Your first question is saved here automatically.")

    st.divider()
    st.toggle("Regenerate with AI", key="force",
              help="Rewrite this question's SQL with AI (uses tokens), then save it.")

if not vitals:
    st.error("No data found. Run:  python demos/healthcare_rpm/generate_data.py")
    st.stop()

# --------------------------------------------------------------------------- #
# KPI strip
# --------------------------------------------------------------------------- #
k1, k2, k3, k4 = st.columns(4)
k1.metric("Patients", f"{patients:,}")
k2.metric("Readings", f"{vitals/1e6:.0f}M" if vitals >= 1e6 else f"{vitals:,}")
k3.metric("Tables", len(tables))
k4.metric("AI model", model_short)
st.divider()

# --------------------------------------------------------------------------- #
# Question
# --------------------------------------------------------------------------- #
st.session_state.setdefault("question", "")

with st.expander("Example questions", expanded=False):
    cols = st.columns(2)
    for i, ex in enumerate(EXAMPLES):
        if cols[i % 2].button(ex, key=f"ex_{i}", use_container_width=True):
            st.session_state.question = ex
            st.rerun()

st.text_area("Your question (ask one thing, or several)", key="question", height=90,
             placeholder="e.g. How many COPD patients?  -  or pick an example above")

saved = STORE.get(st.session_state.question)
force = st.session_state.get("force", False)
will_reuse = bool(saved) and not force

if will_reuse:
    st.success(f"Saved ({len(saved.get('scripts', []))} script(s)). Reusing re-runs the SQL live, no AI tokens.")
elif saved and force:
    st.info("Regenerate is on: the SQL will be rewritten with AI (uses tokens) and saved.")

run = st.button("Run", type="primary")

# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #
if run:
    question = st.session_state.question.strip()
    if not question:
        st.warning("Type a question first.")
        st.stop()

    st.divider()

    # ---- reuse: re-run the saved SQL live (0 tokens) ----
    # Show ONLY the live tables - no saved prose, so the written text can never
    # disagree with the freshly re-run numbers.
    if will_reuse:
        STORE.mark_reused(question)
        for ev in replay_scripts(saved.get("scripts", [])):
            render_data(ev)
        st.caption("Live results from the saved SQL. No AI tokens used.")
        st.stop()

    # ---- fresh: plan the SQL, run it, then answer in plain language ----
    saved_scripts, results, answer_text = [], [], ""
    with st.status("Working...", expanded=True) as status:
        for ev in answer(question, SCHEMA):
            if ev["type"] == "status":
                status.update(label=ev["stage"])
            elif ev["type"] == "error":
                status.update(label="Could not complete", state="error")
                st.error(ev["message"])
                st.stop()
            elif ev["type"] == "query":
                results.append(ev)
                if not ev["error"]:  # only keep working SQL for reuse
                    saved_scripts.append({"title": ev["title"], "sql": ev["sql"]})
            elif ev["type"] == "answer":
                answer_text = ev["text"]
        status.update(label="Done", state="complete", expanded=False)

    if answer_text:
        st.markdown(answer_text)
        st.write("")
    for ev in results:
        render_data(ev)

    if saved_scripts:
        STORE.save(question, saved_scripts, answer_text)
