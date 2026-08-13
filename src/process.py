import argparse
import csv
import json
import os
import re
import sys

APPROACH_CONFIG = {
    "approach_1": {"free_marks": True},
    "approach_2": {"free_marks": True},
    "approach_3": {"free_marks": False},
    "approach_4": {"free_marks": False},
}

VALID_APPROACHES = list(APPROACH_CONFIG.keys())


def _to_fs_name(model):
    return model.split("/")[-1].replace(":", "__")


def _from_fs_name(folder):
    return folder.replace("__", ":")


RESULT_COLUMNS = [
    "question_id", "student_id", "model", "approach", "run",
    "total", "scores_per_point", "buckets_per_point", "format_ok", "feedback_per_point",
    "time_seconds", "median", "run_std",
    "mae", "spearman_rho", "cohen_kappa", "leniency", "feedback_contradiction_rate",
]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--response_store_dir", required=True)
    parser.add_argument("--result_store_dir", required=True)
    parser.add_argument("--datastore_dir", required=True)
    parser.add_argument("--approach", choices=VALID_APPROACHES, default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--question_id", default=None)
    parser.add_argument("--response_file", default="response.txt")
    parser.add_argument("--result_file", default="result.csv")
    return parser.parse_args()


def _task_id_from_question_id(question_id):
    return question_id.rsplit("-", 1)[0]


def _load_single_rubric(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _build_point_lookup(rubric):
    lookup = {}
    for point in rubric["rubric_points"]:
        pid = int(point["id"])
        lookup[pid] = {b["label"]: b["marks"] for b in point["buckets"]}
    return lookup


def load_rubric_lookup(datastore_dir):
    rubrics_dir = os.path.join(datastore_dir, "rubrics")
    lookup = {}
    for task_id in os.listdir(rubrics_dir):
        rubric_path = os.path.join(rubrics_dir, task_id, "rubric.json")
        if not os.path.isfile(rubric_path):
            continue
        rubric = _load_single_rubric(rubric_path)
        lookup[task_id] = _build_point_lookup(rubric)
    return lookup


def get_expected_point_ids(datastore_dir, question_id):
    task_id = _task_id_from_question_id(question_id)
    rubric_path = os.path.join(datastore_dir, "rubrics", task_id, "rubric.json")
    rubric = _load_single_rubric(rubric_path)
    return sorted(int(p["id"]) for p in rubric["rubric_points"])


def _split_into_point_blocks(text):
    pattern = re.compile(
        r"(?:^\s*POINT_ID:\s*(?:Point\s+)?(\d+)(?:[^\S\n]*[—\-][^\n]*)?"
        r"|^\s*POINT\s+ID:\s*(?:Point\s+)?(\d+)(?:[^\S\n]*[—\-][^\n]*)?"
        r"|^\s*POINT_(\d+):"
        r"|^\s*POINT\s+(\d+)(?:[^\S\n]*[—\-][^\n]*)?)"
        r"(.*?)"
        r"(?=^\s*POINT_ID:\s*(?:Point\s+)?\d+"
        r"|^\s*POINT\s+ID:\s*(?:Point\s+)?\d+"
        r"|^\s*POINT_\d+:"
        r"|^\s*POINT\s+\d+"
        r"|\Z)",
        re.DOTALL | re.MULTILINE,
    )
    return [(int(m.group(1) or m.group(2) or m.group(3) or m.group(4)), m.group(5))
            for m in pattern.finditer(text)]


def _extract_marks(block_text):
    m = re.search(r"MARKS:\s*(\d+(?:\.\d+)?)", block_text)
    return round(float(m.group(1))) if m else None


def _extract_bucket(block_text):
    m = re.search(r"BUCKET:\s*(.+)", block_text)
    if not m:
        return None
    label = m.group(1).strip()
    return re.sub(r"\s*\(.*?\)\s*$", "", label).strip()


def _extract_feedback(block_text):
    m = re.search(r"FEEDBACK:\s*(.+)", block_text, re.DOTALL)
    return m.group(1).strip() if m else ""


def parse_free_marks_response(text, expected_point_ids):
    blocks = _split_into_point_blocks(text)
    scores = {}
    feedback = {}
    for pid, block_text in blocks:
        marks = _extract_marks(block_text)
        if marks is not None:
            scores[pid] = marks
        feedback[pid] = _extract_feedback(block_text)
    format_ok = all(pid in scores for pid in expected_point_ids)
    total = sum(scores[pid] for pid in expected_point_ids if pid in scores)
    return {"total": total, "scores": scores, "feedback": feedback, "format_ok": format_ok}


def _lookup_bucket_marks(pid, label, task_rubric):
    if pid in task_rubric and label in task_rubric[pid]:
        return task_rubric[pid][label]
    return None


def parse_bucket_response(text, expected_point_ids, task_rubric):
    blocks = _split_into_point_blocks(text)
    buckets = {}
    feedback = {}
    scores = {}
    format_ok = True
    for pid, block_text in blocks:
        label = _extract_bucket(block_text)
        feedback[pid] = _extract_feedback(block_text)
        if label is None:
            format_ok = False
            continue
        buckets[pid] = label
        marks = _lookup_bucket_marks(pid, label, task_rubric)
        if marks is None:
            format_ok = False
        else:
            scores[pid] = marks
    if not all(pid in buckets for pid in expected_point_ids):
        format_ok = False
    total = sum(scores[pid] for pid in expected_point_ids if pid in scores)
    return {"total": total, "scores": scores, "feedback": feedback, "buckets": buckets, "format_ok": format_ok}


def _empty_parse_result():
    return {
        "total": 0,
        "scores": {},
        "feedback": {},
        "buckets": {},
        "format_ok": False,
    }


def parse_response(text, approach, expected_point_ids, task_rubric):
    try:
        if APPROACH_CONFIG[approach]["free_marks"]:
            result = parse_free_marks_response(text, expected_point_ids)
            result.setdefault("buckets", {})
            return result
        return parse_bucket_response(text, expected_point_ids, task_rubric)
    except Exception:
        return _empty_parse_result()


def discover_runs(response_store_dir, question_id, student_id, approach, model, response_file):
    base = os.path.join(response_store_dir, question_id, student_id, approach, _to_fs_name(model))
    if not os.path.isdir(base):
        return []
    runs = []
    for run_folder in sorted(os.listdir(base)):
        response_path = os.path.join(base, run_folder, response_file)
        if os.path.isfile(response_path):
            runs.append((run_folder, response_path))
    return runs


def build_row(question_id, student_id, model, approach, run_n, parsed):
    return {
        "question_id": question_id,
        "student_id": student_id,
        "model": model,
        "approach": approach,
        "run": run_n,
        "total": parsed["total"],
        "scores_per_point": json.dumps(parsed.get("scores", {})),
        "buckets_per_point": json.dumps(parsed.get("buckets", {})) if parsed.get("buckets") else "",
        "format_ok": parsed["format_ok"],
        "feedback_per_point": json.dumps(parsed.get("feedback", {})),
        "time_seconds": parsed.get("time_seconds", ""),
        "median": "",
        "run_std": "",
        "mae": "",
        "spearman_rho": "",
        "cohen_kappa": "",
        "leniency": "",
        "feedback_contradiction_rate": "",
    }


def _read_response_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def process_combo(response_store_dir, datastore_dir, rubric_lookup, question_id,
                  student_id, approach, model, response_file):
    runs = discover_runs(response_store_dir, question_id, student_id, approach, model, response_file)
    expected_point_ids = get_expected_point_ids(datastore_dir, question_id)
    task_id = _task_id_from_question_id(question_id)
    task_rubric = rubric_lookup.get(task_id, {})
    rows = []
    for run_n, response_path in runs:
        text = _read_response_text(response_path)
        parsed = parse_response(text, approach, expected_point_ids, task_rubric)
        parsed["time_seconds"] = _read_time(os.path.dirname(response_path))
        rows.append(build_row(question_id, student_id, model, approach, run_n, parsed))
    return rows


def _read_time(run_dir):
    path = os.path.join(run_dir, "time.txt")
    if not os.path.isfile(path):
        return ""
    try:
        with open(path, encoding="utf-8") as f:
            return float(f.read().strip())
    except (ValueError, OSError):
        return ""


def _load_existing_results(out_path):
    if not os.path.isfile(out_path):
        return []
    with open(out_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_results(result_store_dir, rows, result_file, filter_question_id=None):
    os.makedirs(result_store_dir, exist_ok=True)
    out_path = os.path.join(result_store_dir, result_file)

    if filter_question_id:
        allowed = {q.strip() for q in filter_question_id.split(",")}
        preserved = [r for r in _load_existing_results(out_path) if r.get("question_id") not in allowed]
    else:
        preserved = []

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(preserved + rows)


def _valid_question_ids(datastore_dir):
    path = os.path.join(datastore_dir, "questions", "question.csv")
    with open(path, newline="", encoding="utf-8") as f:
        return {row["question_id"] for row in csv.DictReader(f)}


def discover_combos(response_store_dir, datastore_dir, filter_question_id, filter_approach, filter_model):
    allowed = {q.strip() for q in filter_question_id.split(",")} if filter_question_id else None
    valid_question_ids = _valid_question_ids(datastore_dir)
    combos = []
    if not os.path.isdir(response_store_dir):
        return combos
    for question_id in os.listdir(response_store_dir):
        if question_id not in valid_question_ids:
            continue
        if allowed is not None and question_id not in allowed:
            continue
        q_path = os.path.join(response_store_dir, question_id)
        if not os.path.isdir(q_path):
            continue
        combos.extend(_discover_combos_for_question(q_path, question_id, filter_approach, filter_model))
    return combos


def _discover_combos_for_question(q_path, question_id, filter_approach, filter_model):
    combos = []
    for student_id in os.listdir(q_path):
        s_path = os.path.join(q_path, student_id)
        if not os.path.isdir(s_path):
            continue
        combos.extend(_discover_combos_for_student(s_path, question_id, student_id, filter_approach, filter_model))
    return combos


def _discover_combos_for_student(s_path, question_id, student_id, filter_approach, filter_model):
    combos = []
    for approach in os.listdir(s_path):
        if filter_approach and approach != filter_approach:
            continue
        a_path = os.path.join(s_path, approach)
        if not os.path.isdir(a_path):
            continue
        for folder in os.listdir(a_path):
            model = _from_fs_name(folder)
            if filter_model and model != filter_model:
                continue
            m_path = os.path.join(a_path, folder)
            if os.path.isdir(m_path):
                combos.append((question_id, student_id, approach, model))
    return combos


def main():
    args = parse_args()
    rubric_lookup = load_rubric_lookup(args.datastore_dir)
    combos = discover_combos(
        args.response_store_dir,
        args.datastore_dir,
        args.question_id,
        args.approach,
        args.model,
    )
    all_rows = []
    for question_id, student_id, approach, model in combos:
        rows = process_combo(
            args.response_store_dir, args.datastore_dir, rubric_lookup,
            question_id, student_id, approach, model, args.response_file,
        )
        all_rows.extend(rows)
    save_results(args.result_store_dir, all_rows, args.result_file, filter_question_id=args.question_id)
    print(f"Wrote {len(all_rows)} rows to {os.path.join(args.result_store_dir, args.result_file)}")


if __name__ == "__main__":
    main()
