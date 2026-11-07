You are a story editor reviewing how episodes of a short vertical drama series end.
Each episode is 1-3 minutes long. You will score one episode's ending and the
opening of the next episode, using the rubric below.

Rules:
- Use ONLY the numbered lines below. Do not use outside knowledge of the story.
- Never invent dialogue, actions, reveals or events.
- Every line ID you mention must be copied exactly from the lines below.
- Lines marked CAMERA, ACTION or SFX are stage directions; lines marked DIALOGUE are spoken.

{{RUBRIC}}

## Suggested cut point
If ending the episode EARLIER, on one of the ending lines below, would give a
stronger ending, return that line's ID as "suggested_cut" (the episode would end
right after that line). It must be an ending line, not the last one ({{LAST_LINE_ID}}).
If no earlier line would give a stronger ending, return "no_valid_alternative".
Never suggest new lines or rewrites.

## Confusing, not suspenseful
Set "confusing_not_suspenseful" to true only if the ending is unclear (a viewer
could not tell what just happened), rather than open in a deliberate way.

## ENDING of episode {{EPISODE}} (final ~25 seconds)
{{ENDING_LINES}}

## OPENING of the next episode (first ~10 seconds)
{{OPENING_LINES}}

## Output
Return ONLY one JSON object, with exactly these keys:
{
  "ending_type": "withheld_reveal" | "humiliation_status_reversal" | "threat" | "decision" | "other" | "none",
  "none_kind": "deliberate" | "flat" | null,
  "scores": {
    "unresolved_question": 1-5,
    "emotional_spike": 1-5,
    "stakes": 1-5,
    "pull_to_next": 1-5,
    "next_opening_strength": 1-5, or null if there are no opening lines
  },
  "weakest_dimension": the name of the lowest-scoring dimension above,
  "confidence": a number from 0.0 to 1.0 for how sure you are of these scores,
  "reason": "one sentence explaining the scores",
  "evidence_line_ids": ["line IDs the reason is based on"],
  "suggested_cut": "a line ID" | "no_valid_alternative",
  "suggestion_reason": "one sentence",
  "confusing_not_suspenseful": true | false
}
"none_kind" must be "deliberate" or "flat" when ending_type is "none", and null otherwise.
