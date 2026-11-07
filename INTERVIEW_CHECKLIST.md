# Interview checklist: running on an unseen screenplay folder

## Before the interview
- [ ] `git pull`; `.venv` works; `python -m pytest` passes.
- [ ] `.env` has a working key. Check quota at https://ai.dev/rate-limit. The free tier allows about 20 calls/day per model, so **don't use up the quota the morning of the interview**.
- [ ] Note which model has quota left. Switch with `--model gemini-3.5-flash-lite` (or another) if needed.
- [ ] Fallback if the API is down: `python run.py --input <folder> --no-llm` (baseline only), and show a saved run in the app.

## In the interview
1. **Look at the folder first:** `.txt` files, an `EPISODE NUMBER:` header, `**TAG:**` + `Start: (MM:SS.cc) | End: (MM:SS.cc)` blocks.
2. **Dry parse (no API):** `python -m src.windows <folder>`
   - "INPUT ERROR" means: read the message aloud. It names the file, the line and what was expected. Explain that this is deliberate: it never guesses.
   - Show one window: `python -m src.windows <folder> --show <N>`.
3. **Score:** `python run.py --input <folder>` (add `--episodes 1-5` if time or quota is short).
4. **Review:** `streamlit run app.py`, then load the run:
   - weakest first
   - open a flagged episode
   - point at the evidence lines and timestamps (from the parser)
   - point at the confidence label (uncalibrated)
   - press Accept or Reject and show the acceptance rate update
5. **Swap model live:** `python run.py --input <folder> --episodes 1-3 --model <other-model>`.
6. **Say the limits:** n=10 evaluation; misses flat endings; scores bunch at the top; flash-lite never suggests cuts; script only.

## If something breaks
| Symptom | Meaning | Do |
|---|---|---|
| `429 ... per day` / status `not_run_quota` | daily free quota used | switch `--model`, or show the baseline plus a saved run |
| `429` then success | per-minute limit, retried | nothing |
| `invalid_output` | the model broke the schema or cited a fake ID twice | show the `errors` field: the validators worked |
| `INPUT ERROR ... gaps` | episode numbers missing | run on a gap-free subset |

# 3-minute video plan
| Time | Show | Say |
|---|---|---|
| 0:00-0:25 | problem_proof table | The problem: weak endings lose the viewer; what I watched and heard (small sample). One user: an editor reviewing endings. |
| 0:25-0:55 | `python run.py --input data/episodes --episodes 5-8` | Code parses lines and timestamps; the LLM only judges the numbered lines; validators reject invented IDs. |
| 0:55-1:50 | Streamlit app | Weakest first, a flagged episode, evidence lines with parser timestamps, uncalibrated confidence, Accept/Reject, acceptance rate. |
| 1:50-2:30 | `evaluation/compare.py` output | 8/10 flag agreement vs 6/10 for the baseline; n=10; the misses (episodes 20, 24); confidence always 0.9+. |
| 2:30-3:00 | config.yaml model line | One-line model swap (3 Gemini models tried), cost per episode from real tokens, free-tier quota limits, what's next. |

Record the real Kuku run locally. Never host it. The hosted app uses demo_data only.
