# LLM-Based Automated Code Grading — Dissertation Framework

## Project Overview

MSc Computer Science (Intelligent Systems) dissertation exploring whether LLMs can
reliably grade student algorithm submissions. The framework runs student code solutions
through 4 grading approaches using local LLMs (via Ollama) and compares outputs against
human-graded ground truth across 6 research questions.

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
│   │   └── {question_id}/
│   │       └── rubric.json
│   ├── system_prompt/
│   │   └── approach_n.txt — approach_1.txt, approach_2.txt, approach_3.txt, approach_4.txt
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
    └── graph_rqs/
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

---

## Ground Truth

Human (researcher) manually grades a sample of submissions using task-specific rubrics,
assigning a bucket per rubric point. This CSV is the reference all LLM outputs are
compared against.

---

## Models (local Ollama)

- `tinyllama`
- `qwen2.5-coder:7b`
- `deepseek-coder:6.7b`

---

## Development Standards

- All identifiers, function names, file names: `snake_case`
- One function per responsibility — never merge loading, processing, and saving into one block
- Keep every function under 30 lines; split if it grows beyond that
- No hardcoded paths — accept paths as CLI arguments or pass as function parameters
- No global mutable state — load data inside functions, return it, do not mutate module-level variables
- Validate at system boundaries (CLI input, file reads); trust internal data after that
- No comments explaining what the code does — only add a comment when the WHY is non-obvious
