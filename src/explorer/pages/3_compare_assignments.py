import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import altair as alt
import pandas as pd
import streamlit as st

import components as ui
import data_access as da

BIN_SIZES = [5, 10, 20, 25, 50]


def submission_grades(assignment):
    # Per (question_id, student_id): the human final grade if finalized, else the LLM median.
    collapsed = da.collapse_to_median(da.load_results(assignment))
    llm = collapsed.groupby(["question_id", "student_id"])["score"].mean()
    grades = pd.DataFrame({"grade": llm, "finalized": False})
    finals = da.load_final_grades(assignment)
    for _, row in finals.iterrows():
        key = (row["question_id"], row["student_id"])
        if key in grades.index:
            grades.loc[key, ["grade", "finalized"]] = [float(row["final_total"]), True]
    return grades


def assignment_summary(assignment, boundary):
    # Cohort statistics for one assignment, computed over per-student assignment grades.
    subs = submission_grades(assignment)
    students = subs.groupby(level="student_id")["grade"].mean()
    return {
        "assignment": assignment,
        "students": int(students.count()),
        "mean": students.mean(),
        "median": students.median(),
        "std": students.std() if students.count() > 1 else float("nan"),
        "pass_rate": 100 * (students >= boundary).mean() if students.count() else float("nan"),
        "pct_finalized": 100 * subs["finalized"].mean() if len(subs) else float("nan"),
    }


def summary_table(assignments, boundary):
    # One row per assignment (in timeline order) of cohort statistics.
    rows = [assignment_summary(a, boundary) for a in assignments]
    return pd.DataFrame(rows)


def _fmt(value):
    # Formats a statistic to one decimal, an em dash when undefined.
    return "—" if pd.isna(value) else f"{value:.1f}"


def render_summary(table):
    # Renders the cohort comparison as a readable table with friendly labels.
    display = pd.DataFrame({
        "Assignment": table["assignment"],
        "Students": table["students"],
        "Class average": table["mean"].map(_fmt),
        "Median": table["median"].map(_fmt),
        "Std dev": table["std"].map(_fmt),
        "Pass rate %": table["pass_rate"].map(_fmt),
        "Finalized %": table["pct_finalized"].map(_fmt),
    })
    st.dataframe(display, hide_index=True, use_container_width=True)


def _grades_long(assignments):
    # Long frame of one row per (assignment, per-student grade) for the density overlay.
    frames = []
    for a in assignments:
        students = submission_grades(a).groupby(level="student_id")["grade"].mean()
        frames.append(pd.DataFrame({"assignment": a, "grade": students.values}))
    if not frames:
        return pd.DataFrame(columns=["assignment", "grade"])
    return pd.concat(frames, ignore_index=True)


def _bin_counts(long, bin_size):
    # Student counts per (assignment, mark-range bin) across the 0-100 range.
    edges = list(range(0, 100, bin_size)) + [100]
    labels = [f"{edges[i]}-{edges[i + 1]}" for i in range(len(edges) - 1)]
    idx = (long["grade"] // bin_size).clip(0, len(labels) - 1).astype(int)
    binned = long.assign(bin=idx.map(dict(enumerate(labels))))
    counts = binned.groupby(["assignment", "bin"]).size().reset_index(name="count")
    return counts, labels


def render_histogram(assignments):
    # Grouped, multi-colour marks histogram: one bar per assignment within each mark range.
    st.subheader("Marks distribution")
    long = _grades_long(assignments)
    if long.empty:
        st.info("No grades to plot.")
        return
    bin_size = st.select_slider("Mark range bin size", options=BIN_SIZES, value=10, key="cmp_bin_size")
    counts, labels = _bin_counts(long, bin_size)
    order = list(dict.fromkeys(assignments))
    chart = (
        alt.Chart(counts, height=320)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X("bin:N", sort=labels, scale=alt.Scale(domain=labels), title="Mark range"),
            xOffset=alt.XOffset("assignment:N", sort=order),
            y=alt.Y("count:Q", title="Students"),
            color=alt.Color("assignment:N", title="Assignment", sort=order),
            tooltip=["assignment", "bin", "count"],
        )
    )
    st.altair_chart(chart, use_container_width=True, key=f"cmp_hist_{bin_size}")


def _selectable_assignments():
    # Real assignments only (drops the None dissertation root), sorted to form the timeline.
    return sorted(a for a in da.list_assignments() if a is not None)


def main():
    st.set_page_config(page_title="Compare assignments", layout="wide")
    ui.apply_theme()
    st.sidebar.title("Grading review")
    st.title("Compare assignments")

    options = _selectable_assignments()
    if not options:
        st.info("No assignments found under result_store/.")
        return
    current = st.session_state.get("assignment")
    default = [current] if current in options else options[:1]
    chosen = st.multiselect("Assignments to compare", options, default=default)
    boundary = st.slider("Pass/grade boundary", 0, 100, 50, 5)
    if not chosen:
        st.info("Select at least one assignment.")
        return

    table = summary_table(sorted(chosen), boundary)
    st.caption("Grades use the professor's final grade where finalized, otherwise the LLM median.")
    render_summary(table)
    st.divider()
    render_histogram(sorted(chosen))


main()
