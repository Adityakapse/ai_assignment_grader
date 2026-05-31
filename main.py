import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import generate_graph
import metrics
import preprocessing
import validation

APPROACHES = ["approach_1", "approach_2", "approach_3", "approach_4"]
MODELS = ["tinyllama", "qwen2.5-coder:7b", "deepseek-coder:6.7b"]


def parse_args():
    # Defines all pipeline paths and flags; skip_* flags allow resuming from any step.
    parser = argparse.ArgumentParser(description="Run the complete grading pipeline end to end.")
    parser.add_argument("--raw_data_dir",        default="raw_data")
    parser.add_argument("--datastore_dir",        default="datastore")
    parser.add_argument("--response_store_dir",   default="response_store")
    parser.add_argument("--result_store_dir",     default="result_store")
    parser.add_argument("--graph_store_dir",      default="graph_store")
    parser.add_argument("--ground_truth",         default="datastore/ground_truth.csv",
                        help="CSV with question_id, student_id, human_total (optional)")
    parser.add_argument("--runs",                 type=int, default=3)
    parser.add_argument("--question_id",          default=None,
                        help="Restrict grading and processing to one question_id")
    parser.add_argument("--skip_preprocessing",   action="store_true")
    parser.add_argument("--skip_grading",         action="store_true")
    parser.add_argument("--skip_graphs",          action="store_true")
    return parser.parse_args()


def _run(label, cmd):
    # Runs a subprocess step, prints a header, and halts the pipeline on non-zero exit.
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\n[PIPELINE ERROR] '{label}' exited with code {result.returncode}. Halting.")
        sys.exit(result.returncode)


def step_preprocessing(args):
    # Step 1: loads raw CSVs and writes the datastore.
    print(f"\n{'=' * 60}\n  Step 1 — Preprocessing\n{'=' * 60}")
    preprocessing.main(args.raw_data_dir, args.datastore_dir)


def step_validation(args):
    # Step 2: checks datastore integrity; exits the pipeline if any check fails.
    print(f"\n{'=' * 60}\n  Step 2 — Validation\n{'=' * 60}")
    validation.main(args.datastore_dir)


def step_grading(args):
    # Step 3: runs grade.py for every approach × model combination via subprocess.
    total = len(APPROACHES) * len(MODELS)
    n = 0
    for approach in APPROACHES:
        for model in MODELS:
            n += 1
            cmd = [
                sys.executable, "src/grade.py",
                "--datastore_dir",       args.datastore_dir,
                "--response_store_dir",  args.response_store_dir,
                "--approach",            approach,
                "--model",               model,
                "--runs",                str(args.runs),
            ]
            if args.question_id:
                cmd += ["--question_id", args.question_id]
            _run(f"Step 3 — Grading [{n}/{total}] {approach} / {model}", cmd)


def step_processing(args):
    # Step 4: runs process.py via subprocess to parse all LLM responses into result.csv.
    cmd = [
        sys.executable, "src/process.py",
        "--response_store_dir", args.response_store_dir,
        "--result_store_dir",   args.result_store_dir,
        "--datastore_dir",      args.datastore_dir,
    ]
    if args.question_id:
        cmd += ["--question_id", args.question_id]
    _run("Step 4 — Processing", cmd)


def step_metrics(args):
    # Step 5: computes all statistical metrics and writes them back into result.csv.
    print(f"\n{'=' * 60}\n  Step 5 — Metrics\n{'=' * 60}")
    metrics.main(args.result_store_dir, args.datastore_dir, ground_truth=args.ground_truth)


def step_graphs(args):
    # Step 6: generates all RQ graphs and saves them to graph_store_dir.
    print(f"\n{'=' * 60}\n  Step 6 — Graphs\n{'=' * 60}")
    generate_graph.main(
        args.result_store_dir,
        args.datastore_dir,
        output_dir=args.graph_store_dir,
        ground_truth=args.ground_truth,
        models=MODELS,
    )


def main():
    args = parse_args()

    if not args.skip_preprocessing:
        step_preprocessing(args)

    step_validation(args)

    if not args.skip_grading:
        step_grading(args)

    step_processing(args)
    step_metrics(args)

    if not args.skip_graphs:
        step_graphs(args)

    print(f"\n{'=' * 60}")
    print("  Pipeline complete.")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
