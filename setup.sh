#!/bin/bash
set -e

# ── 1. Python libraries ────────────────────────────────────────────────────────
echo "Installing Python libraries..."
pip install matplotlib numpy pandas requests scikit-learn scipy seaborn
echo "Libraries installed."

# ── 2. Ollama models ───────────────────────────────────────────────────────────
models=(
    "qwen2.5-coder:14b"
    "deepseek-coder:16b"
    "gemma4:31b-it-q4_K_M"
)

for model in "${models[@]}"; do
    echo "Pulling $model ..."
    ollama pull "$model"
    echo "$model ready."
done

# ── 3. Run main.py ─────────────────────────────────────────────────────────────
echo "All models ready. Running main.py..."
python main.py --skip_preprocessing --skip_grading \
    --question_id "19_20-1-1-java,19_20-2-1-java,19_20-2-2-java,19_20-3-1-java,19_20-4-1-java,asym-1-java,asym-2-java,asym-3-java,asym-4-java,asym-5-java"

echo "Done."
