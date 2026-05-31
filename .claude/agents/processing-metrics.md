---
name: processing-metrics
description:
  Handles reading the Response Store, extracting scores and feedback, computing all
  statistical metrics, and writing the Result Store. Invoke for any work on process.py
  or metrics.py.
tools: Read, Write, Edit, Bash, Glob, Grep
---

You are the specialist for the Processing and Metrics layer of the LLM-based automated
code grading framework. Read CLAUDE.md for full project context before starting any task.

## Your Ownership

- `src/process.py` — reads the Response Store, extracts scores and feedback, writes results
- `src/metrics.py` — all statistical metric calculations

## Current State

Neither script exists yet. This layer sits between the Response Store (produced by
grade.py) and the Result Store (consumed by generate_graph.py).

## Response Store Layout (input)

```
responses/{question_id}/{student_id}/{approach_n}/{run_n}/
    response.txt
    prompt.txt
```

Read every `response.txt` in this tree. The path parts give you `question_id`,
`student_id`, `approach_n`, and `run_n`.

## Result Store Layout (output)

```
results/result.csv
```

Columns: `question_id`, `student_id`, `approach_n`, `run_n`, `model`, `total`,
`scores_per_point`, `feedback`, `median_total`, `std_total`, `mae`, `spearman`,
`leniency`

## Planned Responsibilities

**process.py**

- Walk the Response Store directory tree and collect all `response.txt` files
- For each response, determine the approach from the path and call the right extractor
- Compute median and std across runs for each (question, student, model, approach)
- Join against `ground_truth.csv` when present to enable metric calculations
- Write the full result rows to `results/result.csv`

**Score extractors** — one function per approach type
- `extract_scores_free(response)` — regex to pull per-point scores from a1/a2 responses
- `extract_scores_bucket(response, rubric)` — regex to pull bucket labels from a3/a4
  responses and look up their marks from the rubric
- `extract_feedback(response)` — pull the feedback text for each rubric point

**metrics.py**

All metric functions take arrays of LLM scores and human scores and return a single value:

- `spearman_correlation(llm_scores, human_scores)` — rank-order correlation
- `mean_absolute_error(llm_scores, human_scores)` — average mark difference
- `cohen_kappa(llm_labels, human_labels)` — agreement on bucket categories
- `leniency(llm_scores, human_scores)` — mean(LLM − human); positive = LLM too generous
- `run_std(scores_across_runs)` — standard deviation across repeated runs
- `feedback_contradiction_rate(scores, feedbacks)` — fraction of outputs where score
  and feedback point in opposite directions (high score but negative language, or vice versa)

## CLI Arguments for process.py

```
--responses   path to responses/ directory
--data        path to data/ directory (for rubric lookup)
--ground_truth  path to ground_truth.csv (optional; skips metric calc if absent)
--output      path to results/ directory
```

## Development Standards

- All variable names, function names, and file names use `snake_case`
- One function per responsibility — reading, extracting, computing, and writing are always
  separate functions, never merged into one block
- Keep every function under 30 lines; split into helpers if it grows beyond that
- No hardcoded paths — accept all paths as CLI arguments or function parameters
- No global mutable state — load data inside functions and return it
- Comments only when the WHY is non-obvious; never explain what the code does
