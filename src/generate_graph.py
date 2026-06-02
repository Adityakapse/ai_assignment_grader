import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import spearmanr

PALETTE = sns.color_palette("tab10")
APPROACHES = ["approach_1", "approach_2", "approach_3", "approach_4"]
PRIMARY_MODEL = "qwen2.5-coder:7b"
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
        run_data = subset[subset["run"] == run].groupby("student_id")["total"].first()
        heights = [float(run_data.loc[s]) if s in run_data.index else 0.0
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
                              model=None):
    model = model or PRIMARY_MODEL
    _plot_rq1_runs_figure(df, impl_question, model, output_dir,
                          "rq1_runs_implementation.png")
    _plot_rq1_runs_figure(df, asym_question, model, output_dir,
                          "rq1_runs_asymptotic.png")


def _plot_rq1_deviation_figure(df, model, output_dir, filename):
    df_m = df[df["model"] == model].copy()
    if df_m.empty:
        print(f"Skip {filename}: no data for model {model}")
        return

    approaches = [a for a in APPROACHES if a in df_m["approach"].values]
    deviations = (
        df_m.groupby(["question_id", "student_id", "approach"])["total"]
        .agg(lambda x: (x - x.median()).abs().max())
        .reset_index()
        .rename(columns={"total": "median_dev"})
    )

    students = sorted(deviations["student_id"].unique())
    student_colours = {s: PALETTE[i] for i, s in enumerate(students)}
    rng = np.random.default_rng(42)
    x_positions = np.arange(len(approaches))

    fig, ax = plt.subplots(figsize=(9, 5))
    for i, approach in enumerate(approaches):
        subset = deviations[deviations["approach"] == approach]
        for student in students:
            vals = subset[subset["student_id"] == student]["median_dev"].dropna().values
            if len(vals) == 0:
                continue
            jitter = rng.uniform(-0.15, 0.15, size=len(vals))
            ax.scatter(x_positions[i] + jitter, vals,
                       color=student_colours[student], s=20, alpha=0.7, zorder=3)

    handles = [plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=c,
                           markersize=6, label=s.replace("mut_", ""))
               for s, c in student_colours.items()]
    ax.legend(handles=handles, title="Student", fontsize=8)
    ax.set_xticks(x_positions)
    ax.set_xticklabels([a.replace("approach_", "Approach ") for a in approaches])
    ax.set_ylabel("Max deviation from median run (marks)")
    ax.set_ylim(bottom=0)
    ax.set_title(
        f"RQ1 — Per-student deviation from median score  |  all questions  |  model: {model}",
        fontsize=11,
    )
    plt.tight_layout()
    _save(fig, output_dir, filename)


def plot_rq1_deviation(df, output_dir, model=None):
    model = model or PRIMARY_MODEL
    _plot_rq1_deviation_figure(df, model, output_dir, "rq1_deviation_all_questions.png")


def _plot_rq1_kde_figure(df, gt_df, model, output_dir, filename):
    df_m = df[df["model"] == model].copy()
    if df_m.empty:
        print(f"Skip {filename}: no data for model {model}")
        return

    deduped = _deduplicated_per_student(df_m)
    approach_colours = _approach_colour_map()

    fig, ax = plt.subplots(figsize=(9, 5))
    for approach in APPROACHES:
        vals = deduped[deduped["approach"] == approach]["median"].dropna().values
        if len(vals) < 2:
            continue
        sns.kdeplot(vals, ax=ax, label=approach.replace("approach_", "Approach "),
                    color=approach_colours[approach], linewidth=2, clip=(0, 100))

    if gt_df is not None and "human_total" in gt_df.columns:
        human_vals = gt_df["human_total"].dropna().values
        if len(human_vals) >= 2:
            sns.kdeplot(human_vals, ax=ax, label="Human", color="black",
                        linewidth=2, linestyle="--", clip=(0, 100))

    ax.set_xlim(0, 100)
    ax.set_xlabel("Total marks")
    ax.set_ylabel("Density")
    ax.legend(fontsize=9)
    ax.set_title(
        f"RQ1 — Score distribution by approach vs human  |  model: {model}",
        fontsize=11,
    )
    plt.tight_layout()
    _save(fig, output_dir, filename)


def plot_rq1_score_distribution(df, gt_df, output_dir, model=None):
    model = model or PRIMARY_MODEL
    _plot_rq1_kde_figure(df, gt_df, model, output_dir, "rq1_score_distribution.png")


# ---------------------------------------------------------------------------
# RQ4
# ---------------------------------------------------------------------------

def _plot_rq4_leniency_figure(df, gt_df, model, output_dir, filename):
    if gt_df is None or "human_total" not in gt_df.columns:
        print(f"Skip {filename}: no ground truth data")
        return

    df_m = df[df["model"] == model].copy()
    deduped = _deduplicated_per_student(df_m)
    merged = deduped.merge(
        gt_df[["question_id", "student_id", "human_total"]],
        on=["question_id", "student_id"], how="inner"
    )
    if merged.empty:
        print(f"Skip {filename}: no matched rows after joining ground truth")
        return

    merged["difference"] = merged["median"] - merged["human_total"]
    approaches = [a for a in APPROACHES if a in merged["approach"].values]
    means = merged.groupby("approach")["difference"].mean()

    x = np.arange(len(approaches))
    heights = [means.get(a, 0.0) for a in approaches]
    bar_colours = ["#2ecc71" if h >= 0 else "#e74c3c" for h in heights]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(x, heights, color=bar_colours, width=0.5, edgecolor="white", linewidth=0.8)
    ax.axhline(0, color="black", linewidth=1.2, linestyle="--", zorder=3)

    for bar, h in zip(bars, heights):
        label_y = h + 0.5 if h >= 0 else h - 0.5
        va = "bottom" if h >= 0 else "top"
        ax.text(bar.get_x() + bar.get_width() / 2, label_y,
                f"{h:+.1f}", ha="center", va=va, fontsize=9, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([a.replace("approach_", "Approach ") for a in approaches], fontsize=10)
    ax.set_ylabel("Mean (LLM − Human) marks", fontsize=10)
    ax.set_title(
        f"RQ4 — Leniency by approach  |  model: {model}",
        fontsize=11,
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    plt.tight_layout()
    _save(fig, output_dir, filename)


def plot_rq4_leniency(df, gt_df, output_dir, model=None):
    model = model or PRIMARY_MODEL
    _plot_rq4_leniency_figure(df, gt_df, model, output_dir, "rq4_leniency_by_approach.png")


# ---------------------------------------------------------------------------
# RQ2
# ---------------------------------------------------------------------------

def _plot_rq2_mae_figure(df, gt_df, model, output_dir, filename):
    if gt_df is None or "human_total" not in gt_df.columns:
        print(f"Skip {filename}: no ground truth data")
        return

    df_m = df[df["model"] == model].copy()
    deduped = _deduplicated_per_student(df_m)
    merged = deduped.merge(
        gt_df[["question_id", "student_id", "human_total"]],
        on=["question_id", "student_id"], how="inner"
    )
    if merged.empty:
        print(f"Skip {filename}: no matched rows after joining ground truth")
        return

    merged["abs_error"] = (merged["median"] - merged["human_total"]).abs()
    mae = merged.groupby("approach")["abs_error"].mean()

    # Grouped order: whole rubric (AP1, AP3) then per point (AP2, AP4)
    group_a = ["approach_1", "approach_3"]
    group_b = ["approach_2", "approach_4"]
    ordered = [a for a in group_a if a in mae.index] + \
              [a for a in group_b if a in mae.index]

    # x positions with a gap between groups
    x_positions = []
    for i, a in enumerate(ordered):
        x_positions.append(i if a in group_a else i + 0.6)

    colours = _approach_colour_map()
    heights = [mae.get(a, 0.0) for a in ordered]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(x_positions, heights,
                  color=[colours[a] for a in ordered],
                  width=0.5, edgecolor="white", linewidth=0.8)

    for bar, h in zip(bars, heights):
        ax.text(bar.get_x() + bar.get_width() / 2, h + 0.3,
                f"{h:.1f}", ha="center", va="bottom", fontsize=9, fontweight="bold")

    # Group labels below x-axis
    mid_a = sum(x_positions[:len([a for a in ordered if a in group_a])]) / \
            len([a for a in ordered if a in group_a])
    mid_b = sum(x_positions[len([a for a in ordered if a in group_a]):]) / \
            len([a for a in ordered if a in group_b if a in mae.index])
    ax.text(mid_a, -ax.get_ylim()[1] * 0.12, "Whole Rubric",
            ha="center", fontsize=9, color="gray")
    ax.text(mid_b, -ax.get_ylim()[1] * 0.12, "Per Rubric Point",
            ha="center", fontsize=9, color="gray")

    # Divider between groups
    divider_x = (x_positions[len(group_a) - 1] + x_positions[len(group_a)]) / 2
    ax.axvline(divider_x, color="gray", linestyle="--", linewidth=1, alpha=0.6)

    ax.set_xticks(x_positions)
    ax.set_xticklabels([a.replace("approach_", "AP") for a in ordered], fontsize=10)
    ax.set_ylabel("MAE (marks)", fontsize=10)
    ax.set_title(f"RQ2 — MAE by approach  |  model: {model}", fontsize=11)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    plt.tight_layout()
    _save(fig, output_dir, filename)


def plot_rq2_mae(df, gt_df, output_dir, model=None):
    model = model or PRIMARY_MODEL
    _plot_rq2_mae_figure(df, gt_df, model, output_dir, "rq2_mae_by_approach.png")


def _plot_rq2_spearman_figure(df, gt_df, model, output_dir, filename):
    if gt_df is None or "human_total" not in gt_df.columns:
        print(f"Skip {filename}: no ground truth data")
        return

    df_m = df[df["model"] == model].copy()
    deduped = _deduplicated_per_student(df_m)
    merged = deduped.merge(
        gt_df[["question_id", "student_id", "human_total"]],
        on=["question_id", "student_id"], how="inner"
    )
    if merged.empty:
        print(f"Skip {filename}: no matched rows after joining ground truth")
        return

    group_a = ["approach_1", "approach_3"]
    group_b = ["approach_2", "approach_4"]
    ordered = [a for a in group_a if a in merged["approach"].values] + \
              [a for a in group_b if a in merged["approach"].values]

    rhos = {}
    for approach in ordered:
        subset = merged[merged["approach"] == approach].dropna(subset=["median", "human_total"])
        if len(subset) < 3:
            rhos[approach] = 0.0
            continue
        rho, _ = spearmanr(subset["median"], subset["human_total"])
        rhos[approach] = rho

    x_positions = []
    for i, a in enumerate(ordered):
        x_positions.append(i if a in group_a else i + 0.6)

    colours = _approach_colour_map()
    heights = [rhos[a] for a in ordered]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(x_positions, heights,
                  color=[colours[a] for a in ordered],
                  width=0.5, edgecolor="white", linewidth=0.8)

    for bar, h in zip(bars, heights):
        label_y = h + 0.02 if h >= 0 else h - 0.02
        va = "bottom" if h >= 0 else "top"
        ax.text(bar.get_x() + bar.get_width() / 2, label_y,
                f"{h:.2f}", ha="center", va=va, fontsize=9, fontweight="bold")

    n_a = len([a for a in ordered if a in group_a])
    n_b = len([a for a in ordered if a in group_b])
    mid_a = sum(x_positions[:n_a]) / n_a
    mid_b = sum(x_positions[n_a:]) / n_b
    ax.text(mid_a, -1.18, "Whole Rubric", ha="center", fontsize=9, color="gray")
    ax.text(mid_b, -1.18, "Per Rubric Point", ha="center", fontsize=9, color="gray")

    divider_x = (x_positions[n_a - 1] + x_positions[n_a]) / 2
    ax.axvline(divider_x, color="gray", linestyle="--", linewidth=1, alpha=0.6)
    ax.axhline(0, color="black", linewidth=1, linestyle="--")

    ax.set_xticks(x_positions)
    ax.set_xticklabels([a.replace("approach_", "AP") for a in ordered], fontsize=10)
    ax.set_ylabel("Spearman ρ", fontsize=10)
    ax.set_ylim(-1, 1)
    ax.set_title(f"RQ2 — Spearman correlation by approach  |  model: {model}", fontsize=11)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    plt.tight_layout()
    _save(fig, output_dir, filename)


def plot_rq2_spearman(df, gt_df, output_dir, model=None):
    model = model or PRIMARY_MODEL
    _plot_rq2_spearman_figure(df, gt_df, model, output_dir, "rq2_spearman_by_approach.png")


def _plot_rq2_time_figure(df, models, output_dir, filename):
    group_a = ["approach_1", "approach_3"]
    group_b = ["approach_2", "approach_4"]
    ordered = [a for a in group_a if a in df["approach"].values] + \
              [a for a in group_b if a in df["approach"].values]

    model_colours = _model_colour_map(models)
    bar_width = 0.22
    n_models = len(models)
    offsets = np.linspace(-(n_models - 1) / 2, (n_models - 1) / 2, n_models) * bar_width

    # x positions with gap between groups
    x_positions = []
    for i, a in enumerate(ordered):
        x_positions.append(i if a in group_a else i + 0.7)

    fig, ax = plt.subplots(figsize=(10, 5))

    for j, model in enumerate(models):
        df_m = df[df["model"] == model]
        means = df_m.groupby("approach")["time_seconds"].mean()
        heights = [means.get(a, 0.0) for a in ordered]
        xpos = [x + offsets[j] for x in x_positions]
        bars = ax.bar(xpos, heights, width=bar_width,
                      color=model_colours[model], label=model,
                      edgecolor="white", linewidth=0.6)
        for bar, h in zip(bars, heights):
            if h > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, h + 0.3,
                        f"{h:.0f}s", ha="center", va="bottom", fontsize=7)

    n_a = len([a for a in ordered if a in group_a])
    n_b = len([a for a in ordered if a in group_b])
    mid_a = sum(x_positions[:n_a]) / n_a
    mid_b = sum(x_positions[n_a:]) / n_b
    y_label = -ax.get_ylim()[1] * 0.1
    ax.text(mid_a, y_label, "Whole Rubric", ha="center", fontsize=9, color="gray")
    ax.text(mid_b, y_label, "Per Rubric Point", ha="center", fontsize=9, color="gray")

    divider_x = (x_positions[n_a - 1] + x_positions[n_a]) / 2
    ax.axvline(divider_x, color="gray", linestyle="--", linewidth=1, alpha=0.6)

    ax.set_xticks(x_positions)
    ax.set_xticklabels([a.replace("approach_", "AP") for a in ordered], fontsize=10)
    ax.set_ylabel("Avg time per grading (seconds)", fontsize=10)
    ax.set_title("RQ2 — Average grading time by approach", fontsize=11)
    ax.legend(title="Model", fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    plt.tight_layout()
    _save(fig, output_dir, filename)


def plot_rq2_time(df, output_dir, models=None):
    models = models or sorted(df["model"].dropna().unique().tolist())
    _plot_rq2_time_figure(df, models, output_dir, "rq2_time_by_approach.png")


# ---------------------------------------------------------------------------
# RQ3
# ---------------------------------------------------------------------------

def _plot_rq3_stability_figure(df, output_dir, filename):
    deviations = (
        df.groupby(["question_id", "student_id", "approach", "model"])["total"]
        .agg(lambda x: (x - x.median()).abs().max())
        .reset_index()
        .rename(columns={"total": "max_dev"})
    )

    approach_colours = _approach_colour_map()
    approaches = [a for a in APPROACHES if a in deviations["approach"].values]
    models = sorted(deviations["model"].dropna().unique().tolist())

    fig, ax = plt.subplots(figsize=(11, 5))
    sns.boxplot(
        data=deviations,
        x="model", y="max_dev", hue="approach",
        order=models,
        hue_order=approaches,
        palette={a: approach_colours[a] for a in approaches},
        width=0.6, linewidth=1.2, fliersize=4,
        ax=ax,
    )

    ax.set_xlabel("Model", fontsize=10)
    ax.set_ylabel("Max deviation from median run (marks)", fontsize=10)
    ax.set_title("RQ3 — Score stability across runs by model and approach", fontsize=11)
    ax.set_xticks(range(len(models)))
    ax.set_xticklabels([m.split(":")[0] for m in models], fontsize=9)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, [l.replace("approach_", "Approach ") for l in labels],
              title="Approach", fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    plt.tight_layout()
    _save(fig, output_dir, filename)


def plot_rq3_stability(df, output_dir):
    _plot_rq3_stability_figure(df, output_dir, "rq3_stability_by_model.png")


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
        plot_rq1_deviation(df, output_dir)
        plot_rq1_score_distribution(df, gt_df, output_dir)
    if "rq2" in rq_set:
        plot_rq2_mae(df, gt_df, output_dir)
        plot_rq2_spearman(df, gt_df, output_dir)
        plot_rq2_time(df, output_dir, models=models)
    if "rq3" in rq_set:
        plot_rq3_stability(df, output_dir)
    if "rq4" in rq_set:
        plot_rq4_leniency(df, gt_df, output_dir)


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
