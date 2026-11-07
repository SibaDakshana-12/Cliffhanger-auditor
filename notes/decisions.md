# Design decisions

Each entry: what was decided, why, and the trade-off. Newest at the bottom.

## D1. Parser is regex, not an LLM (Step 1)
- **Why:** line IDs and timestamps are the evidence for every score. They must be deterministic and traceable to a real line in the script, not produced by a model that can invent them.
- **Trade-off:** it only understands this one screenplay format. Anything else is rejected with an error.

## D2. One block = one line, ID `E001-L042` (Step 1)
- Each `**TAG:**` + `Start/End` + text block becomes one line. The ID is the episode number (from the `EPISODE NUMBER:` header) plus the block's position in the file.
- The timestamp must be on the line right after the tag. That rule is what keeps each timestamp attached to its own line.
- If the file name looks like `episode-NNN-...`, its number must match the header. Otherwise parsing stops with an error.

## D3. Strict errors, and the whole folder stops (Step 1)
- A missing or badly formed timestamp, an end time before its start time, missing script markers, a block with no text, or any unrecognised line raises an error naming the file and line number.
- Duplicate episode numbers or gaps in the numbering also stop the run. Each ending is paired with episode N+1, so a gap would pair it with the wrong opening.
- Every bad file in the folder is reported at once, and nothing is scored. No episode is ever silently skipped. A broken file would also corrupt the previous episode's opening window, and stopping before any API call costs nothing.

## D4. Timing oddities are warnings, not errors (Step 1)
- Real pack: 8 blocks (episodes 4, 12, 20, 21, 32, 46) start slightly earlier than the block before them, and the latest End time is not always on the last block (episode 4: last block ends 02:29.00, latest end is 02:31.40).
- A "duplicate timestamp" warning fires only when two blocks of the same kind share the exact start and end times. CAMERA and ACTION blocks often share times on purpose. The real pack has none.

## D5. Windows are chosen by time, then kept in screenplay order (Step 2)
- Episode length = the latest End timestamp. This is **script time**, not measured video length. The final cut may differ, and we don't assume timestamp gaps equal real seconds of video.
- Ending window = every line that overlaps the last 25s (its end is after duration − 25). Opening window = every line of episode N+1 that starts before 10s. The last episode in a folder has no opening window.
- Lines stay in file order, which is the writer's order, so overlapping blocks don't break selection.
- Fallback: if an episode is shorter than the window, use the last (or first) 12 lines and log a warning. The real pack never triggers it: the shortest episode is 1:10. Missing timestamps can't reach this stage because the parser rejects them.
- All three numbers live in `config.yaml`.
- **Trade-off:** a fixed time window gives each episode a different number of lines (6 to 23 in the real pack). Episode 18's window has only 6 lines because its blocks are long.

## D6. CAMERA, ACTION and SOUND FX lines are kept in the windows (Step 2)
- Lines like "cut to black" or "close-up on her terrified face" carry real information about the ending. Each line is labelled with its kind, so the scorer knows it is a stage direction and not dialogue.

## D7. Writer labels will be hidden from the model (decided now, built in Step 5)
- 14 of the 50 endings literally say "cliffhanger" in their closing direction, and 7 say "resolving". The next episode's CONTINUITY NOTES often say "picks up from Episode N's cliffhanger".
- Plan: only window lines go to the model (no LOGLINE or CONTINUITY NOTES), and words like "cliffhanger" or "resolving" are masked in the model's input only. Parser output and anything shown to the editor stay verbatim.
- **Why:** we want the scene scored, not the label. New scripts may not carry labels at all.

## D8. Gemini free tier, ending/opening windows only (Step 5)
- Gemini's free-tier terms (checked by the user on 2026-11-08) say Google may use submitted content to improve its products, human reviewers may read it, and "Do not submit sensitive, confidential, or personal information to the Unpaid Services."
- Kuku's brief calls the pack confidential, but also says "You're welcome to use it with AI tools for your work."
- **Decision (user's choice, option A):** use the free tier, but send only the ending window (~25s) and the next episode's opening (~10s): roughly 15-20% of each script. LOGLINE and CONTINUITY NOTES are never sent.
- The solution doc says production would use a paid or no-training tier.
- Alternatives considered: a local model (nothing leaves the laptop, but weaker and costs setup time) and the paid tier (costs money).

## D9. Model input format and masking (Step 5)
- Each line goes to the model as `ID | start time | KIND SPEAKER (emotion): text`. The model sees times to judge pacing, but its output schema has no timestamp field: every time shown to the editor comes from the parser.
- Writer labels ("cliffhanger", "resolving", "resolution") are replaced with "[cue]", only in CAMERA, ACTION and SOUND FX lines (that's where the writer cues are) and only in the model input. Dialogue is never altered.
- Suggestions are cut points only: an earlier line in the ending window where the episode could end instead, or "no_valid_alternative". Reordering lines isn't supported (simpler to validate and explain).
- An extra output field `none_kind` (deliberate or flat) makes the rubric's none-versus-flat rule checkable by code, instead of hiding it in free text.

## D10. Main model switched to gemini-3.5-flash (Step 10)
- gemini-2.5-flash's free tier allows 20 requests per day, which is fewer than one full run. gemini-3.5-flash answered when 2.5-flash was exhausted (separate quota). gemini-2.5-flash-lite returned 404 ("no longer available to new users").
- Changing the model was one line in config.yaml: no code change.
- gemini-2.5-flash becomes the model-swap comparison, run on the 10 manually scored episodes (fits in its 20/day).

## D11. Second free key and gemini-3.8-flash as the main model (Step 10)
- Both free-tier models on the first key ran out of daily quota (about 20 requests/day each). The user chose to continue on a free API key from a second Google account, aware that Google's terms discourage working around usage limits. Recorded here so the write-up matches the raw outputs.
- The user chose gemini-3.8-flash as the main model. Episodes 1-11 were already scored with gemini-3.5-flash (run 20261108-023202). They are rescored with 3.8 for a consistent main run, and the two runs on the same 11 episodes serve as the model-swap test.
- Scoring order: the user's 10 manually scored episodes first, so the evaluation doesn't depend on how much quota is left.

## D12. Main model is gemini-3.5-flash-lite (Step 10)
- The second key hit the same exhausted quotas, with the same reset time as the first key. Free quotas are counted per Google Cloud project, so it was not a fresh quota. gemini-3.8-flash didn't answer a one-word test prompt within ~5 minutes.
- gemini-3.5-flash-lite still had free quota, so it is the main model for the full run, starting with the 10 manually scored episodes.
- Model-swap test: gemini-3.5-flash-lite vs gemini-3.5-flash on episodes 1-11 (already scored with 3.5-flash in run 20261108-023202), plus agreement with the manual scores where they overlap.
- Trade-off: "lite" is the smaller, cheaper model, so scores may be worse. The manual comparison measures that instead of assuming it.
