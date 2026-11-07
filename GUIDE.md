# GUIDE: how the Cliffhanger Auditor works and why

## The pipeline (one line per step)
1. **Parse** (`src/parser.py`, regex): each script block becomes a line with an ID (`E005-L062`) and its own timestamp. A bad format stops the run with the file name and line number.
2. **Windows** (`src/windows.py`): the ending window is every line overlapping the last 25s; the opening window is every line starting in the next episode's first 10s. Times are script time, not measured video length.
3. **Manual scores** (`evaluation/manual_scores.csv`): I scored 10 episodes (from 1-40) myself before seeing any AI output.
4. **Rubric** (`prompts/rubric.md`): five 1-5 scores with anchors, six ending types, and the rule that tells a deliberate "none" from a flat ending.
5. **Scorer** (`src/scorer.py` + `prompts/scorer_prompt.md`): one LLM call per episode with only the numbered window lines. Writer labels like "cliffhanger" are masked. Output is JSON.
6. **Validators** (`src/validators.py`, plain Python): reject invented line IDs, cut points outside the episode's ending, flat endings with pull above 2, and a wrong weakest dimension. A rejected answer gets one retry with the problems listed.
7. **Aggregate** (`src/aggregate.py`): weighted final score. Flag if the final score is 3.0 or below, or pull_to_next is 2 or below. Timestamps are looked up from the parser.
8. **Baseline** (`src/baseline.py`): keyword and punctuation rules, to check the LLM earns its cost.
9. **App** (`app.py`): ranked list, detail view, Accept / Reject / Needs review saved to `outputs/decisions.csv`, live acceptance rate.
10. **CLI** (`run.py`): `python run.py --input <folder>`.
11. **Reliability and cost**: retries only on temporary errors, a clean stop on daily quota, real token counts, and a cost estimate in `run_meta.json`.

## What is AI and what is code
| Code (deterministic) | AI (judgment) |
|---|---|
| parsing, line IDs, timestamps, windows | ending type, the five scores |
| validation of every ID the model cites | the one-line reason |
| weighted score and flag rule | the suggested cut point (an existing line only) |
| baseline | |

**Human in the loop:** the editor accepts or rejects every flag and suggestion. The tool never edits anything.

## Key design choices (details in notes/decisions.md)
- **Regex parser, strict errors:** evidence must trace back to a real line, so a wrong format fails loudly instead of being guessed at.
- **Fixed time windows:** simple and explainable. The trade-off is that windows vary from 6 to 23 lines.
- **Writer labels masked:** 14 of the 50 endings literally say "cliffhanger" in a stage direction. The model should judge the scene, not the label.
- **The model outputs no timestamps:** every time the editor sees comes from the parser.
- **Cut points only, no rewrites:** every suggestion can be checked against the real script.
- **Confidence is shown as "model-reported, uncalibrated":** in testing it was 0.90-1.00 even on wrong answers.
- **Free tier, windows only:** the free-tier terms allow Google to use the inputs, so only about 15-20% of each script is sent. Production would use a paid or no-training tier.

## Interview Q&A
**Why this problem?** _(your words: your research findings, plus the overlap with Problem 1, since promos also need cliffhangers)_

**How do you know it's any good?** "I scored 10 episodes myself before seeing any AI output. The LLM agreed with my weak/strong flag on 8 of 10, against 6 of 10 for a keyword baseline, and its overall score was within 1 point of mine on all 10. But n=10 is tiny, and I chose the flag threshold after seeing my own scores. Episodes 41-50 were held out and run once: all 10 gave valid output, but I have no manual scores for them, so accuracy there isn't measured."

**Where does it fail?**
- It missed the flat ending I care most about (episode 20, which it called a "threat").
- It gave pull 5 to an ending I scored 2 (episode 24).
- It never scores pull below 3 and calls too many endings "threat".
- Its confidence is always 0.90 or higher.
- It can't judge animation, audio, acting or originality: it only reads scripts.

**How do you stop it inventing things?**
- It sees only numbered lines.
- It can't output timestamps.
- Code rejects any line ID it wasn't shown and any cut outside the episode.
- The limit: code checks that cited lines exist, not that they support the reason. That's the editor's job.

**How do you swap the model?** "One line in config.yaml, or `--model`. I actually ran three Gemini models: 2.5-flash, 3.5-flash and 3.5-flash-lite. Model swap results are in the solution doc." _(Only Gemini is implemented; another provider means adding one function in src/llm.py.)_

**What does it cost at scale?** The real token counts are in `run_meta.json`; see the solution doc for the numbers. The free tier allows about 20 calls per day per model, which ran out during this project. Production needs the paid tier.

**What happens on a new folder in a different format?** "It stops before any API call, with the file name, line number and what was expected. It never guesses and never skips an episode silently."

**How would you know it worked for a real team?** Editor acceptance rate in the app, and the share of flagged episodes the editor agrees with. Only audience data (completion and next-episode rates before and after a re-cut) could show it improves retention. I don't claim that.
