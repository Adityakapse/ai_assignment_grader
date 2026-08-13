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
    st.markdown(THEME_CSS, unsafe_allow_html=True)


APPROACHES = ["approach_1", "approach_2", "approach_3", "approach_4"]
APPROACH_LABELS = {
    "approach_1": "A1 · whole rubric, free marks",
    "approach_2": "A2 · per point, free marks",
    "approach_3": "A3 · whole rubric, classify",
    "approach_4": "A4 · per point, classify",
}


def _assignment_selector():
    options = da.list_assignments()
    if not options:
        st.sidebar.warning("No datasets found under result_store/.")
        return None
    saved = st.session_state.get("assignment_choice")
    index = options.index(saved) if saved in options else 0
    choice = st.sidebar.selectbox(
        "Assignment", options,
        index=index,
        format_func=lambda a: "Main (dissertation)" if a is None else a,
        key="assignment",
    )
    st.session_state["assignment_choice"] = choice
    return choice


def _available_options(assignment):
    try:
        df = da.load_results(assignment)
    except Exception:
        df = None
    if df is None or df.empty:
        return list(da.PRODUCTION_MODELS.keys()), APPROACHES
    models = da.available_models(df)
    approaches = [a for a in APPROACHES if a in set(df["approach"])]
    return models or list(da.PRODUCTION_MODELS.keys()), approaches or APPROACHES


def _persisted_radio(label, options, state_key, widget_key, default_index=0, **kwargs):
    saved = st.session_state.get(state_key)
    index = options.index(saved) if saved in options else default_index
    choice = st.sidebar.radio(label, options, index=index, key=widget_key, **kwargs)
    st.session_state[state_key] = choice
    return choice


def sidebar_controls():
    apply_theme()
    st.sidebar.title("Grading review")
    assignment = _assignment_selector()
    models, approaches = _available_options(assignment)
    model = _persisted_radio(
        "Grader model", models,
        f"model_choice_{assignment}", f"model_{assignment}",
    )
    default_ap = approaches.index("approach_4") if "approach_4" in approaches else 0
    approach = _persisted_radio(
        "Approach", approaches,
        f"approach_choice_{assignment}", f"approach_{assignment}",
        default_index=default_ap,
        format_func=lambda a: APPROACH_LABELS[a],
    )
    scope = _persisted_radio(
        "Question scope", ["all", "implementation", "asymptotic"],
        "scope_choice", "scope",
    )
    return assignment, model, approach, scope


def scope_filter(df, scope):
    if scope == "implementation":
        return df[~df["question_id"].str.startswith("asym-")]
    if scope == "asymptotic":
        return df[df["question_id"].str.startswith("asym-")]
    return df


def code_language(question_id):
    return "python" if question_id.endswith("python") else "java"


def render_code(text, question_id):
    st.code(str(text), language=code_language(question_id))


def render_rubric_table(rubric):
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
    if point.get("target"):
        return point["target"]
    for bucket in point["buckets"]:
        if bucket["label"] == "Correct":
            return bucket["description"]
    return ""


def cell_detail(cell_row):
    return {
        "score": float(cell_row["score"]),
        "scores": da.parse_json_col(cell_row.get("scores_per_point")),
        "buckets": da.parse_json_col(cell_row.get("buckets_per_point")),
        "feedback": da.parse_json_col(cell_row.get("feedback_per_point")),
    }


def render_approach_columns(cells_by_approach, rubric, gt_row=None):
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
    detail = cell_detail(cell_row)
    st.markdown(f"**{APPROACH_LABELS[approach]}**")
    st.metric("Total", f"{detail['score']:.0f}")
    for point in rubric["rubric_points"]:
        pid = str(point["id"])
        bucket = detail["buckets"].get(pid, "—")
        marks = detail["scores"].get(pid, "—")
        st.write(f"P{pid}: `{bucket}` · {marks}")


def _render_gt_column(gt_row, rubric):
    st.markdown("**Ground truth (human)**")
    st.metric("Total", f"{float(gt_row['human_total']):.0f}")
    buckets = da.parse_json_col(gt_row.get("buckets_per_point"))
    for point in rubric["rubric_points"]:
        pid = str(point["id"])
        st.write(f"P{pid}: `{buckets.get(pid, '—')}`")
