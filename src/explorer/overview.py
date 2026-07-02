import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import altair as alt
import pandas as pd
import streamlit as st

import components as ui
import data_access as da

BIN_SIZES = [5, 10, 20, 25, 50]


def approach_cells(assignment, model, approach, scope):
    # Returns the full run-collapsed rows for the selected model and approach within scope.
    collapsed = da.collapse_to_median(ui.scope_filter(da.load_results(assignment), scope))
    sel = collapsed[(collapsed["model"] == model) & (collapsed["approach"] == approach)]
    return sel.reset_index(drop=True)


def range_status(score, boundary, margin):
    # Classifies a score relative to the boundary band as above, below, or borderline.
    if score > boundary + margin:
        return "above"
    if score < boundary - margin:
        return "below"
    return "borderline"


def annotate(cells, assignment):
    # Adds the reviewed flag and saved final score for each submission (independent of the boundary).
    cells = cells.copy()
    finals = da.load_final_grades(assignment)
    if finals.empty:
        cells["final_score"] = pd.NA
    else:
        f = finals[["question_id", "student_id", "final_total"]].rename(columns={"final_total": "final_score"})
        cells = cells.merge(f, on=["question_id", "student_id"], how="left")
    cells["reviewed"] = cells["final_score"].notna()
    return cells


def add_status(cells, boundary, margin):
    # Classifies each submission as above/borderline/below once the boundary and margin are chosen.
    cells = cells.copy()
    cells["status"] = cells["score"].apply(lambda s: range_status(s, boundary, margin))
    return cells


def _fmt_stat(value):
    # Formats a score statistic to one decimal, or an em dash when it is undefined.
    return "—" if pd.isna(value) else f"{value:.1f}"


def render_kpis(cells):
    # Shows the cohort progress counters and class score statistics for the current selection.
    total = len(cells)
    finalized = int(cells["reviewed"].sum())
    mean = cells["score"].mean() if total else float("nan")
    std = cells["score"].std() if total > 1 else float("nan")
    cols = st.columns(5)
    cols[0].metric("Submissions", total)
    cols[1].metric("Finalized", finalized)
    cols[2].metric("Pending", total - finalized)
    cols[3].metric("Class average", _fmt_stat(mean))
    cols[4].metric("Std dev", _fmt_stat(std))


def filter_by_range(table, choice):
    # Applies the above/below/borderline range filter chosen by the professor.
    if choice == "All":
        return table
    return table[table["status"] == choice.lower()]


def assign_bins(cells, bin_size):
    # Labels each submission with its 0–100 mark-range bin and returns the ordered bin labels.
    edges = list(range(0, 100, bin_size)) + [100]
    labels = [f"{edges[i]}-{edges[i + 1]}" for i in range(len(edges) - 1)]
    cells = cells.copy()
    idx = (cells["score"] // bin_size).clip(0, len(labels) - 1).astype(int)
    cells["bin"] = idx.map(dict(enumerate(labels)))
    return cells, labels


def _bin_counts(binned, labels):
    # Builds a one-row-per-bin count frame including empty bins so every range stays on the axis.
    counts = binned.groupby("bin").size().reindex(labels, fill_value=0)
    return counts.rename_axis("bin").reset_index(name="count")


def render_histogram(cells):
    # Draws a clickable mark-distribution histogram; returns (binned_cells, selected_bin_labels).
    bin_size = st.select_slider("Mark range bin size", options=BIN_SIZES, value=10, key="bin_size")
    binned, labels = assign_bins(cells, bin_size)
    counts = _bin_counts(binned, labels)
    pick = alt.selection_point(name="pick", fields=["bin"], toggle=False)
    chart = (
        alt.Chart(counts, height=240)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X("bin:N", sort=labels, title="Mark range"),
            y=alt.Y("count:Q", title="Submissions"),
            color=alt.condition(pick, alt.value("#18181b"), alt.value("#e4e4e7")),
            tooltip=["bin", "count"],
        )
        .add_params(pick)
    )
    event = st.altair_chart(chart, on_select="rerun", use_container_width=True, key=f"histogram_{bin_size}")
    return binned, _selected_bins(event)


def _selected_bins(event):
    # Extracts the bin labels the professor clicked from the chart selection event.
    try:
        points = event["selection"]["pick"]
    except (KeyError, TypeError):
        return []
    return [p["bin"] for p in points if "bin" in p]


def filter_by_bins(table, selected):
    # Narrows the table to the clicked histogram bins; no selection shows every bin.
    if not selected:
        return table
    return table[table["bin"].isin(selected)]


def render_filters(locked):
    # Range filter controls; disabled and reset to All while a histogram bar drives the list.
    choice = st.radio(
        "Show", ["All", "Above", "Borderline", "Below"],
        horizontal=True, index=0, disabled=locked,
        key="show_locked" if locked else "show",
    )
    boundary = st.slider("Pass/grade boundary", 0, 100, 50, 5, disabled=locked)
    show_margin = choice == "Borderline" and not locked
    margin = st.slider("Borderline margin (±)", 0, 20, 5, 1) if show_margin else 0
    return choice, boundary, margin


def render_table(assignment, model, approach, scope):
    # Renders KPIs, the histogram, the filters, then the submission table and bulk save-all action.
    cells = annotate(approach_cells(assignment, model, approach, scope), assignment)
    render_kpis(cells)
    binned, selected = render_histogram(cells)
    st.caption("Click a bar to list only its submissions (overrides the Show filter); click it again or an empty area to clear.")
    choice, boundary, margin = render_filters(locked=bool(selected))

    binned = add_status(binned, boundary, margin)
    if selected:
        table = filter_by_bins(binned, selected).sort_values("score")
    else:
        table = filter_by_range(binned, choice).sort_values("score")
    if table.empty:
        st.info("No submissions match the current selection.")
        return
    _save_all(table, approach, assignment)
    _show_grid(table)


def _review_url(row):
    # Builds the deep link that opens a specific submission on the Review & Adjust page.
    return f"/review_and_adjust?question_id={row['question_id']}&student_id={row['student_id']}"


def _show_grid(table):
    # Shows the submission table with reviewed status, final score, and a per-row review link.
    table = table.copy()
    table["action"] = table.apply(_review_url, axis=1)
    st.dataframe(
        table[["question_id", "student_id", "score", "reviewed", "final_score", "action"]],
        hide_index=True, use_container_width=True,
        column_config={
            "reviewed": st.column_config.CheckboxColumn("Reviewed", disabled=True),
            "final_score": st.column_config.NumberColumn("Final"),
            "action": st.column_config.LinkColumn("Review", display_text="Review & adjust"),
        },
    )


def _record_from_cell(row, approach):
    # Builds a final-grade record that accepts one approach's median grade as-is.
    detail = ui.cell_detail(row)
    return {
        "question_id": row["question_id"], "student_id": row["student_id"],
        "final_total": int(round(detail["score"])),
        "final_scores_per_point": json.dumps(detail["scores"]),
        "final_buckets_per_point": json.dumps({k: str(v) for k, v in detail["buckets"].items()}),
        "final_feedback_per_point": json.dumps(detail["feedback"]),
        "adjustment_note": f"bulk-accepted from {approach}", "status": "finalized",
    }


def _save_all(table, approach, assignment):
    # Bulk-accepts every not-yet-reviewed submission in the current view as the approach's grade.
    pending = table[~table["reviewed"]]
    count = len(pending)
    label = f"Save all {count} pending as {ui.APPROACH_LABELS[approach]}"
    if st.button(label, type="primary", disabled=count == 0):
        records = [_record_from_cell(row, approach) for _, row in pending.iterrows()]
        written = da.bulk_upsert_final_grades(assignment, records)
        st.success(f"Finalized {written} submissions. Open one to fine-tune if needed.")
        st.rerun()


def main():
    st.set_page_config(page_title="Overview", layout="wide")
    assignment, model, approach, scope = ui.sidebar_controls()
    st.title("Overview & Outliers")
    st.caption(f"Scores shown for **{ui.APPROACH_LABELS[approach]}** · model **{model}**")
    render_table(assignment, model, approach, scope)


main()
