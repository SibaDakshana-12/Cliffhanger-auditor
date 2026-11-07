# Cliffhanger rubric (v1)

You judge two things from a screenplay: how strongly an episode ENDS, and how
strongly the NEXT episode OPENS. Judge only the numbered lines you are given.
Do not use knowledge of other episodes, and do not imagine events that are not
in the lines.

## Scores (whole numbers 1-5)

**unresolved_question**: Does the ending leave a specific question open at the cut?
- 1: Nothing is left open. The scene resolves or simply stops.
- 3: Something is vaguely open, but it is not urgent or not specific.
- 5: A specific, urgent question hangs at the final line (who is it? will she survive? what is the secret?).

**emotional_spike**: How strong is the emotion in the final seconds, compared with the rest of the window?
- 1: The final beat is calm or flat.
- 3: The emotion is clear but steady, with no peak at the end.
- 5: The strongest emotional moment lands in the last seconds (shock, humiliation, terror, rage).

**stakes**: What can a character lose, as shown in these lines?
- 1: Nothing is at risk.
- 3: Something matters, but the loss would be small or far off.
- 5: Life, love, identity, freedom or status is clearly and immediately at risk.

**pull_to_next**: Would a viewer tap Next right now?
- 1: They could happily stop here.
- 3: Mild curiosity.
- 5: They must see what happens next.

**next_opening_strength**: Do the first ~10 seconds of the next episode grab the viewer?
- 1: A slow start: re-explains, opens on something unrelated, or has no hook.
- 3: Picks up the story, but slowly.
- 5: Pays off or escalates the previous ending at once, or opens on a new shock.
- If no next-episode lines are given, return null.

A score of 2 or below is **weak**.

## ending_type (pick one)
- **withheld_reveal**: the episode cuts just before a secret, identity, power or answer is revealed.
- **humiliation_status_reversal**: a character is humiliated, or the balance of power suddenly flips.
- **threat**: danger, a demand or an ultimatum hangs over a character.
- **decision**: a character must choose, or has just made a choice whose result is unknown.
- **other**: a hook that fits none of the above.
- **none**: no cliffhanger. This is a valid answer, not an error.

## none: deliberate or flat?
An ending can have no cliffhanger and still be fine, or it can just be flat.
- **Deliberate none**: the scene closes on purpose with a clear emotional beat, such as a romantic moment, a quiet resolution or a character's resolve. Score it honestly; pull_to_next may still be 3 or higher.
- **Flat continuation**: the story just keeps going and stops, with no new information, no change and no hook. pull_to_next MUST be 2 or lower.
When ending_type is none, the reason must say which of the two it is.

## Labels written into the script
Some scripts contain stage directions that name the ending (for example a music
cue marked as a cliffhanger). These have been replaced with "[cue]". Judge what
happens in the lines, not how the writer labelled it.

## Evidence
Every judgment must cite the line IDs it is based on. Quote nothing that is not in the lines.
