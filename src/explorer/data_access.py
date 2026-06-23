import json
import os
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

PRODUCTION_MODELS = {"Qwen3:14b": "local", "gpt-oss-120b": "cloud"}

FINAL_GRADE_COLUMNS = [
    "question_id", "student_id", "final_total",
    "final_scores_per_point", "final_buckets_per_point", "final_feedback_per_point",
    "adjustment_note", "status", "updated_at",
]


def project_root():
    # Resolves the project root from this file's location (src/explorer/ -> ../../), overridable via env.
    env_root = os.environ.get("PROJECT_ROOT")
    if env_root:
        return env_root
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def paths():
    # Returns the absolute paths of every store the explorer reads from or writes to.
    root = project_root()
    datastore = os.path.join(root, "datastore")
    return {
        "root": root,
        "datastore": datastore,
        "result_csv": os.path.join(root, "result_store", "result.csv"),
        "final_grades_csv": os.path.join(root, "result_store", "final_grades.csv"),
        "ground_truth_csv": os.path.join(datastore, "ground_truth.csv"),
        "questions_csv": os.path.join(datastore, "questions", "question.csv"),
        "solutions_csv": os.path.join(datastore, "solutions", "solutions.csv"),
        "rubrics_dir": os.path.join(datastore, "rubrics"),
    }


def task_id_from_question_id(question_id):
    # Strips the language suffix to get the task_id (e.g. 19_20-2-1-java -> 19_20-2-1).
    return question_id.rsplit("-", 1)[0]


def parse_json_col(value):
    # Safely parses a JSON-string CSV cell into a dict, returning {} on any failure.
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return {}
    text = str(value).strip()
    if text in ("", "{}", "nan"):
        return {}
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {}


@st.cache_data
def load_results():
    # Reads result.csv and keeps only the two fully-covered production models.
    df = pd.read_csv(paths()["result_csv"])
    df = df[df["model"].isin(PRODUCTION_MODELS)].copy()
    df["total"] = df["total"].astype(float)
    df["median"] = df["median"].astype(float)
    return df


def _representative_run(group):
    # Picks the run whose total is closest to the median, sourcing its per-point detail for display.
    median = group["median"].iloc[0]
    idx = (group["total"] - median).abs().idxmin()
    return group.loc[idx]


@st.cache_data
def collapse_to_median(df):
    # Reduces the 3 runs of every (question, student, model, approach) cell to one representative row.
    keys = ["question_id", "student_id", "model", "approach"]
    rows = [_representative_run(g) for _, g in df.groupby(keys)]
    collapsed = pd.DataFrame(rows).reset_index(drop=True)
    collapsed["score"] = collapsed["median"]
    return collapsed


@st.cache_data
def load_ground_truth():
    # Loads the human reference grades keyed by (question_id, student_id); empty frame if absent.
    path = paths()["ground_truth_csv"]
    if not os.path.isfile(path):
        return pd.DataFrame(columns=["question_id", "student_id", "human_total", "buckets_per_point"])
    return pd.read_csv(path)


@st.cache_data
def load_questions():
    # Loads question metadata indexed by question_id for fast title/description/solution lookup.
    return pd.read_csv(paths()["questions_csv"]).set_index("question_id")


@st.cache_data
def load_solutions():
    # Loads student submissions indexed by (student_id, question_id).
    df = pd.read_csv(paths()["solutions_csv"])
    return df.set_index(["student_id", "question_id"])


@st.cache_data
def load_rubric(question_id):
    # Reads the rubric.json for a question's task, returning None when no rubric exists.
    task_id = task_id_from_question_id(question_id)
    path = os.path.join(paths()["rubrics_dir"], task_id, "rubric.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def bucket_marks(rubric, point_id, label):
    # Returns the marks awarded for a given bucket label on a rubric point, or 0 if not found.
    for point in rubric["rubric_points"]:
        if int(point["id"]) == int(point_id):
            for b in point["buckets"]:
                if b["label"] == label:
                    return b["marks"]
    return 0


def load_final_grades():
    # Reads final_grades.csv into a DataFrame, returning an empty typed frame before the first save.
    path = paths()["final_grades_csv"]
    if not os.path.isfile(path):
        return pd.DataFrame(columns=FINAL_GRADE_COLUMNS)
    return pd.read_csv(path, dtype={"question_id": str, "student_id": str})


def get_final_grade(question_id, student_id):
    # Returns the saved final grade for one submission as a dict, or None if not yet finalized.
    df = load_final_grades()
    match = df[(df["question_id"] == question_id) & (df["student_id"] == student_id)]
    if match.empty:
        return None
    return match.iloc[0].to_dict()


def upsert_final_grade(record):
    # Inserts or replaces the single final-grade row for a (question_id, student_id) pair.
    bulk_upsert_final_grades([record])


def finalized_keys():
    # Returns the set of (question_id, student_id) pairs that already have a saved final grade.
    df = load_final_grades()
    if df.empty:
        return set()
    return set(zip(df["question_id"], df["student_id"]))


def bulk_upsert_final_grades(records):
    # Inserts or replaces many final-grade rows in a single read/write, returning the count written.
    if not records:
        return 0
    path = paths()["final_grades_csv"]
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for record in records:
        record["updated_at"] = now
    new_rows = pd.DataFrame(records)
    keys = set(zip(new_rows["question_id"], new_rows["student_id"]))
    df = load_final_grades()
    if not df.empty:
        df = df[~df.apply(lambda r: (r["question_id"], r["student_id"]) in keys, axis=1)]
    df = pd.concat([df, new_rows], ignore_index=True)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False, columns=FINAL_GRADE_COLUMNS)
    return len(records)
