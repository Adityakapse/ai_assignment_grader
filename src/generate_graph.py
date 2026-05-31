import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

PALETTE = sns.color_palette("tab10")
APPROACHES = ["approach_1", "approach_2", "approach_3", "approach_4"]
DPI = 150


def load_results(result_store_dir):
    path = os.path.join(result_store_dir, "result.csv")
    df = pd.read_csv(path)
    numeric_cols = [
        "total", "median", "run_std", "mae", "spearman_rho",
        "time_seconds", "leniency", "feedback_contradiction_rate",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "format_ok" in df.columns:
        df["format_ok"] = (
            df["format_ok"].astype(str).str.strip().str.lower()
            .map(lambda v: v in ("true", "1", "yes"))
        )
    return df


def load_ground_truth(path):
    if path is None or not os.path.isfile(path):
        return None
    gt = pd.read_csv(path)
    gt["human_total"] = pd.to_numeric(gt["human_total"], errors="coerce")
    return gt


def load_solutions(datastore_dir):
    path = os.path.join(datastore_dir, "solutions", "solutions.csv")
    if not os.path.isfile(path):
        return None
    return pd.read_csv(path)


def _save(fig, output_dir, filename):
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def _approach_colour_map():
    return {app: PALETTE[i] for i, app in enumerate(APPROACHES)}


def _model_colour_map(models):
    return {mdl: PALETTE[i] for i, mdl in enumerate(models)}


def _deduplicated_per_student(df):
    return df.drop_duplicates(subset=["question_id", "student_id", "model", "approach"])


def _check_column_nonempty(df, col, graph_name):
    if col not in df.columns or df[col].isna().all():
        print(f"Skip {graph_name}: column '{col}' is empty or missing.")
        return False
    return True


# ---------------------------------------------------------------------------
# RQ1
# ---------------------------------------------------------------------------

def _draw_delta_bracket(ax, x_center, heights, width_span, margin=4):
    delta = max(heights) - min(heights)
    top = max(heights) + margin
    half = width_span / 2
    tick = 1.5
    ax.plot([x_center - half, x_center + half], [top, top], "k-", lw=1)
    ax.plot([x_center - half, x_center - half], [top - tick, top], "k-", lw=1)
    ax.plot([x_center + half, x_center + half], [top - tick, top], "k-", lw=1)
    ax.text(x_center, top + 1, f"Δ={delta:.0f}", ha="center", va="bottom",
            fontsize=8, fontweight="bold")


def _rq1_runs_subplot(ax, df_q, approach, students, runs):
    subset = df_q[df_q["approach"] == approach]
    x = np.arange(len(students))
    width = 0.7 / len(runs)
    for i, run in enumerate(runs):
        run_data = subset[subset["run"] == run].set_index("student_id")
        heights = [float(run_data.loc[s, "total"]) if s in run_data.index else 0.0
                   for s in students]
        offset = (i - (len(runs) - 1) / 2) * width
        ax.bar(x + offset, heights, width, label=run.replace("run_", "Run "),
               color=PALETTE[i])
    for j, student in enumerate(students):
        heights = subset[subset["student_id"] == student]["total"].dropna().tolist()
        if len(heights) >= 2:
            _draw_delta_bracket(ax, float(x[j]), heights, width * len(runs))
    ax.set_title(approach.replace("approach_", "Approach "), fontsize=10)
    ax.set_xticks(x)
    ax.set_xticklabels([s.replace("mut_", "") for s in students], fontsize=9)
    ax.set_ylabel("Total marks")
    ax.set_ylim(0, 120)
    ax.legend(fontsize=7, title="Run")


def _plot_rq1_runs_figure(df, question_id, model, output_dir, filename):
    df_q = df[(df["question_id"] == question_id) & (df["model"] == model)].copy()
    if df_q.empty:
        print(f"Skip {filename}: no data for {question_id} / {model}")
        return
    approaches = [a for a in APPROACHES if a in df_q["approach"].values]
    runs = sorted(df_q["run"].unique())
    students = [s for s in ["mut_correct", "mut_semi", "mut_wrong"]
                if s in df_q["student_id"].values]
    fig, axes = plt.subplots(2, 2, figsize=(12, 10), sharey=True)
    axes = axes.flatten()
    for ax, approach in zip(axes, approaches):
        _rq1_runs_subplot(ax, df_q, approach, students, runs)
    for ax in axes[len(approaches):]:
        ax.set_visible(False)
    fig.suptitle(
        f"RQ1 — Score consistency across runs  |  {question_id}  |  model: {model}",
        fontsize=11,
    )
    plt.tight_layout()
    _save(fig, output_dir, filename)


def plot_rq1_run_consistency(df, output_dir,
                              impl_question="19_20-1-1-java",
                              asym_question="asym-1-java",
                              model="qwen2.5-coder:7b"):
    _plot_rq1_runs_figure(df, impl_question, model, output_dir,
                          "rq1_runs_implementation.png")
    _plot_rq1_runs_figure(df, asym_question, model, output_dir,
                          "rq1_runs_asymptotic.png")


# ---------------------------------------------------------------------------
# RQ graphs go here — added one at a time after discussion
# ---------------------------------------------------------------------------


def main(result_store_dir, datastore_dir, output_dir="graph_store",
         ground_truth=None, rq=None, models=None):
    df = load_results(result_store_dir)
    gt_df = load_ground_truth(ground_truth)
    rq_set = set(rq) if rq else {"rq1", "rq2", "rq3", "rq4", "rq5", "rq6"}
    models = models or sorted(df["model"].dropna().unique().tolist())
    print(f"Loaded {len(df)} result rows. RQs to plot: {sorted(rq_set)}")
    if "rq1" in rq_set:
        plot_rq1_run_consistency(df, output_dir)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate dissertation graphs")
    parser.add_argument("--result-store", required=True)
    parser.add_argument("--datastore", required=True)
    parser.add_argument("--output-dir", default="graph_store")
    parser.add_argument("--ground-truth", default=None)
    parser.add_argument("--rq", nargs="*", default=None,
                        help="Which RQs to plot, e.g. --rq rq1 rq3")
    args = parser.parse_args()

    main(
        result_store_dir=args.result_store,
        datastore_dir=args.datastore,
        output_dir=args.output_dir,
        ground_truth=args.ground_truth,
        rq=args.rq,
    )
