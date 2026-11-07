"""Check the LLM's output against the parsed screenplay. Plain Python, no AI.

Pydantic (schemas.ScorerOutput) already rejects scores outside 1-5, unknown
ending types and missing fields. This file checks what Pydantic can't: that
every cited line ID really exists in the lines the model was shown, that the
suggested cut is inside the episode's ending, and the rubric's own rules.

The model never outputs timestamps (the schema has no such field). Every time
shown to the editor is looked up from the parser by line ID.

Limit: we check that cited IDs EXIST, not that they actually support the reason.
"""
import re

from src.schemas import EpisodeWindows, ScorerOutput

LINE_ID_RE = re.compile(r"\bE\d{3,}-L\d{3,}\b")
NO_CUT = "no_valid_alternative"


def validate(out: ScorerOutput, win: EpisodeWindows) -> list[str]:
    """Return a list of problems (empty list = valid)."""
    problems = []
    shown = {l.id for l in win.ending + win.opening}
    ending_ids = [l.id for l in win.ending]

    # 1. Evidence must cite lines the model was actually shown.
    unknown = [i for i in out.evidence_line_ids if i not in shown]
    if unknown:
        problems.append(f"evidence_line_ids not in the lines provided: {unknown}")

    # 2. Line IDs mentioned inside the free-text reasons must exist too.
    mentioned = set(LINE_ID_RE.findall(out.reason + " " + out.suggestion_reason))
    if mentioned - shown:
        problems.append(f"reason text mentions line IDs not in the lines provided: {sorted(mentioned - shown)}")

    # 3. A suggested cut must be an earlier line of THIS episode's ending.
    if out.suggested_cut != NO_CUT:
        if out.suggested_cut not in ending_ids:
            problems.append(f"suggested_cut {out.suggested_cut!r} is not a line of episode {win.episode}'s ending "
                            f"(use a line ID from the ending or '{NO_CUT}')")
        elif out.suggested_cut == ending_ids[-1]:
            problems.append(f"suggested_cut {out.suggested_cut} is the current last line, so it is not a new cut")

    # 4. Rubric rules: none_kind only for "none"; a flat ending must have low pull.
    if out.ending_type == "none" and out.none_kind is None:
        problems.append("ending_type is 'none' but none_kind is missing (must be 'deliberate' or 'flat')")
    if out.ending_type != "none" and out.none_kind is not None:
        problems.append(f"none_kind must be null when ending_type is {out.ending_type!r}")
    if out.none_kind == "flat" and out.scores.pull_to_next > 2:
        problems.append(f"a flat ending must have pull_to_next <= 2, got {out.scores.pull_to_next}")

    # 5. Opening score only when there is a next episode.
    if win.opening and out.scores.next_opening_strength is None:
        problems.append("next_opening_strength is missing but opening lines were provided")
    if not win.opening and out.scores.next_opening_strength is not None:
        problems.append("next_opening_strength given but there is no next episode")

    # 6. weakest_dimension must really be (one of) the lowest scores.
    scores = {k: v for k, v in out.scores.model_dump().items() if v is not None}
    if out.weakest_dimension not in scores or scores[out.weakest_dimension] != min(scores.values()):
        problems.append(f"weakest_dimension {out.weakest_dimension!r} is not the lowest score {scores}")

    return problems
