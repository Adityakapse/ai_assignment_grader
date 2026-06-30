import os
import re
import sys
import tempfile

_EXPLORER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _EXPLORER)
sys.path.insert(0, os.path.dirname(_EXPLORER))

import streamlit as st

import components as ui
import data_access as da
import generate_graph as gg

PLOTS = [
    ("plot_rq1_run_consistency", ["df", "out", "impl_q", "asym_q", "model"]),
    ("plot_rq1_deviation", ["df", "out", "model"]),
    ("plot_rq1_score_distribution", ["df", "gt", "out", "model"]),
    ("plot_rq2_mae", ["df", "gt", "out", "models"]),
    ("plot_rq2_spearman", ["df", "gt", "out", "model"]),
    ("plot_rq2_time", ["df", "out", "models"]),
    ("plot_rq3_stability", ["df", "out", "models"]),
    ("plot_rq3_format_failures", ["df", "out", "models"]),
    ("plot_rq4_leniency", ["df", "gt", "out", "model"]),
    ("plot_rq4_leniency_scatter", ["df", "gt", "out", "model"]),
    ("plot_rq4_bucket_distribution", ["df", "gt", "datastore", "out", "model"]),
    ("plot_rq4_length_bias", ["df", "datastore", "out", "model"]),
]


@st.cache_data(show_spinner="Loading data…")
def scoped_inputs(scope):
    # Loads the raw result and ground-truth frames, restricted to the two models and the scope.
    result_store = os.path.dirname(da.paths()["result_csv"])
    df = gg.load_results(result_store)
    df = ui.scope_filter(df[df["model"].isin(da.PRODUCTION_MODELS)], scope)
    gt = gg.load_ground_truth(da.paths()["ground_truth_csv"])
    gt = ui.scope_filter(gt, scope) if gt is not None else None
    return df, gt


def _call_args(spec, df, gt, model, out):
    # Maps a plot function's argument spec to concrete values for the current selection.
    values = {
        "df": df, "gt": gt, "out": out, "model": model,
        "models": list(da.PRODUCTION_MODELS.keys()),
        "datastore": da.paths()["datastore"],
        "impl_q": gg.IMPL_QUESTION, "asym_q": gg.ASYM_QUESTION,
    }
    return [values[name] for name in spec]


@st.cache_data(show_spinner="Generating graphs…")
def build_images(scope, model):
    # Runs every plot function and returns the rendered PNGs as (clean_title, bytes) pairs.
    df, gt = scoped_inputs(scope)
    out = tempfile.mkdtemp()
    for func_name, spec in PLOTS:
        try:
            getattr(gg, func_name)(*_call_args(spec, df, gt, model, out))
        except Exception:
            continue
    return _read_pngs(out)


def _clean_title(filename):
    # Strips the leading rq-number prefix and turns the filename into a readable title.
    name = re.sub(r"^rq\d+_", "", filename.replace(".png", ""))
    return name.replace("_", " ").strip().capitalize()


def _read_pngs(directory):
    # Collects (clean_title, bytes) for every PNG the plot functions wrote to a directory.
    images = []
    for name in sorted(os.listdir(directory)):
        if name.endswith(".png"):
            with open(os.path.join(directory, name), "rb") as f:
                images.append((_clean_title(name), f.read()))
    return images


def main():
    st.set_page_config(page_title="Graphs", layout="wide")
    model, _approach, scope = ui.sidebar_controls()
    st.title("Graphs")
    st.caption(f"Model **{model}** · scope **{scope}** (multi-model charts use both production models)")
    images = build_images(scope, model)
    if not images:
        st.info("No graphs available for this selection.")
        return
    for title, data in images:
        with st.expander(title, expanded=False):
            st.image(data, use_container_width=True)


main()
