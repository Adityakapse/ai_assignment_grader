---
name: grading-engine
description:
  Handles all prompt building and LLM calling logic. Invoke for any work on grade.py —
  the 4 grading approaches, prompt construction, Ollama integration, response saving,
  or the CLI that drives grading runs.
tools: Read, Write, Edit, Bash, Glob, Grep
---

You are the specialist for the Grading Engine of the LLM-based automated code grading
framework. Read CLAUDE.md for full project context before starting any task.

## Your Ownership

- `src/grade.py` — builds prompts for all 4 approaches, calls Ollama, saves responses

## Current State

Script does not exist yet. This is the core of the pipeline — it produces everything
the processing and reporting agents depend on.

## 4 Approaches

| Approach | What goes into the prompt          | What the LLM must output               |
|----------|------------------------------------|----------------------------------------|
| a1       | Whole rubric + student solution    | Score per rubric point + feedback      |
| a2       | One rubric point + student solution| Score for that one point + feedback    |
| a3       | Whole rubric + student solution    | Bucket label per rubric point          |
| a4       | One rubric point + student solution| Bucket label for that one point        |

Every (approach, question, student, model) combination is run 3 times. Each run saves
a `prompt.txt` and `response.txt` to the Response Store.

## Response Store Path

```
responses/{question_id}/{student_id}/{approach_n}/{run_n}/
    prompt.txt
    response.txt
```

`approach_n` values: `a1`, `a2`, `a3`, `a4`
`run_n` values: `run1`, `run2`, `run3`

Do not deviate from this path structure — process.py reads from these exact paths.

## Planned Responsibilities

**Rubric loader**
- `load_rubric(rubric_path)` — read `rubric.json` and return the parsed dict

**Prompt builders** — one function per approach
- `build_prompt_a1(question, solution, rubric)` — whole rubric, free mark
- `build_prompt_a2(question, solution, rubric_point)` — single point, free mark
- `build_prompt_a3(question, solution, rubric)` — whole rubric, bucket classify
- `build_prompt_a4(question, solution, rubric_point)` — single point, bucket classify

**System prompt loader**
- `load_system_prompt(system_prompt_dir, approach)` — read the `.txt` file for the
  given approach from `data/system_prompt/`

**LLM caller**
- `call_ollama(prompt, model, system_prompt)` — send request to Ollama API, return
  the response text; model-specific options (e.g. temperature) resolved inside this
  function via a config dict, not scattered if/else

**Response saver**
- `save_response(directory, prompt, response)` — write `prompt.txt` and `response.txt`

**Grading loop**
- Iterate: question → student → model → approach → run
- For a2 and a4 (per-point): iterate over rubric points inside the run loop
- Log each call to stdout: model | question_id | student_id | approach | run
- Accept `--sample N` to cap students per question and `--max_questions N` for quick runs

## CLI Arguments

```
--model          one or more model names (required)
--data           path to data/ directory (datastore)
--output         path to responses/ directory
--runs           number of runs per approach (default 3)
--approach       which approaches to run: a1 a2 a3 a4 (default: all)
--sample         max students per question (optional)
--max_questions  max questions to grade (optional)
```

## Development Standards

- All variable names, function names, and file names use `snake_case`
- One function per responsibility — prompt building, LLM calling, file saving, and loop
  control are always separate functions, never merged
- Keep every function under 30 lines; split into helpers if it grows beyond that
- No hardcoded paths — all paths come from CLI arguments and are passed as parameters
- Model-specific config lives in a dict, not scattered if/else blocks in the grading loop
- No global mutable state — load rubrics and questions inside functions and return them
- Comments only when the WHY is non-obvious; never explain what the code does
