import pandas as pd
import streamlit as st

import data_access as da

APPROACHES = ["approach_1", "approach_2", "approach_3", "approach_4"]
APPROACH_LABELS = {
    "approach_1": "A1 · whole rubric, free marks",
    "approach_2": "A2 · per point, free marks",
    "approach_3": "A3 · whole rubric, classify",
    "approach_4": "A4 · per point, classify",
}


def sidebar_controls():
    # Renders the shared model, approach, and question-scope selectors and returns the choices.
    st.sidebar.title("Grading review")
    models = list(da.PRODUCTION_MODELS.keys())
    model = st.sidebar.radio(
        "Grader model",
        models,
        format_func=lambda m: f"{m} ({da.PRODUCTION_MODELS[m]})",
        key="model",
    )
    approach = st.sidebar.radio(
        "Approach",
        APPROACHES,
        index=3,
        format_func=lambda a: APPROACH_LABELS[a],
        key="approach",
    )
    scope = st.sidebar.radio(
        "Question scope",
        ["all", "implementation", "asymptotic"],
        key="scope",
    )
    return model, approach, scope


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
