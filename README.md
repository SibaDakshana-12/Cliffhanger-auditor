# Cliffhanger Auditor

Reads microdrama screenplays and checks how each episode **ends** and how the
**next one opens**. For every episode it gives an ending type, five 1-5 scores,
a model-reported (uncalibrated) confidence, a one-line reason, evidence line IDs
with timestamps, and a suggested earlier cut point using existing lines (or
`no_valid_alternative`). Weak endings are flagged, and an editor accepts or
rejects each one.

It only reads scripts. It cannot judge animation, audio, acting or story originality.

## Install
Python 3.11+.
```
python -m venv .venv
.venv\Scripts\activate            # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
```
Create `.env` in this folder with a Gemini API key (free at aistudio.google.com):
```
GEMINI_API_KEY=your_key_here
```

## Run
```
python run.py --input demo_data/episodes            # 3 synthetic demo episodes
python run.py --input data/episodes --episodes 1-40 # a subset
python run.py --input demo_data/episodes --no-llm   # rule-based baseline only, no key needed
streamlit run app.py                                # review screen: ranked list, detail, Accept/Reject
python evaluation/compare.py                        # manual scores vs LLM vs baseline
python -m pytest                                    # tests
```
Output goes to `outputs/raw/<run_id>/`:
- `results.json` and `results.csv`: one record per episode
- `run_meta.json`: model, failures, retries, flagged episodes, cost estimate from real token counts

Editor decisions go to `outputs/decisions.csv`.

## Run on a new screenplay folder
```
python run.py --input path/to/new_folder
```
The folder must hold `.txt` files in the same format as the input pack:
- an `EPISODE NUMBER: Episode N` header
- `--- SCRIPT START ---` / `--- SCRIPT END ---` markers
- `SCENE NN` sections
- blocks of `**TAG:**`, then `Start: (MM:SS.cc) | End: (MM:SS.cc)`, then one text line

Episode numbers must be unique and gap-free. Anything else stops the run with an error naming the file and line, before any API call. Nothing is guessed and no episode is silently skipped.

To preview what the model will see: `python -m src.windows path/to/new_folder --show 3`.

## Swap the model
Edit `llm:` in `config.yaml`, or pass `--model <name>` for a single run. All provider code is in `src/llm.py`. Gemini is the only provider implemented; another provider means adding one function there.

## Settings (`config.yaml`)
- **Window sizes:** ending 25s, opening 10s.
- **Masked writer labels:** words like "cliffhanger" in stage directions are hidden from the model.
- **Scoring:** score weights, flag thresholds, retry limit, paid-tier prices for the cost estimate.
- **`save_text`:** with `false` (the default), outputs keep only line IDs, timestamps and scores, and leave out the model's reasons.

## Confidentiality
`data/`, `outputs/`, `research/` and `.env` are gitignored. The Kuku screenplays and any output derived from them never go in this repo. The hosted demo uses only `demo_data/` (synthetic) or uploaded files.

## Layout
```
src/        parser, windows, llm wrapper, scorer, validators, aggregate, baseline, schemas
prompts/    rubric.md, scorer_prompt.md   (every LLM prompt lives here; see PROMPTS.md)
evaluation/ manual_scores.csv, compare.py
notes/      decisions.md, ai_mistakes.md
demo_data/  synthetic episodes (invented, labelled SYNTHETIC)
```
