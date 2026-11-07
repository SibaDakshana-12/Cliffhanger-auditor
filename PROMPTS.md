# PROMPTS.md

# Part A: prompts used inside the tool

## 1. Rubric
- **Path:** `prompts/rubric.md`
- **Pipeline step:** inserted into the scorer prompt (Step 5) where `{{RUBRIC}}` appears.
- **Purpose:** defines the five 1-5 scores, the six ending types, and how to tell a deliberate "none" from a flat ending. It's the shared standard the user's manual scores and the LLM are both judged by.
- **Exact text:** see the file (it is inserted verbatim).
- **Input / output:** no input of its own; it's part of the scorer prompt.
- **Why worded this way:**
  - Anchors at 1, 3 and 5 so scores aren't vague.
  - "none" is explicitly valid, but "flat" must have pull_to_next <= 2: the user's research found a no-cliffhanger reel that was fine and one that was boring.
  - It tells the model that writer labels were replaced with "[cue]", so it judges the scene rather than the label.
- **Known real failure:** none observed yet.
- **Version history:**
  - v1 (2026-11-08): written with the user; approved ("ok").

## 2. Scorer prompt
- **Path:** `prompts/scorer_prompt.md`
- **Pipeline step:** Step 5 (`src/scorer.py`). One call per episode.
- **Purpose:** scores one episode's ending and the next episode's opening, picks an ending type, cites evidence line IDs, and suggests an earlier cut point or "no_valid_alternative".
- **Exact text:** see the file. Placeholders: `{{RUBRIC}}`, `{{EPISODE}}`, `{{LAST_LINE_ID}}`, `{{ENDING_LINES}}`, `{{OPENING_LINES}}`.
- **Input:** numbered lines, one per row, as `E003-L116 | 02:12.40 | DIALOGUE NAME (emotion): text`, for the ending window (~25s) and the next opening (~10s). Writer labels are masked in stage directions.
- **Output schema:** `ScorerOutput` in `src/schemas.py`:
  - ending_type, none_kind
  - scores (5 dimensions, 1-5)
  - weakest_dimension
  - confidence (model-reported, uncalibrated)
  - reason, evidence_line_ids
  - suggested_cut, suggestion_reason
  - confusing_not_suspenseful
- **Checked by:** Pydantic (types, ranges, allowed values), then `src/validators.py` (IDs exist, cut is inside the ending, rubric rules). If rejected, the prompt is re-sent with the problems listed (`RETRY_NOTE` in `src/scorer.py`).
- **Why worded this way:**
  - "Use ONLY the numbered lines" and "copy IDs exactly" reduce invented evidence.
  - No timestamp field, so the model can't invent times.
  - Cut points only, so a suggestion can always be checked against the real script.
- **Known real failures:**
  - gemini-2.5-flash, episode 3: all scores 5, yet it suggested an earlier cut (M5).
  - gemini-3.5-flash-lite, full run: never used "flat", never suggested a cut, and gave pull 5 to an ending the user scored 2 (M7).
- **Version history:**
  - v1 (2026-11-08): first version, tested on episodes 2 and 3, then used unchanged for all runs (no tuning on episodes 41-50).

# Part B: prompts I used to build the tool (template, filled in by me)

| # | Date | Tool | What I asked (short) | What I kept / changed | Where it went wrong |
|---|------|------|----------------------|-----------------------|---------------------|
| 1 |      |      |                      |                       |                     |
