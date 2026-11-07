"""A simple rule-based scorer to compare the LLM against. No AI.

It looks only at surface signals in the ending window: does the last spoken line
end in a question or an exclamation, is it very short, and do the last lines
contain reveal / threat / humiliation / decision words. Every score starts at 2
and rules add points. If the LLM can't beat this, the LLM isn't worth its cost.

The word lists are generic English (no story-specific names), so this baseline
only works on English scripts. Writer labels are masked first, as for the LLM.
"""
import re

from src.schemas import EpisodeWindows, Line, Scores
from src.scorer import mask

REVEAL = ["truth", "secret", "who are you", "identity", "really", "revealed", "recogni", "discover",
          "the real", "hidden", "lied", "know who"]
THREAT = ["kill", "die", "death", "dead", "gallows", "execut", "blood", "knife", "blade", "gun", "poison",
          "hang", "burn", "or else", "pay", "ransom", "weapon", "branding"]
HUMILIATION = ["worthless", "pathetic", "beggar", "nothing", "shame", "kneel", "humiliat", "disgrace",
               "servant", "trash", "fool", "embarrass"]
DECISION = ["choose", "decide", "marry me", "will you", "promise", "swear", "vow", "agree", "deal"]
SHOCK = ["shock", "terror", "terrified", "gasp", "scream", "horrif", "tears", "slap", "collapse", "freez",
         "stunned", "cut to black"]


def has_any(text: str, words: list[str]) -> bool:
    return any(w in text for w in words)


def clamp(x: int) -> int:
    return max(1, min(5, x))


def baseline_score(win: EpisodeWindows, cfg: dict) -> dict:
    """Return {'ending_type', 'scores', 'rules'}; 'rules' lists which rules fired, for explainability."""
    text = lambda lines: " ".join(mask(l.text, cfg).lower() for l in lines)
    tail = text(win.ending[-3:])                       # last three lines of the ending
    spoken = [l for l in win.ending if l.kind == "dialogue"]
    last_said = re.sub(r'[\s"”’\']+$', "", spoken[-1].text) if spoken else ""
    rules = []

    unresolved = emotional = stakes = 2
    if last_said.endswith("?"):
        unresolved += 2; rules.append("last spoken line is a question")
    if last_said.endswith("...") or last_said.endswith("…"):
        unresolved += 1; rules.append("last spoken line trails off")
    if has_any(tail, REVEAL):
        unresolved += 1; rules.append("reveal word in last lines")
    if last_said.endswith("!"):
        emotional += 1; rules.append("last spoken line is an exclamation")
    if has_any(tail, SHOCK):
        emotional += 2; rules.append("shock word in last lines")
    if has_any(tail, THREAT):
        stakes += 2; rules.append("threat word in last lines")
    if has_any(tail, HUMILIATION):
        stakes += 1; rules.append("humiliation word in last lines")

    pull = round((unresolved + emotional + stakes) / 3)
    if spoken and len(last_said.split()) <= 4:
        pull += 1; rules.append("last spoken line is very short (<= 4 words)")

    opening = None
    if win.opening:
        opening = 2
        open_spoken = [l for l in win.opening if l.kind == "dialogue"]
        if open_spoken:
            opening += 1; rules.append("next episode has dialogue in the first 10s")
        if any(re.search(r"[!?]", l.text) for l in open_spoken) or has_any(text(win.opening), SHOCK):
            opening += 1; rules.append("next opening has a question, exclamation or shock word")

    # First matching type wins; no rule fired at all means "none".
    if has_any(tail, THREAT):
        ending_type = "threat"
    elif has_any(tail, REVEAL):
        ending_type = "withheld_reveal"
    elif has_any(tail, HUMILIATION):
        ending_type = "humiliation_status_reversal"
    elif has_any(tail, DECISION):
        ending_type = "decision"
    elif rules:
        ending_type = "other"
    else:
        ending_type = "none"

    scores = Scores(unresolved_question=clamp(unresolved), emotional_spike=clamp(emotional),
                    stakes=clamp(stakes), pull_to_next=clamp(pull),
                    next_opening_strength=clamp(opening) if opening is not None else None)
    return {"ending_type": ending_type, "scores": scores, "rules": rules}
