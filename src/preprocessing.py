# Plan:
# 1. Discover cohort files by scanning raw_data_dir for *_task_descriptions.csv.
# 2. Load and merge task descriptions from all cohorts; map to the target schema.
# 3. Drop question rows missing title, description, or sample solution.
# 4. Load and merge solutions from all cohorts.
# 5. Drop solution rows where solution is empty.
# 6. Save merged questions to datastore/questions/question.csv.
# 7. Save merged solutions to datastore/solutions/solutions.csv (preserving any mut_* rows).
# 8. Print EDA summary stats to stdout.

import csv
import os

csv.field_size_limit(10**7)


def discover_cohort_prefixes(raw_data_dir):
    # Finds cohort identifiers (e.g. "19_20") by scanning for *_task_descriptions.csv files.
    prefixes = []
    for name in sorted(os.listdir(raw_data_dir)):
        if name.endswith("_task_descriptions.csv"):
            prefix = name[: -len("_task_descriptions.csv")]
            prefixes.append(prefix)
    return prefixes


def load_csv_rows(path):
    # Reads a CSV file and returns all rows as a list of dicts.
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def strip_row_strings(row):
    # Strips leading/trailing whitespace from every string value in a row dict.
    return {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}


def load_questions(raw_data_dir, prefixes):
    # Loads and merges task descriptions from all cohorts, mapping raw column names to the target schema.
    rows = []
    for prefix in prefixes:
        path = os.path.join(raw_data_dir, f"{prefix}_task_descriptions.csv")
        for raw in load_csv_rows(path):
            r = strip_row_strings(raw)
            rows.append({
                "question_id": r["id"],
                "question_title": r["title_eng"],
                "question_desc": r["task_description_plain_eng"],
                "sample_solution": r["answer"],
                "question_type": "implementation",
            })
    return rows


def drop_incomplete_questions(rows):
    # Removes questions missing a title, description, or sample solution; returns (kept, dropped).
    kept, dropped = [], []
    for r in rows:
        if r["question_title"] and r["question_desc"] and r["sample_solution"]:
            kept.append(r)
        else:
            dropped.append(r)
    return kept, dropped


def load_solutions(raw_data_dir, prefixes):
    # Loads and merges student solutions from all cohorts into a unified list.
    rows = []
    for prefix in prefixes:
        path = os.path.join(raw_data_dir, f"{prefix}_solutions.csv")
        for raw in load_csv_rows(path):
            r = strip_row_strings(raw)
            rows.append({
                "student_id": r["student_id"],
                "question_id": r["question_id"],
                "solution": r["solution"],
            })
    return rows


def drop_empty_solutions(rows):
    # Removes rows where the solution field is blank; returns (kept, dropped).
    kept = [r for r in rows if r["solution"]]
    dropped = [r for r in rows if not r["solution"]]
    return kept, dropped


def save_csv(path, fieldnames, rows):
    # Writes rows to a CSV at the given path, creating parent directories if needed.
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def save_questions(datastore_dir, rows):
    # Saves the merged questions to datastore/questions/question.csv.
    path = os.path.join(datastore_dir, "questions", "question.csv")
    save_csv(path, ["question_id", "question_title", "question_desc", "sample_solution", "question_type"], rows)
    return path


def load_mutation_rows(path):
    # Returns any existing rows whose student_id starts with "mut_", so they survive a re-run.
    if not os.path.isfile(path):
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return [r for r in csv.DictReader(fh) if r.get("student_id", "").startswith("mut_")]


def save_solutions(datastore_dir, rows):
    # Saves merged solutions to solutions.csv, preserving any existing mutation rows.
    path = os.path.join(datastore_dir, "solutions", "solutions.csv")
    mutation_rows = load_mutation_rows(path)
    save_csv(path, ["student_id", "question_id", "solution"], rows + mutation_rows)
    return path


def print_eda(questions, dropped_questions, solutions, dropped_solutions):
    # Prints a summary of loaded, dropped, and saved counts to stdout.
    print("=== EDA Summary ===")
    print(f"Questions loaded:  {len(questions) + len(dropped_questions)}")
    print(f"Questions kept:    {len(questions)}")
    print(f"Questions dropped: {len(dropped_questions)}")
    if dropped_questions:
        for r in dropped_questions:
            empty_fields = [f for f in ["question_title", "question_desc", "sample_solution"] if not r[f]]
            print(f"  dropped {r['question_id']}: empty fields = {empty_fields}")

    print(f"\nSolutions loaded:  {len(solutions) + len(dropped_solutions)}")
    print(f"Solutions kept:    {len(solutions)}")
    print(f"Solutions dropped: {len(dropped_solutions)}")

    sol_per_q = {}
    for r in solutions:
        sol_per_q.setdefault(r["question_id"], 0)
        sol_per_q[r["question_id"]] += 1

    print(f"\nSolutions per question:")
    for qid in sorted(sol_per_q):
        print(f"  {qid}: {sol_per_q[qid]}")


def main(raw_data_dir, datastore_dir):
    prefixes = discover_cohort_prefixes(raw_data_dir)

    raw_questions = load_questions(raw_data_dir, prefixes)
    questions, dropped_questions = drop_incomplete_questions(raw_questions)

    raw_solutions = load_solutions(raw_data_dir, prefixes)
    solutions, dropped_solutions = drop_empty_solutions(raw_solutions)

    save_questions(datastore_dir, questions)
    save_solutions(datastore_dir, solutions)

    print_eda(questions, dropped_questions, solutions, dropped_solutions)
