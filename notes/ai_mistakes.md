# Real AI mistakes

Only real, observed mistakes, with how they were caught. Never invented examples.
"Build AI" = Claude Code helping write the tool. "Scorer AI" = the LLM inside the tool.

## M1. Build AI miscounted scenes during inspection (Step 1)
- **What happened:** to count scenes per episode, the build AI used a quick text search for lines starting with `SCENE `. In episode 6 that also matched the upper-case `SCENE HEADING:`, `SCENE START:` and `SCENE END:` field lines, so it reported 8 scenes. The parser shows episode 6 has 2.
- **Caught by:** comparing against the parser's real scene count.
- **Lesson:** quick text searches over a format with case variations mislead. Trust the tested parser.

## M2. Build AI wrote a wrong expected value in a test (Step 1)
- **What happened:** a test expected the "missing timestamp" error on line 14 of a small test file. The parser said line 19, which is the correct line: the row where the timestamp should have been.
- **Caught by:** running the tests. The code was right and the test was wrong, so the test was fixed.
- **Lesson:** tests check the AI's code, but tests written by AI need checking too.

## M3. A separate AI assistant claimed the scripts have no line IDs (Step 3)
- **What happened:** the user scored the 10 episodes themselves, then asked a separate AI assistant to write notes for each row. Its notes said "numbered line IDs were not included in the screenplay text files" and "the source file and numbered line IDs are not present in the current working files". That's false: our parser gives every block an ID (e.g. `E005-L062`). The assistant had never seen the parser and stated it anyway.
- **Caught by:** the build AI noticed the notes didn't read like human notes and contradicted the parser's output. The user confirmed the scores were their own and only the notes were AI-written.
- **Fix:** the `notes` and `evidence_basis` columns were deleted from `evaluation/manual_scores.csv`. The user's scores were kept unchanged.
- **Lesson:** AI tools confidently state facts about files they haven't seen. Ground truth for evaluation must be human-made, and anything an AI adds to it must be checked or removed.

## M4. Build AI wired up the Gemini API wrongly and retried errors that can't succeed (Step 5)
- **What happened:** the first real scorer run failed for every attempt with `400 INVALID_ARGUMENT: JSON mode is not enabled for api version v1`. The build AI had used the SDK's default API version. Worse, its retry loop retried this permanent error 3 more times per episode (about 30s wasted each).
- **Caught by:** the retry/error counters in the output record. All 8 attempts were logged as API failures; none was hidden.
- **Fix:** request the `v1beta` API in `src/llm.py`, and retry only temporary errors (429 rate limit, 5xx, network) via `is_retryable()`.

## M5. Scorer AI: "perfect ending, but cut earlier" (Step 5, episode 3)
- **What happened:** for episode 3, gemini-2.5-flash gave all five scores 5 with confidence 1.0, yet still suggested an earlier cut (E003-L116), saying it would create "a stronger, more immediate unresolved question". If the current ending already scores 5 on everything, "stronger" contradicts its own scores. It returned identical output on a second run, so this is a consistent behaviour, not noise.
- **Also seen:** confidence 1.0 on a subjective judgment, which shows why confidence is labelled uncalibrated.
- **Status:** not fixed. The output passes validation (the cut is a real earlier ending line). The editor sees both scores and the suggestion and decides. To revisit after the full run, if it happens often.

## M6. Build AI launched the full run without checking free-tier quotas (Step 10)
- **What happened:** the first 1-40 run with gemini-2.5-flash scored episodes 1-3, then hit the free tier's **20 requests per day** limit (`429 RESOURCE_EXHAUSTED ... Generate content requests per day limit exceeded on Free Tier`). The build AI's retry logic treated every 429 as temporary, so it retried a daily limit 3 more times per episode: 29 episodes failed, with 117 failed API calls in total.
- A second build-AI slip in the same run: the background command piped output through `grep`, which held back the progress log, so the failure wasn't visible until the results file was checked.
- **Caught by:** the per-episode `status` and `api_failures` counts in `results.json` (kept as evidence in `outputs/raw/20261108-021304/`).
- **Fix:** `is_daily_quota()` in `src/llm.py`. A per-day 429 is no longer retried, and `run.py` stops calling the LLM; remaining episodes get baseline scores and status `not_run_quota`, listed explicitly. Main model switched to gemini-3.5-flash (separate quota); gemini-2.5-flash is kept for the model-swap test.
- **Lesson:** check the provider's rate limits before a batch run, and treat "per minute" and "per day" limits differently.

## M7. Scorer AI (gemini-3.5-flash-lite): the scores barely vary, and two features go unused (full run, episodes 1-40)
Real numbers from runs 20261108-024935 and 20261108-025008:
- **Missed the flat ending:** for episode 20, which the user scored as a flat continuation (pull 2), the model said "threat" with pull 3. Across all 40 episodes it never used `none_kind: "flat"` (11 "none" endings, all "deliberate").
- **Over-scored a weak ending:** episode 24, user pull 2, model pull 5 (final 4.25, not flagged).
- **Squeezed toward the top:** pull_to_next was 5 for 23 of 40 episodes. Every hook type averages a final of about 4.4-4.6 and "none" averages 2.4, so it acts more like a "hook / no hook" switch than a 1-5 scale.
- **Never suggested a cut:** "no_valid_alternative" on all 40 episodes. gemini-3.5-flash did suggest cuts (e.g. E005-L058), so the suggestion feature depends on the model.
- **Confidence was always 0.90-1.00,** including on episodes 20 and 24 where it disagreed most with the user.
- **3 invalid outputs** (episodes 12, 23, 28): `weakest_dimension` was null or not an allowed value. Pydantic caught all 3 and the corrective retry fixed them.
- **Trope check:** "humiliation" and "withheld_reveal" endings (episodes 1, 26, 27, 34) all got pull 5, but threat and decision endings score just as high. The over-scoring isn't specific to the "insulted hero, reveal withheld" trope, and with only one manual example of that trope (episode 28: user 5, model 5) it can't be confirmed or ruled out.
