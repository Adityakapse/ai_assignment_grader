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

# MODELS = ["tinyllama", "qwen2.5-coder:7b", "qwen2.5-coder:14b"]
# MODELS = ["qwen2.5-coder:14b", "deepseek-coder:16b", "gemma4:31b-it-q4_K_M"]
# MODELS = ["qwen2.5-coder:14b","gemma4:26b"]
# OLLAMA_MODELS = ["Qwen3:14b","devstral-small-2","gemma4:26b"]
# OLLAMA_MODELS = ["Qwen3:14b"]
OLLAMA_MODELS = []
# NIM_MODELS    = ["nvidia/nemotron-3-super-120b-a12b","openai/gpt-oss-120b"]
NIM_MODELS    = ["openai/gpt-oss-120b"]

# ALL_MODELS    = NIM_MODELS
ALL_MODELS    = OLLAMA_MODELS + NIM_MODELS


NIM_API_KEY = os.environ.get("NIM_API_KEY", "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")





def parse_args():
    # Defines all pipeline paths and flags; skip_* flags allow resuming from any step.
    parser = argparse.ArgumentParser(description="Run the complete grading pipeline end to end.")
    parser.add_argument("--raw_data_dir",        default="raw_data")
    parser.add_argument("--datastore_dir",        default="datastore")
    parser.add_argument("--response_store_dir",   default="response_store")
    parser.add_argument("--result_store_dir",     default="result_store")
    parser.add_argument("--graph_store_dir",      default="graph_store")
    parser.add_argument("--ground_truth",         default=None,
                        help="CSV with question_id, student_id, human_total; defaults to <datastore_dir>/ground_truth.csv")
    parser.add_argument("--assignment",           default=None,
                        help="Grade an assignment under datastore/<name>/ and write to result_store/<name>/; the default run is untouched")
    parser.add_argument("--approaches",           nargs="+", choices=APPROACHES, default=None,
                        help="Subset of approaches to run; defaults to all four")
    parser.add_argument("--ollama_models",        nargs="+", default=None,
                        help="Override the Ollama model list for this run")
    parser.add_argument("--nim_models",           nargs="+", default=None,
                        help="Override the NIM model list for this run")
    parser.add_argument("--runs",                 type=int, default=3)
    parser.add_argument("--question_id",          default=None,
                        help="Restrict grading and processing to one question_id")
    parser.add_argument("--skip_preprocessing",   action="store_true")
    parser.add_argument("--skip_grading",         action="store_true")
    parser.add_argument("--skip_processing",      action="store_true")
    parser.add_argument("--skip_graphs",          action="store_true")
    return parser.parse_args()


def resolve_paths(args):
    # Redirects every store to a per-assignment subfolder; the default run (no --assignment) is unchanged.
    if args.assignment:
        args.datastore_dir    = os.path.join(args.datastore_dir, args.assignment)
        args.result_store_dir = os.path.join(args.result_store_dir, args.assignment)
        args.graph_store_dir  = os.path.join(args.graph_store_dir, args.assignment)
    if args.ground_truth is None:
        args.ground_truth = os.path.join(args.datastore_dir, "ground_truth.csv")


def resolve_models(args):
    # Picks the approaches and model lists for this run, falling back to the module defaults.
    approaches    = args.approaches if args.approaches else APPROACHES
    ollama_models = args.ollama_models if args.ollama_models is not None else OLLAMA_MODELS
    nim_models    = args.nim_models if args.nim_models is not None else NIM_MODELS
    return approaches, ollama_models, nim_models


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


def _grade_model_list(args, models, backend, api_key, n_start, total, approaches):
    n = n_start
    for approach in approaches:
        for model in models:
            n += 1
            cmd = [
                sys.executable, os.path.join("src", "grade.py"),
                "--datastore_dir",       args.datastore_dir,
                "--response_store_dir",  args.response_store_dir,
                "--approach",            approach,
                "--model",               model,
                "--runs",                str(args.runs),
                "--backend",             backend,
                "--api_key",             api_key,
            ]
            if args.question_id:
                cmd += ["--question_id", args.question_id]
            _run(f"Step 3 — Grading [{n}/{total}] {approach} / {model}", cmd)
    return n


def step_grading(args, approaches, ollama_models, nim_models):
    # Step 3: runs grade.py for every approach × model combination via subprocess.
    total = len(approaches) * len(ollama_models + nim_models)
    n = _grade_model_list(args, ollama_models, "ollama", "",          0,     total, approaches)
    _grade_model_list(args, nim_models,    "nim",    NIM_API_KEY,  n,     total, approaches)


def step_processing(args):
    # Step 4: runs process.py via subprocess to parse all LLM responses into result.csv.
    cmd = [
        sys.executable, os.path.join("src", "process.py"),
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


def step_graphs(args, all_models):
    # Step 6: generates all RQ graphs and saves them to graph_store_dir.
    print(f"\n{'=' * 60}\n  Step 6 — Graphs\n{'=' * 60}")
    generate_graph.main(
        args.result_store_dir,
        args.datastore_dir,
        output_dir=args.graph_store_dir,
        ground_truth=args.ground_truth,
        models=[m.split("/")[-1] for m in all_models],
    )


def main():
    args = parse_args()
    resolve_paths(args)
    approaches, ollama_models, nim_models = resolve_models(args)
    all_models = ollama_models + nim_models

    if not args.skip_preprocessing:
        step_preprocessing(args)

    step_validation(args)

    if not args.skip_grading:
        step_grading(args, approaches, ollama_models, nim_models)

    if not args.skip_processing:
        step_processing(args)
        step_metrics(args)

    if not args.skip_graphs:
        step_graphs(args, all_models)

    print(f"\n{'=' * 60}")
    print("  Pipeline complete.")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
