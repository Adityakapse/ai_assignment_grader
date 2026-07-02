import pandas as pd
import streamlit as st

import data_access as da

THEME_CSS = """
<style>
:root {
  --bg: #ffffff;
  --fg: #09090b;
  --muted: #71717a;
  --border: #e4e4e7;
  --accent: #18181b;
  --subtle: #fafafa;
}
html, body, [class*="css"] { -webkit-font-smoothing: antialiased; }
h1, h2, h3, h4 { letter-spacing: -0.01em; font-weight: 650; }
.block-container { padding-top: 2.5rem; max-width: 1200px; }

/* Buttons — solid black primary, outlined secondary (shadcn style) */
.stButton > button, .stDownloadButton > button {
  border-radius: 0.55rem;
  border: 1px solid var(--border);
  font-weight: 550;
  transition: all 0.12s ease;
}
.stButton > button[kind="primary"] {
  background: var(--accent); color: #fff; border-color: var(--accent);
}
.stButton > button[kind="primary"]:hover { background: #000; border-color: #000; }
.stButton > button[kind="secondary"] { background: #fff; color: var(--fg); }
.stButton > button[kind="secondary"]:hover { background: var(--subtle); border-color: #d4d4d8; }

/* Metric cards — bordered tiles */
[data-testid="stMetric"] {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  padding: 1rem 1.1rem;
}
[data-testid="stMetricValue"] { font-weight: 650; letter-spacing: -0.02em; }
[data-testid="stMetricLabel"] { color: var(--muted); }

/* Expanders & containers — clean hairline borders */
[data-testid="stExpander"] details {
  border: 1px solid var(--border);
  border-radius: 0.75rem;
}
[data-testid="stExpander"] summary:hover { color: var(--accent); }

/* Inputs — neutral focus ring */
[data-baseweb="input"], [data-baseweb="select"] > div, .stTextArea textarea {
  border-radius: 0.55rem !important;
}

/* Tables */
[data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: 0.75rem; }

/* Sidebar — slightly inset, hairline divider */
[data-testid="stSidebar"] { background: var(--subtle); border-right: 1px solid var(--border); }

/* Tabs & radios — muted unselected, black selected */
[data-baseweb="tab-highlight"] { background: var(--accent) !important; }

hr { border-color: var(--border); }
</style>
"""


def apply_theme():
    # Injects the shared monochrome (shadcn-style) CSS; call once at the top of every page.
    st.markdown(THEME_CSS, unsafe_allow_html=True)


APPROACHES = ["approach_1", "approach_2", "approach_3", "approach_4"]
APPROACH_LABELS = {
    "approach_1": "A1 · whole rubric, free marks",
    "approach_2": "A2 · per point, free marks",
    "approach_3": "A3 · whole rubric, classify",
    "approach_4": "A4 · per point, classify",
}


def _assignment_selector():
    # Renders the dataset picker; None is the dissertation root, otherwise a result_store subfolder.
    options = da.list_assignments()
    if not options:
        st.sidebar.warning("No datasets found under result_store/.")
        return None
    return st.sidebar.selectbox(
        "Assignment", options,
        format_func=lambda a: "Main (dissertation)" if a is None else a,
        key="assignment",
    )


def _available_options(assignment):
    # Restricts the model and approach choices to what the selected dataset actually contains.
    try:
        df = da.load_results(assignment)
    except Exception:
        df = None
    if df is None or df.empty:
        return list(da.PRODUCTION_MODELS.keys()), APPROACHES
    models = [m for m in da.PRODUCTION_MODELS if m in set(df["model"])]
    approaches = [a for a in APPROACHES if a in set(df["approach"])]
    return models or list(da.PRODUCTION_MODELS.keys()), approaches or APPROACHES


def sidebar_controls():
    # Renders the assignment, model, approach, and question-scope selectors and returns the choices.
    apply_theme()
    st.sidebar.title("Grading review")
    assignment = _assignment_selector()
    models, approaches = _available_options(assignment)
    model = st.sidebar.radio(
        "Grader model",
        models,
        format_func=lambda m: f"{m} ({da.PRODUCTION_MODELS[m]})",
        key=f"model_{assignment}",
    )
    default_ap = approaches.index("approach_4") if "approach_4" in approaches else 0
    approach = st.sidebar.radio(
        "Approach",
        approaches,
        index=default_ap,
        format_func=lambda a: APPROACH_LABELS[a],
        key=f"approach_{assignment}",
    )
    scope = st.sidebar.radio(
        "Question scope",
        ["all", "implementation", "asymptotic"],
        key="scope",
    )
    return assignment, model, approach, scope


def scope_filter(df, scope):
    # Filters a frame to implementation (non-asym) or asymptotic (asym-) questions, or returns all.
    if scope == "implementation":
        return df[~df["question_id"].str.startswith("asym-")]
    if scope == "asymptotic":
        return df[df["question_id"].str.startswith("asym-")]
    return df


def code_language(question_id):
    # Infers the syntax-highlighting language from the question_id suffix.
    return "python" if question_id.endswith("python") else "java"


def render_code(text, question_id):
    # Renders a code block with language detected from the question_id.
    st.code(str(text), language=code_language(question_id))


def render_rubric_table(rubric):
    # Renders the rubric points and their bucket marks as a compact reference table.
    rows = []
    for point in rubric["rubric_points"]:
        marks = {b["label"]: b["marks"] for b in point["buckets"]}
        rows.append({
            "Point": point["id"],
            "Name": point["name"],
            "Correct": marks.get("Correct", ""),
            "Semi": marks.get("Semi", ""),
            "Wrong": marks.get("Wrong", ""),
            "Assessing": _point_target(point),
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def _point_target(point):
    # Describes what the rubric point assesses: its target if set, else the full-credit criterion.
    if point.get("target"):
        return point["target"]
    for bucket in point["buckets"]:
        if bucket["label"] == "Correct":
            return bucket["description"]
    return ""


def cell_detail(cell_row):
    # Parses a collapsed result row into score, per-point marks, buckets, and feedback dicts.
    return {
        "score": float(cell_row["score"]),
        "scores": da.parse_json_col(cell_row.get("scores_per_point")),
        "buckets": da.parse_json_col(cell_row.get("buckets_per_point")),
        "feedback": da.parse_json_col(cell_row.get("feedback_per_point")),
    }


def render_approach_columns(cells_by_approach, rubric, gt_row=None):
    # Lays the four approaches side-by-side (plus an optional ground-truth column) for comparison.
    columns = [a for a in APPROACHES if a in cells_by_approach]
    headers = columns + (["ground_truth"] if gt_row is not None else [])
    cols = st.columns(len(headers))
    for col, name in zip(cols, headers):
        with col:
            if name == "ground_truth":
                _render_gt_column(gt_row, rubric)
            else:
                _render_compare_column(name, cells_by_approach[name], rubric)


def _render_compare_column(approach, cell_row, rubric):
    # Renders one approach column in compare mode: total and per-point bucket/marks (no inline feedback).
    detail = cell_detail(cell_row)
    st.markdown(f"**{APPROACH_LABELS[approach]}**")
    st.metric("Total", f"{detail['score']:.0f}")
    for point in rubric["rubric_points"]:
        pid = str(point["id"])
        bucket = detail["buckets"].get(pid, "—")
        marks = detail["scores"].get(pid, "—")
        st.write(f"P{pid}: `{bucket}` · {marks}")


def _render_gt_column(gt_row, rubric):
    # Renders the human ground-truth column alongside the approach columns for reference.
    st.markdown("**Ground truth (human)**")
    st.metric("Total", f"{float(gt_row['human_total']):.0f}")
    buckets = da.parse_json_col(gt_row.get("buckets_per_point"))
    for point in rubric["rubric_points"]:
        pid = str(point["id"])
        st.write(f"P{pid}: `{buckets.get(pid, '—')}`")
