import csv
import os
import sys


def load_question_ids(datastore_dir):
    # Reads all question_ids from question.csv; exits if the file is missing or empty.
    path = os.path.join(datastore_dir, "questions", "question.csv")
    if not os.path.exists(path):
        print(f"[ERROR] question.csv not found: {path}")
        sys.exit(1)
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        question_ids = [row["question_id"] for row in reader]
    if not question_ids:
        print(f"[ERROR] question.csv is empty: {path}")
        sys.exit(1)
    return question_ids


def _task_id_from_question_id(question_id):
    # Strips the language suffix to get the task_id (e.g. 19_20-2-1-java → 19_20-2-1).
    parts = question_id.split("-")
    return "-".join(parts[:-1])


def check_rubrics(question_ids, datastore_dir):
    # Checks that rubric.json exists for every unique task_id; deduplicates across language variants.
    errors = []
    seen_task_ids = set()
    for qid in question_ids:
        task_id = _task_id_from_question_id(qid)
        if task_id in seen_task_ids:
            continue
        seen_task_ids.add(task_id)
        rubric_path = os.path.join(datastore_dir, "rubrics", task_id, "rubric.json")
        if not os.path.exists(rubric_path):
            errors.append(f"rubric missing for task_id={task_id}: {rubric_path}")
    return errors


def check_solutions(question_ids, datastore_dir):
    # Checks that at least one solution exists in solutions.csv for every question_id.
    solutions_path = os.path.join(datastore_dir, "solutions", "solutions.csv")
    with open(solutions_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        covered = {row["question_id"] for row in reader}
    errors = []
    for qid in question_ids:
        if qid not in covered:
            errors.append(f"no solutions found for question_id={qid}")
    return errors


def _question_types(datastore_dir):
    # Returns the set of question_types declared in question.csv.
    path = os.path.join(datastore_dir, "questions", "question.csv")
    with open(path, newline="", encoding="utf-8") as f:
        return {row.get("question_type", "implementation") for row in csv.DictReader(f)}


def check_system_prompts(datastore_dir):
    # Checks that approach_1..4 are present, plus analysis_approach_1..4 if any analysis questions exist.
    errors = []
    for n in range(1, 5):
        prompt_path = os.path.join(datastore_dir, "system_prompt", f"approach_{n}.txt")
        if not os.path.exists(prompt_path):
            errors.append(f"system prompt missing: {prompt_path}")
    if "analysis" in _question_types(datastore_dir):
        for n in range(1, 5):
            prompt_path = os.path.join(datastore_dir, "system_prompt", f"analysis_approach_{n}.txt")
            if not os.path.exists(prompt_path):
                errors.append(f"system prompt missing: {prompt_path}")
    return errors


def main(datastore_dir):
    question_ids = load_question_ids(datastore_dir)

    all_errors = []
    all_errors.extend(check_rubrics(question_ids, datastore_dir))
    all_errors.extend(check_solutions(question_ids, datastore_dir))
    all_errors.extend(check_system_prompts(datastore_dir))

    if all_errors:
        for error in all_errors:
            print(f"[ERROR] {error}")
        sys.exit(1)

    print("PASSED")
