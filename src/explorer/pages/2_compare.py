import os
import re
import sys
import tempfile

_EXPLORER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _EXPLORER)
sys.path.insert(0, os.path.dirname(_EXPLORER))

import altair as alt
import pandas as pd
import streamlit as st

import components as ui
import data_access as da
import generate_graph as gg

PLOTS = [
    ("plot_rq1_run_consistency", ["df", "out", "impl_q", "asym_q", "model"]),
    ("plot_rq1_deviation", ["df", "out", "model"]),
    ("plot_rq1_score_distribution", ["df", "gt", "out", "model"]),
    ("plot_rq2_mae", ["df", "gt", "out", "models"]),
    ("plot_rq2_spearman", ["df", "gt", "out", "model"]),
    ("plot_rq2_time", ["df", "out", "models"]),
    ("plot_rq3_stability", ["df", "out", "models"]),
    ("plot_rq3_format_failures", ["df", "out", "models"]),
    ("plot_rq4_leniency", ["df", "gt", "out", "model"]),
    ("plot_rq4_leniency_scatter", ["df", "gt", "out", "model"]),
    ("plot_rq4_bucket_distribution", ["df", "gt", "datastore", "out", "model"]),
    ("plot_rq4_length_bias", ["df", "datastore", "out", "model"]),
]


@st.cache_data(show_spinner="Loading data…")
def scoped_inputs(assignment, scope):
    result_store = os.path.dirname(da.paths(assignment)["result_csv"])
    df = gg.load_results(result_store)
    df = ui.scope_filter(df, scope)
    gt = gg.load_ground_truth(da.paths(assignment)["ground_truth_csv"])
    gt = ui.scope_filter(gt, scope) if gt is not None else None
    return df, gt


def _call_args(spec, df, gt, model, out, assignment):
    values = {
        "df": df, "gt": gt, "out": out, "model": model,
        "models": da.available_models(df),
        "datastore": da.paths(assignment)["datastore"],
        "impl_q": gg.IMPL_QUESTION, "asym_q": gg.ASYM_QUESTION,
    }
    return [values[name] for name in spec]


@st.cache_data(show_spinner="Generating graphs…")
def build_images(assignment, scope, model):
    df, gt = scoped_inputs(assignment, scope)
    out = tempfile.mkdtemp()
    for func_name, spec in PLOTS:
        try:
            getattr(gg, func_name)(*_call_args(spec, df, gt, model, out, assignment))
        except Exception:
            continue
    return _read_pngs(out)


def _clean_title(filename):
    name = re.sub(r"^rq\d+_", "", filename.replace(".png", ""))
    return name.replace("_", " ").strip().capitalize()


def _read_pngs(directory):
    images = []
    for name in sorted(os.listdir(directory)):
        if name.endswith(".png"):
            with open(os.path.join(directory, name), "rb") as f:
                images.append((_clean_title(name), f.read()))
    return images


def _point_max(point):
    if point.get("max_marks") is not None:
        return float(point["max_marks"])
    for bucket in point["buckets"]:
        if bucket["label"] == "Correct":
            return float(bucket["marks"])
    return 0.0


def point_difficulty(question_cells, rubric):
    stats = {str(p["id"]): {"name": p["name"], "max": _point_max(p), "pcts": []}
             for p in rubric["rubric_points"]}
    for _, row in question_cells.iterrows():
        scores = da.parse_json_col(row.get("scores_per_point"))
        for pid, s in stats.items():
            if pid in scores and s["max"]:
                s["pcts"].append(100 * float(scores[pid]) / s["max"])
    rows = [{"point": f"P{pid}", "name": s["name"],
             "avg_pct": round(sum(s["pcts"]) / len(s["pcts"]), 1) if s["pcts"] else 0.0}
            for pid, s in stats.items()]
    return pd.DataFrame(rows)


def _difficulty_cells(assignment, model, approach):
    collapsed = da.collapse_to_median(da.load_results(assignment))
    return collapsed[(collapsed["model"] == model) & (collapsed["approach"] == approach)]


def render_point_difficulty(assignment, model, approach):
    st.subheader("Rubric point difficulty")
    cells = _difficulty_cells(assignment, model, approach)
    questions = sorted(cells["question_id"].unique())
    if not questions:
        st.info("No graded submissions for this selection.")
        return
    saved = st.session_state.get("selected_question")
    qid = st.selectbox("Question", questions,
                       index=questions.index(saved) if saved in questions else 0,
                       key="difficulty_q")
    st.session_state["selected_question"] = qid
    rubric = da.load_rubric(assignment, qid)
    if rubric is None:
        st.info("No rubric found for this question.")
        return
    data = point_difficulty(cells[cells["question_id"] == qid], rubric)
    hardest = data.loc[data["avg_pct"].idxmin()]
    st.caption(f"Each bar = average % of the point's max marks earned across all students. "
               f"Lower = harder. Hardest: **{hardest['point']} · {hardest['name']}** ({hardest['avg_pct']:.0f}%).")
    chart = (
        alt.Chart(data, height=260)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, color="#18181b")
        .encode(
            x=alt.X("point:N", sort=list(data["point"]), title="Rubric point"),
            y=alt.Y("avg_pct:Q", title="Avg % of max earned", scale=alt.Scale(domain=[0, 100])),
            tooltip=["point", "name", "avg_pct"],
        )
    )
    st.altair_chart(chart, use_container_width=True)


def main():
    st.set_page_config(page_title="Graphs", layout="wide")
    assignment, model, approach, scope = ui.sidebar_controls()
    st.title("Graphs")
    render_point_difficulty(assignment, model, approach)
    st.divider()
    st.caption(f"Model **{model}** · scope **{scope}** (multi-model charts use all graded models)")
    images = build_images(assignment, scope, model)
    if not images:
        st.info("No graphs available for this selection.")
        return
    for title, data in images:
        with st.expander(title, expanded=False):
            st.image(data, use_container_width=True)


main()
