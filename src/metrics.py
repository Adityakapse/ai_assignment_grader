import csv
import json
import os
import statistics
import warnings

from scipy.stats import ConstantInputWarning, spearmanr
from sklearn.metrics import cohen_kappa_score

warnings.filterwarnings("ignore", category=ConstantInputWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")
warnings.filterwarnings("ignore", category=RuntimeWarning, module="sklearn")

RESULT_COLUMNS = [
    "question_id", "student_id", "model", "approach", "run",
    "total", "scores_per_point", "buckets_per_point", "format_ok", "feedback_per_point",
    "time_seconds", "median", "run_std",
    "mae", "spearman_rho", "cohen_kappa", "leniency", "feedback_contradiction_rate",
]

_POSITIVE_KEYWORDS = [
    "correct", "correctly", "good", "well", "right", "proper", "properly",
    "successfully", "valid",
]
_NEGATIVE_KEYWORDS = [
    "incorrect", "wrong", "missing", "fail", "fails", "error", "not", "no",
    "lacks", "absent",
]


def _parse_bool(value):
    # Normalises CSV string values like "True"/"1"/"yes" to a Python bool.
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes")


def load_results(path):
    # Reads result.csv and coerces total to float and format_ok to bool for downstream calculations.
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["total"] = float(row["total"])
            row["format_ok"] = _parse_bool(row["format_ok"])
            rows.append(row)
    return rows


def load_ground_truth(path):
    # Loads human-graded totals and optional bucket labels; returns empty dicts if no file is given.
    if path is None or not os.path.isfile(path):
        return {}, {}
    gt_totals = {}
    gt_buckets = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["question_id"], row["student_id"])
            gt_totals[key] = float(row["human_total"])
            if "buckets_per_point" in row and row["buckets_per_point"]:
                try:
                    gt_buckets[key] = json.loads(row["buckets_per_point"])
                except (json.JSONDecodeError, ValueError):
                    pass
    return gt_totals, gt_buckets


def load_rubric_buckets(datastore_dir, question_id):
    # Loads bucket definitions for a question's rubric, used to convert free marks to bucket labels.
    task_id = question_id.rsplit("-", 1)[0]
    path = os.path.join(datastore_dir, "rubrics", task_id, "rubric.json")
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        rubric = json.load(f)
    result = {}
    for point in rubric["rubric_points"]:
        pid = int(point["id"])
        result[pid] = [{"label": b["label"], "marks": b["marks"]} for b in point["buckets"]]
    return result


def marks_to_bucket(mark, bucket_list):
    # Maps a numeric mark to the nearest bucket label by absolute distance.
    return min(bucket_list, key=lambda b: abs(b["marks"] - mark))["label"]


def get_llm_bucket_labels(row, datastore_dir):
    # Returns per-point bucket labels for a row: uses stored buckets_per_point or converts free marks via marks_to_bucket.
    raw_buckets = row.get("buckets_per_point", "")
    if raw_buckets:
        try:
            parsed = json.loads(raw_buckets)
            if parsed:
                return {str(k): v for k, v in parsed.items()}
        except (json.JSONDecodeError, ValueError):
            pass
    raw_scores = row.get("scores_per_point", "")
    if not raw_scores:
        return {}
    try:
        scores = json.loads(raw_scores)
    except (json.JSONDecodeError, ValueError):
        return {}
    rubric_buckets = load_rubric_buckets(datastore_dir, row["question_id"])
    labels = {}
    for pid_str, mark in scores.items():
        pid = int(pid_str)
        if pid in rubric_buckets:
            labels[pid_str] = marks_to_bucket(float(mark), rubric_buckets[pid])
    return labels


def group_by_student(rows):
    # Groups rows by (question_id, student_id, model, approach) to collect all runs per student.
    groups = {}
    for row in rows:
        key = (row["question_id"], row["student_id"], row["model"], row["approach"])
        groups.setdefault(key, []).append(row)
    return groups


def group_by_combo(rows):
    # Groups rows by (question_id, model, approach) to collect all students per combo for aggregate metrics.
    groups = {}
    for row in rows:
        key = (row["question_id"], row["model"], row["approach"])
        groups.setdefault(key, []).append(row)
    return groups


def add_run_stats(rows, student_groups):
    # Fills median and run_std on every row using all runs for that student/model/approach.
    for row in rows:
        key = (row["question_id"], row["student_id"], row["model"], row["approach"])
        group = student_groups[key]
        totals = [r["total"] for r in group]
        row["median"] = statistics.median(totals)
        row["run_std"] = statistics.pstdev(totals) if len(totals) > 1 else 0.0
    return rows


def _contains_any(text, keywords):
    # Returns True if any keyword appears in the lowercased text.
    lowered = text.lower()
    return any(kw in lowered for kw in keywords)


def _is_contradiction(row):
    # Flags a row where high score has negative feedback language, or low score has positive language.
    score = row["total"]
    feedback = str(row.get("feedback_per_point", ""))
    if score > 70 and _contains_any(feedback, _NEGATIVE_KEYWORDS):
        return True
    if score < 30 and _contains_any(feedback, _POSITIVE_KEYWORDS):
        return True
    return False


def compute_feedback_contradiction_rate(rows):
    # Proportion of rows where score and feedback sentiment contradict each other.
    if not rows:
        return 0.0
    return sum(_is_contradiction(r) for r in rows) / len(rows)


def _get_paired_totals(student_groups, gt_totals, question_id, model, approach):
    # Builds parallel LLM-median and human-total lists for students that have ground truth entries.
    llm_medians = []
    human_totals = []
    for (qid, sid, mdl, app), group in student_groups.items():
        if qid != question_id or mdl != model or app != approach:
            continue
        key = (qid, sid)
        if key not in gt_totals:
            continue
        totals = [r["total"] for r in group]
        llm_medians.append(statistics.median(totals))
        human_totals.append(gt_totals[key])
    return llm_medians, human_totals


def compute_mae(llm, human):
    # Mean absolute error between LLM medians and human totals.
    return sum(abs(l - h) for l, h in zip(llm, human)) / len(llm)


def compute_leniency(llm, human):
    # Mean signed difference (LLM − human); positive = LLM is generous, negative = LLM is strict.
    return sum(l - h for l, h in zip(llm, human)) / len(llm)


def compute_spearman_rho(llm, human):
    # Spearman rank correlation coefficient between LLM and human totals.
    # Returns "" if fewer than 3 paired samples or either array is constant (correlation undefined).
    if len(llm) < 3:
        return ""
    if len(set(llm)) == 1 or len(set(human)) == 1:
        return ""
    rho, _ = spearmanr(llm, human)
    return float(rho)


def _flatten_label_pairs(combo_rows, gt_buckets, question_id, datastore_dir):
    # Produces parallel LLM and human label lists across all points and students in a combo.
    llm_list = []
    human_list = []
    for row in combo_rows:
        sid = row["student_id"]
        key = (question_id, sid)
        if key not in gt_buckets:
            continue
        llm_buckets = get_llm_bucket_labels(row, datastore_dir)
        if not llm_buckets:
            continue
        human_buckets = gt_buckets[key]
        for pid_str, llm_label in llm_buckets.items():
            if pid_str in human_buckets:
                llm_list.append(llm_label)
                human_list.append(human_buckets[pid_str])
    return llm_list, human_list


def compute_cohen_kappa(combo_rows, gt_buckets, datastore_dir, question_id):
    # Cohen's kappa between LLM and human bucket labels; returns "" if no ground truth, too few samples,
    # or all labels are identical (degenerate case where kappa is undefined).
    if not gt_buckets:
        return ""
    llm_list, human_list = _flatten_label_pairs(combo_rows, gt_buckets, question_id, datastore_dir)
    if len(llm_list) < 3:
        return ""
    if len(set(llm_list)) == 1 or len(set(human_list)) == 1:
        return ""
    try:
        return float(cohen_kappa_score(llm_list, human_list))
    except (ValueError, ZeroDivisionError):
        return ""


def compute_combo_metrics(combo_rows, student_groups, gt_totals, gt_buckets, combo, datastore_dir):
    # Computes all five aggregate metrics for one (question_id, model, approach) combo.
    question_id, model, approach = combo
    llm, human = _get_paired_totals(student_groups, gt_totals, question_id, model, approach)
    if llm:
        mae = compute_mae(llm, human)
        leniency = compute_leniency(llm, human)
        rho = compute_spearman_rho(llm, human)
    else:
        mae = leniency = rho = ""
    kappa = compute_cohen_kappa(combo_rows, gt_buckets, datastore_dir, question_id)
    fcr = compute_feedback_contradiction_rate(combo_rows)
    return {
        "mae": mae,
        "spearman_rho": rho,
        "cohen_kappa": kappa,
        "leniency": leniency,
        "feedback_contradiction_rate": fcr,
    }


def add_combo_metrics(rows, combo_groups, student_groups, gt_totals, gt_buckets, datastore_dir):
    # Writes combo-level metrics onto every row belonging to that combo in-place.
    for combo, combo_rows in combo_groups.items():
        metrics = compute_combo_metrics(
            combo_rows, student_groups, gt_totals, gt_buckets, combo, datastore_dir
        )
        for row in combo_rows:
            row.update(metrics)
    return rows


def save_results(rows, path, columns):
    # Overwrites the result CSV with the fully annotated rows, ignoring any extra fields.
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main(result_store_dir, datastore_dir, ground_truth=None, result_file="result.csv", output_file=None):
    result_path = os.path.join(result_store_dir, result_file)
    output_path = os.path.join(result_store_dir, output_file if output_file else result_file)
    rows = load_results(result_path)
    gt_totals, gt_buckets = load_ground_truth(ground_truth)
    student_groups = group_by_student(rows)
    combo_groups = group_by_combo(rows)
    add_run_stats(rows, student_groups)
    add_combo_metrics(rows, combo_groups, student_groups, gt_totals, gt_buckets, datastore_dir)
    save_results(rows, output_path, RESULT_COLUMNS)
    print(f"Wrote {len(rows)} rows to {output_path}")
