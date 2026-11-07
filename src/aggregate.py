"""Turn the five dimension scores into one final score and a flag. Plain Python.

All numbers (weights, thresholds) live in config.yaml under `aggregate:`.
"""
from src.schemas import Episode, Scores


def final_score(scores: Scores, cfg: dict) -> float:
    """Weighted average of the available scores, on the same 1-5 scale."""
    weights = cfg["aggregate"]["weights"]
    available = {k: v for k, v in scores.model_dump().items() if v is not None}
    total_weight = sum(weights[k] for k in available)
    return round(sum(weights[k] * v for k, v in available.items()) / total_weight, 2)


def flag_reasons(final: float, scores: Scores, cfg: dict) -> list[str]:
    """Why an episode is flagged as weak (empty list = not flagged)."""
    a = cfg["aggregate"]
    reasons = []
    if final <= a["flag_final_at_or_below"]:
        reasons.append(f"final score {final} <= {a['flag_final_at_or_below']}")
    if scores.pull_to_next <= a["flag_pull_at_or_below"]:
        reasons.append(f"pull_to_next {scores.pull_to_next} <= {a['flag_pull_at_or_below']}")
    return reasons


def line_times(line_ids: list[str], episodes: list[Episode]) -> list[dict]:
    """Look up timestamps for cited line IDs FROM THE PARSER (never from the model)."""
    lookup = {l.id: l for ep in episodes for l in ep.lines}
    return [{"id": i, "start": lookup[i].start, "end": lookup[i].end} for i in line_ids if i in lookup]
