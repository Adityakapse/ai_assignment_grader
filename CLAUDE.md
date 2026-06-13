# LLM-Based Automated Code Grading — Dissertation Framework

## Project Overview

MSc Computer Science (Intelligent Systems) dissertation exploring whether LLMs can
reliably grade student algorithm submissions. The framework runs student code solutions
through 4 grading approaches using local LLMs (via Ollama) and cloud LLMs (via NVIDIA NIM)
and compares outputs against human-graded ground truth across 6 research questions.

---

## Pipeline Architecture

```
Raw Dataset
    └── preprocessing.py
            └── datastore/             (Datastore)
                    └── validation.py
                            └── grade.py
                                    └── response_store/    (Response Store)
                                            └── process.py + metrics.py
                                                    └── result_store/      (Result Store)
                                                            └── generate_graph.py
                                                                    └── graph_store/
```

---

## Folder Structure

```
.
├── CLAUDE.md
├── architecture_pipeline.png
├── raw_data/                — Raw Dataset (input to preprocessing)
│   └── AD2022dataset/
├── src/
│   ├── preprocessing.py     — loads + cleans raw dataset CSVs
│   ├── validation.py        — checks datastore before grading
│   ├── grade.py             — builds prompts, calls LLMs, saves responses
│   ├── process.py           — reads responses, extracts scores and feedback
│   ├── metrics.py           — all statistical metrics (Spearman, Cohen's k, MAE …)
│   └── generate_graph.py    — produces all RQ plots
├── datastore/               — Datastore (output of preprocessing)
│   ├── questions/
│   │   └── question.csv     — question_id, question_title, question_desc, sample_solution
│   ├── solutions/
│   │   └── solutions.csv    — student_id, question_id, solution
│   ├── rubrics/
│   │   └── {task_id}/
│   │       └── rubric.json
│   ├── ground_truth.csv     — human-graded reference scores
│   ├── system_prompt/
│   │   ├── approach_1..4.txt          — implementation question prompts
│   │   └── analysis_approach_1..4.txt — analysis/asymptotic question prompts
│   └── tests/
│       └── {question_id}/
├── response_store/          — Response Store
│   └── {question_id}/
│       └── {student_id}/
│           └── {approach_n}/
│               └── {model}/
│                   └── {run_n}/
│                       ├── response.txt
│                       └── prompt.txt
├── result_store/            — Result Store
│   └── result.csv           — question_id, student_id, approach_n, run_n, total, metrics
└── graph_store/             — Graph Store
    ├── overall/             — graphs across all questions
    ├── implementation/      — graphs for implementation questions only (19_20- prefix)
    └── asymptotic/          — graphs for asymptotic analysis questions only (asym- prefix)
```

---

## 4 Grading Approaches

| Approach   | Rubric granularity | Scoring mode       |
|------------|--------------------|--------------------|
| approach_1 | Whole rubric       | LLM freely marks   |
| approach_2 | Per rubric point   | LLM freely marks   |
| approach_3 | Whole rubric       | Classify to bucket |
| approach_4 | Per rubric point   | Classify to bucket |

Every approach runs 3 times per (question, student, model). Median of 3 runs = final score.

---

## 6 Research Questions

- **RQ1**: Classifier vs free marker — consistency and agreement with human grades
- **RQ2**: Whole rubric vs point-by-point — accuracy and time cost
- **RQ3**: Robustness — how stable are scores across repeated runs per model and approach
- **RQ4**: Bias — too strict, too generous, middle-ground avoidance, length bias
- **RQ5**: Feedback quality — grounded, factually correct, consistent with score
- **RQ6**: Failure modes — what type of mistakes do LLMs make, are they systematic

---

## Rubric Schema

`datastore/rubrics/{question_id}/rubric.json`:

```json
{
  "question_id": "string",
  "total_marks": 100,
  "rubric_points": [
    {
      "id": 1,
      "title": "short title",
      "description": "what is being assessed",
      "buckets": [
        { "label": "Correct", "marks": 40, "description": "criterion fully met" },
        { "label": "Semi",    "marks": 20, "description": "criterion partially met" },
        { "label": "Wrong",   "marks": 0,  "description": "criterion not met" }
      ]
    }
  ]
}
```

Every rubric has exactly 3 buckets: `Correct`, `Semi`, `Wrong`. The `Correct` values sum to 100.
The `Internally consistent but incorrect final result` bucket was removed from all rubrics.

---

## Ground Truth

Human (researcher) manually grades a sample of submissions using task-specific rubrics,
assigning a bucket per rubric point. This CSV is the reference all LLM outputs are
compared against.

---

## Models

### Local (Ollama)
- `qwen2.5-coder:14b`
- `qwen3:14b`
- `devstral-small-2`

### Cloud (NVIDIA NIM — free endpoint)
- `nvidia/nemotron-3-super-120b-a12b`

Model lists are defined in `main.py` as `OLLAMA_MODELS`, `NIM_MODELS`, and `ALL_MODELS`.
`NIM_API_KEY` is read from the `NIM_API_KEY` environment variable.
`grade.py` selects the backend via `--backend ollama|nim`; folder names in `response_store`
use only the model name (vendor prefix stripped), e.g. `nemotron-3-super-120b-a12b`.

---

## Development Standards

- All identifiers, function names, file names: `snake_case`
- One function per responsibility — never merge loading, processing, and saving into one block
- Keep every function under 30 lines; split if it grows beyond that
- No hardcoded paths — accept paths as CLI arguments or pass as function parameters
- No global mutable state — load data inside functions, return it, do not mutate module-level variables
- Validate at system boundaries (CLI input, file reads); trust internal data after that
- No comments explaining what the code does — only add a comment when the WHY is non-obvious
