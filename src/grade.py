import argparse
import csv
import json
import os
import sys
import time

import requests

OLLAMA_API = "http://localhost:11434/api/generate"

APPROACH_CONFIG = {
    "approach_1": {"whole_rubric": True,  "free_marks": True},
    "approach_2": {"whole_rubric": False, "free_marks": True},
    "approach_3": {"whole_rubric": True,  "free_marks": False},
    "approach_4": {"whole_rubric": False, "free_marks": False},
}

VALID_APPROACHES = list(APPROACH_CONFIG.keys())


def _to_fs_name(model):
    return model.replace(":", "__")


def parse_args():
    # Parses and validates CLI args; exits if datastore_dir does not exist.
    parser = argparse.ArgumentParser()
    parser.add_argument("--datastore_dir", required=True)
    parser.add_argument("--response_store_dir", required=True)
    parser.add_argument("--approach", required=True, choices=VALID_APPROACHES)
    parser.add_argument("--model", required=True)
    parser.add_argument("--question_id", default=None)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--response_file", default="response.txt")
    parser.add_argument("--prompt_file", default="prompt.txt")
    args = parser.parse_args()
    if not os.path.isdir(args.datastore_dir):
        print(f"Error: datastore_dir does not exist: {args.datastore_dir}")
        sys.exit(1)
    return args


def load_question_map(datastore_dir):
    # Loads all questions into a dict keyed by question_id for quick lookup during grading.
    path = os.path.join(datastore_dir, "questions", "question.csv")
    question_map = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            question_map[row["question_id"]] = {
                "question_desc": row["question_desc"],
                "sample_solution": row["sample_solution"],
                "question_type": row.get("question_type", "implementation"),
            }
    return question_map


def load_solutions(datastore_dir, question_id):
    # Returns all student solutions for a specific question_id.
    csv.field_size_limit(10**7)
    path = os.path.join(datastore_dir, "solutions", "solutions.csv")
    solutions = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["question_id"] == question_id:
                solutions.append({
                    "student_id": row["student_id"],
                    "solution": row["solution"],
                })
    return solutions


def load_rubric(datastore_dir, question_id):
    # Derives task_id from question_id and loads its rubric.json.
    parts = question_id.rsplit("-", 1)
    task_id = parts[0]
    path = os.path.join(datastore_dir, "rubrics", task_id, "rubric.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_system_prompt(datastore_dir, approach, question_type="implementation"):
    # Selects analysis_approach_n.txt for analysis questions, approach_n.txt for all others.
    prefix = "analysis_" if question_type == "analysis" else ""
    path = os.path.join(datastore_dir, "system_prompt", f"{prefix}{approach}.txt")
    with open(path, encoding="utf-8") as f:
        return f.read()


def _format_point_free_marks(point):
    # Formats a rubric point for free-mark approaches — shows valid mark range, no buckets.
    return (
        f"Point {point['id']} — {point['name']} (valid range: 0–{point['max_marks']})\n"
        f"  {point.get('target', point.get('description', ''))}"
    )


def _format_point_buckets(point):
    # Formats a rubric point for bucket approaches — lists each bucket label, marks, and description.
    bucket_lines = "\n".join(
        f"    - {b['label']} ({b['marks']} marks): {b['description']}"
        for b in point["buckets"]
    )
    target = point.get("target", point.get("description", ""))
    return (
        f"Point {point['id']} — {point['name']}\n"
        f"  {target}\n"
        f"  Buckets:\n{bucket_lines}"
    )


def _format_point(point, free_marks):
    # Dispatches to the correct point formatter based on whether the approach uses free marks or buckets.
    if free_marks:
        return _format_point_free_marks(point)
    return _format_point_buckets(point)


def _build_prompt_header(question, solution):
    # Builds the shared QUESTION / SAMPLE SOLUTION / STUDENT SOLUTION header used by all prompt types.
    return (
        f"QUESTION:\n{question['question_desc']}\n\n"
        f"SAMPLE SOLUTION:\n{question['sample_solution']}\n\n"
        f"STUDENT SOLUTION:\n{solution}\n\n"
    )


def build_prompt_whole(question, solution, rubric, free_marks):
    # Builds a single prompt containing all rubric points (approach_1 and approach_3).
    header = _build_prompt_header(question, solution)
    points_text = "\n\n".join(
        _format_point(p, free_marks) for p in rubric["rubric_points"]
    )
    return header + f"RUBRIC:\n{points_text}"


def build_prompt_point(question, solution, point, free_marks):
    # Builds a prompt for a single rubric point (approach_2 and approach_4).
    header = _build_prompt_header(question, solution)
    point_text = _format_point(point, free_marks)
    return header + f"RUBRIC POINT:\n{point_text}"


def call_ollama(prompt, model, system_prompt, retries=3, timeout=300):
    # Sends a prompt to the local Ollama API and returns the model's response text.
    # Retries up to `retries` times on timeout or empty response before giving up.
    if model == "deepseek-coder:6.7b":
        options = {
            "temperature": 0.0,
            "num_ctx": 2048,
            "num_predict": 100,
        }
    else:
        options = {}
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "system": system_prompt,
        "options": options,
    }
    for attempt in range(1, retries + 1):
        try:
            response = requests.post(OLLAMA_API, json=payload, timeout=timeout)
            result = response.json()["response"]
            if result.strip():
                return result
            if attempt < retries:
                print(f"  [warn] Empty response (attempt {attempt}/{retries}), retrying...")
        except requests.exceptions.Timeout:
            if attempt == retries:
                raise
            print(f"  [warn] Ollama timeout (attempt {attempt}/{retries}), retrying...")
    return ""


def assemble_per_point_response(point_results):
    # Joins individual per-point LLM responses into one block prefixed with POINT_ID: for process.py to parse.
    blocks = [
        f"POINT_ID: {item['point_id']}\n{item['response']}"
        for item in point_results
    ]
    return "\n\n".join(blocks)


def response_exists(response_store_dir, question_id, student_id, approach, model, run_n, response_file):
    # Checks if a non-empty response file already exists so completed runs are not re-graded.
    # Empty files (from a previous failed attempt) are treated as not done and will be retried.
    path = os.path.join(
        response_store_dir, question_id, student_id, approach, _to_fs_name(model), run_n, response_file
    )
    return os.path.isfile(path) and os.path.getsize(path) > 0


def save_run(response_store_dir, question_id, student_id, approach, model, run_n,
             response, prompt_text, elapsed_seconds, response_file, prompt_file):
    # Writes response.txt, prompt.txt, and time.txt to the response_store path for this run.
    directory = os.path.join(
        response_store_dir, question_id, student_id, approach, _to_fs_name(model), run_n
    )
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, response_file), "w", encoding="utf-8") as f:
        f.write(response)
    with open(os.path.join(directory, prompt_file), "w", encoding="utf-8") as f:
        f.write(prompt_text)
    with open(os.path.join(directory, "time.txt"), "w", encoding="utf-8") as f:
        f.write(f"{elapsed_seconds:.4f}")


def _grade_whole_rubric(question, solution_text, rubric, system_prompt, model, free_marks):
    # Grades by sending all rubric points in one prompt; returns (response, prompt).
    prompt = build_prompt_whole(question, solution_text, rubric, free_marks)
    response = call_ollama(prompt, model, system_prompt)
    return response, prompt


def _grade_per_point(question, solution_text, rubric, system_prompt, model, free_marks):
    # Grades by calling the LLM once per rubric point and assembling the responses.
    point_results = []
    prompts = []
    for point in rubric["rubric_points"]:
        prompt = build_prompt_point(question, solution_text, point, free_marks)
        response = call_ollama(prompt, model, system_prompt)
        point_results.append({"point_id": point["id"], "response": response})
        prompts.append(prompt)
    assembled = assemble_per_point_response(point_results)
    separator = "\n\n" + "=" * 40 + "\n\n"
    return assembled, separator.join(prompts)


def grade_one_run(question, solution_text, rubric, system_prompt, model, whole_rubric, free_marks):
    # Dispatches to whole-rubric or per-point grading; also measures total wall-clock seconds.
    start = time.perf_counter()
    if whole_rubric:
        response, prompt = _grade_whole_rubric(question, solution_text, rubric, system_prompt, model, free_marks)
    else:
        response, prompt = _grade_per_point(question, solution_text, rubric, system_prompt, model, free_marks)
    elapsed = time.perf_counter() - start
    return response, prompt, elapsed


def grade_question(question_id, question, solutions, rubric, system_prompt,
                   model, approach, whole_rubric, free_marks, runs,
                   response_store_dir, response_file, prompt_file):
    # Iterates over all students and runs, skipping any run that already has a saved response.
    for sol in solutions:
        student_id = sol["student_id"]
        solution_text = sol["solution"]
        for n in range(1, runs + 1):
            run_n = f"run_{n}"
            if response_exists(response_store_dir, question_id, student_id, approach, model, run_n, response_file):
                print(f"skip {question_id} / {student_id} / {approach} / {model} / {run_n}")
                continue
            response, prompt_text, elapsed = grade_one_run(
                question, solution_text, rubric, system_prompt,
                model, whole_rubric, free_marks
            )
            save_run(
                response_store_dir, question_id, student_id, approach, model, run_n,
                response, prompt_text, elapsed, response_file, prompt_file
            )
            print(f"graded {question_id} / {student_id} / {approach} / {model} / {run_n}")


def main():
    args = parse_args()
    question_map = load_question_map(args.datastore_dir)
    config = APPROACH_CONFIG[args.approach]
    whole_rubric = config["whole_rubric"]
    free_marks = config["free_marks"]

    if args.question_id:
        question_ids = [q.strip() for q in args.question_id.split(",")]
    else:
        question_ids = list(question_map.keys())
    prompt_cache = {}

    for question_id in question_ids:
        if question_id not in question_map:
            print(f"Warning: {question_id} not found in question map, skipping.")
            continue
        question = question_map[question_id]
        qtype = question["question_type"]
        if qtype not in prompt_cache:
            prompt_cache[qtype] = load_system_prompt(args.datastore_dir, args.approach, qtype)
        system_prompt = prompt_cache[qtype]
        solutions = load_solutions(args.datastore_dir, question_id)
        rubric = load_rubric(args.datastore_dir, question_id)
        grade_question(
            question_id, question, solutions, rubric, system_prompt,
            args.model, args.approach, whole_rubric, free_marks, args.runs,
            args.response_store_dir, args.response_file, args.prompt_file,
        )


if __name__ == "__main__":
    main()
