import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import streamlit as st

import components as ui
import data_access as da


def approach_cells(model, approach, scope):
    # Returns the full run-collapsed rows for the selected model and approach within scope.
    collapsed = da.collapse_to_median(ui.scope_filter(da.load_results(), scope))
    sel = collapsed[(collapsed["model"] == model) & (collapsed["approach"] == approach)]
    return sel.reset_index(drop=True)


def range_status(score, boundary, margin):
    # Classifies a score relative to the boundary band as above, below, or borderline.
    if score > boundary + margin:
        return "above"
    if score < boundary - margin:
        return "below"
    return "borderline"


def annotate(cells, boundary, margin):
    # Adds range status plus the reviewed flag and saved final score for each submission.
    cells = cells.copy()
    cells["status"] = cells["score"].apply(lambda s: range_status(s, boundary, margin))
    finals = da.load_final_grades()
    if finals.empty:
        cells["final_score"] = pd.NA
    else:
        f = finals[["question_id", "student_id", "final_total"]].rename(columns={"final_total": "final_score"})
        cells = cells.merge(f, on=["question_id", "student_id"], how="left")
    cells["reviewed"] = cells["final_score"].notna()
    return cells


def render_kpis(cells):
    # Shows the cohort progress counters for the current model, approach, and scope.
    total = len(cells)
    finalized = int(cells["reviewed"].sum())
    cols = st.columns(3)
    cols[0].metric("Submissions", total)
    cols[1].metric("Finalized", finalized)
    cols[2].metric("Pending", total - finalized)


def filter_by_range(table, choice):
    # Applies the above/below/borderline range filter chosen by the professor.
    if choice == "All":
        return table
    return table[table["status"] == choice.lower()]


def render_table(model, approach, scope):
    # Renders KPIs, the controls, the submission table, and the bulk save-all action.
    boundary = st.slider("Pass/grade boundary", 0, 100, 50, 5)
    margin = st.slider("Borderline margin (±)", 0, 20, 5, 1)
    choice = st.radio("Show", ["All", "Above", "Borderline", "Below"], horizontal=True)

    cells = annotate(approach_cells(model, approach, scope), boundary, margin)
    render_kpis(cells)
    table = filter_by_range(cells, choice).sort_values("score")
    if table.empty:
        st.info("No submissions in this range.")
        return
    _save_all(table, approach)
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


def _save_all(table, approach):
    # Bulk-accepts every not-yet-reviewed submission in the current view as the approach's grade.
    pending = table[~table["reviewed"]]
    count = len(pending)
    label = f"💾 Save all {count} pending as {ui.APPROACH_LABELS[approach]}"
    if st.button(label, type="primary", disabled=count == 0):
        records = [_record_from_cell(row, approach) for _, row in pending.iterrows()]
        written = da.bulk_upsert_final_grades(records)
        st.success(f"Finalized {written} submissions. Open one to fine-tune if needed.")
        st.rerun()


def main():
    st.set_page_config(page_title="Overview", page_icon="📊", layout="wide")
    model, approach, scope = ui.sidebar_controls()
    st.title("📊 Overview & Outliers")
    st.caption(f"Scores shown for **{ui.APPROACH_LABELS[approach]}** · model **{model}**")
    render_table(model, approach, scope)


main()
