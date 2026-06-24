import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

import components as ui
import data_access as da

BUCKETS = ["Correct", "Semi", "Wrong"]


def model_cells(model, question_id, student_id):
    # Returns {approach: collapsed_row} for one submission graded by one model.
    collapsed = da.collapse_to_median(da.load_results())
    sel = collapsed[
        (collapsed["model"] == model)
        & (collapsed["question_id"] == question_id)
        & (collapsed["student_id"] == student_id)
    ]
    return {row["approach"]: row for _, row in sel.iterrows()}


def ground_truth_row(question_id, student_id):
    # Returns the human ground-truth row for a submission, or None when absent.
    gt = da.load_ground_truth()
    match = gt[(gt["question_id"] == question_id) & (gt["student_id"] == student_id)]
    return None if match.empty else match.iloc[0]


def apply_deep_link():
    # Reads a submission handed over via URL query params, then clears them so manual picks stick.
    params = st.query_params
    if "question_id" in params:
        st.session_state["selected_question"] = params["question_id"]
        st.session_state["selected_student"] = params.get("student_id")
        st.query_params.clear()


def pick_submission(model):
    # Renders the question/student selectors, defaulting to any selection handed over from Overview.
    collapsed = da.collapse_to_median(da.load_results())
    collapsed = collapsed[collapsed["model"] == model]
    questions = sorted(collapsed["question_id"].unique())
    q_default = _default_index(questions, st.session_state.get("selected_question"))
    question_id = st.selectbox("Question", questions, index=q_default)
    students = sorted(collapsed[collapsed["question_id"] == question_id]["student_id"].unique())
    s_default = _default_index(students, st.session_state.get("selected_student"))
    student_id = st.selectbox("Student submission", students, index=s_default)
    return question_id, student_id


def _default_index(options, value):
    # Returns the index of a previously selected value, or 0 when it is not in the list.
    return options.index(value) if value in options else 0


def render_context(question_id, student_id, rubric):
    # Shows the question, the student solution, the sample solution, and the rubric reference.
    question = da.load_questions().loc[question_id]
    st.markdown(f"### {question['question_title']}")
    with st.expander("Question description"):
        st.markdown(str(question["question_desc"]))
    left, right = st.columns(2)
    with left:
        st.markdown("**Student submission**")
        ui.render_code(_solution_text(student_id, question_id), question_id)
    with right:
        st.markdown("**Sample solution**")
        ui.render_code(question["sample_solution"], question_id)
    with st.expander("Rubric"):
        ui.render_rubric_table(rubric)


def _solution_text(student_id, question_id):
    # Looks up the student's submitted code, tolerating missing entries.
    solutions = da.load_solutions()
    key = (student_id, question_id)
    if key not in solutions.index:
        return "(submission not found)"
    return solutions.loc[key, "solution"]


def render_view(cells, rubric, gt_row):
    # Optionally lays all approaches side-by-side; the single approach is shown by the editor below.
    if not st.checkbox("Compare approaches", value=False):
        return
    ui.render_approach_columns(cells, rubric, gt_row)
    _render_feedback_expanders(cells, rubric)


def _render_feedback_expanders(cells, rubric):
    # Per rubric point, expands on click to show every approach's feedback for that point.
    st.markdown("**Per-point feedback** (click to expand)")
    for point in rubric["rubric_points"]:
        pid = str(point["id"])
        with st.expander(f"Point {pid} · {point['name']}"):
            for approach, row in cells.items():
                feedback = da.parse_json_col(row.get("feedback_per_point")).get(pid, "—")
                st.markdown(f"*{ui.APPROACH_LABELS[approach]}*: {feedback}")


def _editor_seed(question_id, student_id, rubric, cells, approach):
    # Builds the initial editor values from an existing final grade, else from the selected approach.
    saved = da.get_final_grade(question_id, student_id)
    if saved is not None:
        return (da.parse_json_col(saved["final_buckets_per_point"]),
                da.parse_json_col(saved["final_scores_per_point"]),
                da.parse_json_col(saved["final_feedback_per_point"]))
    source = cells[approach] if approach in cells else next(iter(cells.values()))
    detail = ui.cell_detail(source)
    return {k: str(v) for k, v in detail["buckets"].items()}, detail["scores"], detail["feedback"]


def ensure_editor_state(question_id, student_id, rubric, cells, approach):
    # Initialises per-point widget state once per submission so edits persist across reruns.
    token = f"{question_id}|{student_id}"
    if st.session_state.get("edit_for") == token:
        return
    buckets, scores, feedback = _editor_seed(question_id, student_id, rubric, cells, approach)
    for point in rubric["rubric_points"]:
        pid = str(point["id"])
        label = buckets.get(pid) if buckets.get(pid) in BUCKETS else "Wrong"
        st.session_state[f"bucket_{pid}"] = label
        st.session_state[f"marks_{pid}"] = int(scores.get(pid, da.bucket_marks(rubric, pid, label)))
        st.session_state[f"fb_{pid}"] = str(feedback.get(pid, ""))
    st.session_state["edit_for"] = token


def _sync_marks(pid, rubric):
    # Callback: when a point's bucket changes, reset its marks to that bucket's rubric value.
    st.session_state[f"marks_{pid}"] = da.bucket_marks(rubric, pid, st.session_state[f"bucket_{pid}"])


def _prefill_from(source_detail, rubric):
    # Callback: load buckets, marks, and feedback from a chosen approach or ground truth into the editor.
    for point in rubric["rubric_points"]:
        pid = str(point["id"])
        label = source_detail["buckets"].get(pid)
        label = label if label in BUCKETS else "Wrong"
        st.session_state[f"bucket_{pid}"] = label
        st.session_state[f"marks_{pid}"] = int(source_detail["scores"].get(pid, da.bucket_marks(rubric, pid, label)))
        st.session_state[f"fb_{pid}"] = str(source_detail["feedback"].get(pid, ""))


def _prefill_controls(cells, rubric, gt_row):
    # Renders the "pre-fill from" picker that seeds the editor from a source grade.
    options = [a for a in ui.APPROACHES if a in cells]
    labels = {a: ui.APPROACH_LABELS[a] for a in options}
    if gt_row is not None:
        options.append("ground_truth")
        labels["ground_truth"] = "Ground truth (human)"
    choice = st.selectbox("Pre-fill from", options, format_func=lambda o: labels[o])
    st.button("Load values", on_click=_prefill_from,
              args=(_source_detail(choice, cells, gt_row, rubric), rubric))


def _source_detail(choice, cells, gt_row, rubric):
    # Returns a {buckets, scores, feedback} detail dict for the chosen pre-fill source.
    if choice == "ground_truth":
        buckets = da.parse_json_col(gt_row.get("buckets_per_point"))
        scores = {pid: da.bucket_marks(rubric, pid, lbl) for pid, lbl in buckets.items()}
        return {"buckets": buckets, "scores": scores, "feedback": {}}
    return ui.cell_detail(cells[choice])


def render_point_editors(rubric):
    # Renders the per-point bucket, marks, and feedback inputs; returns the running marks total.
    total = 0
    for point in rubric["rubric_points"]:
        pid = str(point["id"])
        st.markdown(f"**Point {pid} · {point['name']}**")
        c1, c2 = st.columns([1, 1])
        c1.selectbox("Bucket", BUCKETS, key=f"bucket_{pid}",
                     on_change=_sync_marks, args=(pid, rubric))
        c2.number_input("Marks", min_value=0, max_value=100, step=1, key=f"marks_{pid}")
        st.text_area("Feedback", key=f"fb_{pid}", height=70)
        total += int(st.session_state[f"marks_{pid}"])
    return total


def render_editor(question_id, student_id, rubric, cells, gt_row, approach):
    # Renders the full final-grade editor and persists the decision on save.
    st.subheader("Final grade")
    saved = da.get_final_grade(question_id, student_id)
    if saved is not None:
        st.success(
            f"✓ Already finalized at {int(float(saved['final_total']))}/100 "
            f"on {saved.get('updated_at', '')}. Editing below will update it."
        )
    ensure_editor_state(question_id, student_id, rubric, cells, approach)
    _prefill_controls(cells, rubric, gt_row)
    summed = render_point_editors(rubric)

    st.metric("Sum of point marks", summed)
    override = st.checkbox("Override total manually")
    final_total = st.number_input("Final total", 0, 100, summed, 1) if override else summed
    note = st.text_area("Adjustment note (optional)", key="adjust_note")
    if st.button("💾 Save final grade", type="primary"):
        _save(question_id, student_id, rubric, final_total, note)


def _collect_point_values(rubric):
    # Reads the per-point buckets, marks, and feedback back out of widget state for saving.
    buckets, scores, feedback = {}, {}, {}
    for point in rubric["rubric_points"]:
        pid = str(point["id"])
        buckets[pid] = st.session_state[f"bucket_{pid}"]
        scores[pid] = int(st.session_state[f"marks_{pid}"])
        feedback[pid] = st.session_state[f"fb_{pid}"]
    return buckets, scores, feedback


def _save(question_id, student_id, rubric, final_total, note):
    # Writes the upserted final-grade row and confirms the persisted values.
    buckets, scores, feedback = _collect_point_values(rubric)
    da.upsert_final_grade({
        "question_id": question_id, "student_id": student_id,
        "final_total": int(final_total),
        "final_scores_per_point": json.dumps(scores),
        "final_buckets_per_point": json.dumps(buckets),
        "final_feedback_per_point": json.dumps(feedback),
        "adjustment_note": note, "status": "finalized",
    })
    st.success(f"Saved final grade {int(final_total)}/100 for {question_id} · {student_id}.")


def main():
    st.set_page_config(page_title="Review & Adjust", page_icon="📝", layout="wide")
    model, approach, _ = ui.sidebar_controls()
    st.title("📝 Review & Adjust")
    apply_deep_link()
    question_id, student_id = pick_submission(model)
    rubric = da.load_rubric(question_id)
    if rubric is None:
        st.error("No rubric found for this question.")
        return
    render_context(question_id, student_id, rubric)
    st.divider()
    cells = model_cells(model, question_id, student_id)
    if not cells:
        st.warning("This model did not grade this submission.")
        return
    gt_row = ground_truth_row(question_id, student_id)
    render_view(cells, rubric, gt_row)
    st.divider()
    render_editor(question_id, student_id, rubric, cells, gt_row, approach)


main()
