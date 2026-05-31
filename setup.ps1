# Run this in PowerShell as Administrator
# If you get an execution policy error, first run:
#   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

$ErrorActionPreference = "Stop"

# ── 1. Python libraries ────────────────────────────────────────────────────────
Write-Host "`nInstalling Python libraries..." -ForegroundColor Cyan
pip install matplotlib numpy pandas requests scikit-learn scipy seaborn
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: pip install failed. Make sure Python and pip are on your PATH." -ForegroundColor Red
    exit 1
}
Write-Host "Libraries installed." -ForegroundColor Green

# ── 2. Ollama models ───────────────────────────────────────────────────────────
$models = @(
    "qwen2.5-coder:14b",
    "deepseek-coder:16b",
    "gemma4:31b-it-q4_K_M"
)

foreach ($model in $models) {
    Write-Host "`nPulling $model ..." -ForegroundColor Cyan
    ollama pull $model
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to pull $model" -ForegroundColor Red
        exit 1
    }
    Write-Host "$model ready." -ForegroundColor Green
}

# ── 3. Run main.py ─────────────────────────────────────────────────────────────
Write-Host "`nAll models ready. Running main.py..." -ForegroundColor Cyan
python main.py --skip_preprocessing --skip_grading `
    --question_id "19_20-1-1-java,19_20-2-1-java,19_20-2-2-java,19_20-3-1-java,19_20-4-1-java,asym-1-java,asym-2-java,asym-3-java,asym-4-java,asym-5-java"

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: main.py exited with an error." -ForegroundColor Red
    exit 1
}

Write-Host "`nDone." -ForegroundColor Green
