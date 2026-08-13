# Dependencies

You must have Python 3 and the following libraries:

For pandas        : pip install pandas
For numpy         : pip install numpy
For scipy         : pip install scipy
For scikit-learn  : pip install scikit-learn
For matplotlib    : pip install matplotlib
For seaborn       : pip install seaborn
For streamlit     : pip install streamlit
For python-dotenv : pip install python-dotenv
For requests      : pip install requests
For openai        : pip install openai

# For local models (Ollama)

Ollama must be installed and running on `http://localhost:11434`, and each model you
intend to use must be pulled first

ollama pull qwen3:14b
ollama pull devstral-small-2

# For cloud models (API key)

Create a `.env` file in the project root with the keys for whichever provider you use

NIM_API_KEY=your_nvidia_nim_key_here
GEMINI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here

`NIM_API_KEY` is read automatically. Any other key is selected per run with `--api_key_env`.


# For running the code run main.py :

# structure :

python3 main.py [optional arguments]

Note: the built-in model lists in `main.py` are empty currently. You must
specify the models for the run with `--nim_models`, `--ollama_models`, or `--other_models`.


# arguments :

--raw_data_dir        : folder holding the raw cohort CSVs           (default: raw_data)
                        input to Step 1 preprocessing

--datastore_dir       : cleaned dataset folder                       (default: datastore)
                        holds questions, solutions, rubrics, system prompts, ground truth

--response_store_dir  : where raw LLM responses are saved            (default: response_store)
                        one folder per question/student/approach/model/run

--result_store_dir    : where result.csv is written                  (default: result_store)

--graph_store_dir     : where the generated graphs are saved         (default: graph_store)

--ground_truth        : CSV of human grades to compare against
                        (default: <datastore_dir>/ground_truth.csv)

--assignment          : grade an assignment under datastore/<name>/ and write results to
                        result_store/<name>/ ; the main dissertation run stays untouched

--approaches          : approach_1, approach_2, approach_3, approach_4
                        subset of approaches to run                  (default: all four)

--ollama_models       : list of local Ollama models to grade with
                        e.g. --ollama_models qwen3:14b devstral-small-2

--nim_models          : list of NVIDIA NIM models to grade with
                        e.g. --nim_models openai/gpt-oss-120b

--other_models        : models for any generic OpenAI-compatible provider
                        requires --base_url and --api_key_env

--base_url            : OpenAI-compatible endpoint used by --other_models

--api_key_env         : name of the .env variable holding the key for --other_models

--runs                : number of grading runs per submission        (default: 3)
                        the median of the runs is used as the final score

--question_id         : restrict grading and processing to one or more question_ids
                        comma-separated, e.g. "19_20-1-1-java,asym-5-java"

--skip_preprocessing  : flag, skip Step 1 and reuse the existing datastore
--skip_grading        : flag, skip Step 3 and reuse the saved responses
--skip_processing     : flag, skip Steps 4 and 5 (processing and metrics)
--skip_graphs         : flag, skip Step 6 graph generation


# Running the Full Pipeline

Run everything end to end with one cloud model:

python3 main.py --nim_models openai/gpt-oss-120b

Run everything with one local Ollama model:

python3 main.py --ollama_models qwen3:14b

Run with several models at once (local and cloud together):

python3 main.py --ollama_models qwen3:14b devstral-small-2 --nim_models openai/gpt-oss-120b

Run with a generic OpenAI-compatible provider (Gemini, Claude, Groq):

python3 main.py --other_models gemini-2.0-flash \
    --base_url https://generativelanguage.googleapis.com/v1beta/openai/ \
    --api_key_env GEMINI_API_KEY


# Running a Subset

Grade only the two bucket-classification approaches:

python3 main.py --nim_models openai/gpt-oss-120b --approaches approach_3 approach_4

Grade a single question only:

python3 main.py --nim_models openai/gpt-oss-120b --question_id 21_22-3-1-java

Grade several specific questions (comma-separated, no spaces):

python3 main.py --nim_models openai/gpt-oss-120b \
    --question_id "21_22-3-1-java,asym-5-java"

Use 5 runs per submission instead of the default 3:

python3 main.py --nim_models openai/gpt-oss-120b --runs 5



# Resuming 
Reuse the existing datastore, skip preprocessing:

python3 main.py --nim_models openai/gpt-oss-120b --skip_preprocessing

Recompute results and graphs from responses already on disk (no LLM calls):

python3 main.py --skip_preprocessing --skip_grading

Regenerate only the graphs:

python3 main.py --skip_preprocessing --skip_grading --skip_processing

Grade only, and stop before processing and graphs:

python3 main.py --nim_models openai/gpt-oss-120b \
    --skip_preprocessing --skip_processing --skip_graphs


# Example of Grading a Separate Assignment

`--assignment` redirects every store to a named subfolder, so a new dataset can be
graded. It expects the cleaned data to already exist at `datastore/<name>/`:

python3 main.py --assignment assignment1 --nim_models openai/gpt-oss-120b --skip_preprocessing

This reads `datastore/assignment1/` and writes to `response_store/assignment1/`,
`result_store/assignment1/`, and `graph_store/assignment1/`.


# Running Individual Stages

# Grading

python3 src/grade.py --datastore_dir datastore --response_store_dir response_store \
    --approach approach_4 --model openai/gpt-oss-120b --backend nim --api_key $NIM_API_KEY

--datastore_dir       : cleaned dataset folder                       (required)
--response_store_dir  : where responses are written                  (required)
--approach            : approach_1, approach_2, approach_3, approach_4   (required)
--model               : model name to grade with                     (required)
--backend             : ollama, nim, other                           (default: ollama)
--api_key             : API key, for the nim and other backends
--base_url            : endpoint URL, for the other backend
--question_id         : restrict to one or more question_ids (comma-separated)
--runs                : runs per submission                          (default: 3)

Local Ollama example:

python3 src/grade.py --datastore_dir datastore --response_store_dir response_store \
    --approach approach_1 --model qwen3:14b --backend ollama --question_id 21_22-3-1-java

# Processing

python3 src/process.py --response_store_dir response_store \
    --result_store_dir result_store --datastore_dir datastore

--response_store_dir  : folder of saved LLM responses                (required)
--result_store_dir    : where result.csv is written                  (required)
--datastore_dir       : needed to load rubrics for mark lookup       (required)
--approach            : only reprocess one approach                  (optional)
--model               : only reprocess one model                     (optional)
--question_id         : only reprocess one or more questions         (optional)

# Graphs

python3 src/generate_graph.py --result-store result_store --datastore datastore \
    --output-dir graph_store --ground-truth datastore/ground_truth.csv

--result-store  : folder containing result.csv                       (required)
--datastore     : cleaned dataset folder                             (required)
--output-dir    : where the PNGs are saved                           (default: graph_store)
--ground-truth  : human grades CSV to plot against                   (optional)

# Real-data preprocessing

python3 src/preprocessing_realData.py --raw_data_dir raw_data/AD2022dataset \
    --datastore_dir datastore --out_dir datastore/realdata --per_question 3

--raw_data_dir  : folder of raw cohort CSVs
--datastore_dir : source datastore, read only (rubrics and prompts are copied from it)
--out_dir       : where the real-data dataset is written    (default: datastore/realdata)
--per_question  : how many submissions to sample per question           (default: 3)
--full_qids     : question IDs to keep ALL submissions for, instead of --per_question



# Human Review Tool
streamlit run src/explorer/overview.py


# To Generate Graphs

python3 src/generate_graph.py --result-store result_store --datastore datastore \
    --output-dir graph_store --ground-truth datastore/ground_truth.csv
