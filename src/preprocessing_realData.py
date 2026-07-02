# Plan:
# 1. Merge the real student solutions from every cohort's *_solutions.csv in raw_data.
# 2. Keep only implementation questions (drop asymptotic "asym-" questions) that have a rubric
#    and exist in the datastore question.csv, with a non-empty solution.
# 3. Sample a fixed number of solutions per question (deterministic: first N by student_id).
# 4. Write the sampled solutions + the implementation questions into a separate real-data dataset
#    (default datastore/realdata/), reusing the datastore's rubrics and system prompts.
# The synthetic experiment datastore is only read, never modified.

import argparse
import csv
import os
import shutil

csv.field_size_limit(10**7)

DEFAULT_PER_QUESTION = 3


def read_csv_rows(path):
    # Reads a CSV file and returns all rows as a list of dicts.
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def merge_raw_solutions(raw_data_dir):
    # Merges the student solutions from every cohort's *_solutions.csv into one list.
    rows = []
    for name in sorted(os.listdir(raw_data_dir)):
        if name.endswith("_solutions.csv"):
            rows.extend(read_csv_rows(os.path.join(raw_data_dir, name)))
    return rows


def rubric_task_ids(datastore_dir):
    # Returns the set of task_ids that have a rubric folder in the datastore.
    rubrics_dir = os.path.join(datastore_dir, "rubrics")
    return {d for d in os.listdir(rubrics_dir) if os.path.isdir(os.path.join(rubrics_dir, d))}


def implementation_questions(datastore_dir):
    # Returns the datastore question rows for implementation questions only (drops asym- analysis ones).
    path = os.path.join(datastore_dir, "questions", "question.csv")
    return [r for r in read_csv_rows(path) if not r["question_id"].startswith("asym-")]


def is_gradable(row, valid_qids, rubric_tasks):
    # A solution is gradable if it is non-empty, implementation-only, in question.csv, and has a rubric.
    qid = row["question_id"]
    return (
        row["solution"].strip() != ""
        and not qid.startswith("asym-")
        and qid in valid_qids
        and qid.rsplit("-", 1)[0] in rubric_tasks
    )


def sample_solutions(rows, valid_qids, rubric_tasks, per_question):
    # Keeps the first `per_question` gradable solutions per question, ordered by student_id for reproducibility.
    ordered = sorted(rows, key=lambda r: (r["question_id"], r["student_id"]))
    per_q = {}
    for r in ordered:
        if is_gradable(r, valid_qids, rubric_tasks) and len(per_q.get(r["question_id"], [])) < per_question:
            per_q.setdefault(r["question_id"], []).append(r)
    return [r for rows_q in per_q.values() for r in rows_q]


def save_solutions(out_dir, rows):
    # Writes the sampled solutions to <out_dir>/solutions/solutions.csv in the datastore schema.
    path = os.path.join(out_dir, "solutions", "solutions.csv")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["student_id", "question_id", "solution"])
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r[k] for k in ("student_id", "question_id", "solution")})
    return path


def save_questions(out_dir, rows):
    # Writes the implementation questions to <out_dir>/questions/question.csv.
    path = os.path.join(out_dir, "questions", "question.csv")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fields = ["question_id", "question_title", "question_desc", "sample_solution", "question_type"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def copy_reused(datastore_dir, out_dir):
    # Reuses the datastore's rubrics and system prompts as-is (copied, so nothing is shared or mutated).
    for sub in ("rubrics", "system_prompt"):
        shutil.copytree(os.path.join(datastore_dir, sub), os.path.join(out_dir, sub), dirs_exist_ok=True)


def print_summary(questions, sampled, per_question):
    # Prints how many questions and solutions were written, and the per-question counts.
    per_q = {}
    for r in sampled:
        per_q[r["question_id"]] = per_q.get(r["question_id"], 0) + 1
    print("=== Real-data preprocessing summary ===")
    print(f"Implementation questions: {len(questions)}")
    print(f"Solutions sampled (<= {per_question}/question): {len(sampled)}")
    print(f"Questions with solutions: {len(per_q)}")
    for qid in sorted(per_q):
        print(f"  {qid}: {per_q[qid]}")


def main(raw_data_dir, datastore_dir, out_dir, per_question):
    valid_qids = {r["question_id"] for r in implementation_questions(datastore_dir)}
    rubric_tasks = rubric_task_ids(datastore_dir)

    raw = merge_raw_solutions(raw_data_dir)
    sampled = sample_solutions(raw, valid_qids, rubric_tasks, per_question)
    questions = implementation_questions(datastore_dir)

    save_questions(out_dir, questions)
    save_solutions(out_dir, sampled)
    copy_reused(datastore_dir, out_dir)

    print_summary(questions, sampled, per_question)


def parse_args():
    parser = argparse.ArgumentParser(description="Build a real-data dataset (implementation questions only).")
    parser.add_argument("--raw_data_dir", default="raw_data/AD2022dataset")
    parser.add_argument("--datastore_dir", default="datastore")
    parser.add_argument("--out_dir", default="datastore/realdata")
    parser.add_argument("--per_question", type=int, default=DEFAULT_PER_QUESTION)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.raw_data_dir, args.datastore_dir, args.out_dir, args.per_question)
