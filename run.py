"""Run the Cliffhanger Auditor on a folder of screenplays.

    python run.py --input data/episodes
    python run.py --input data/episodes --episodes 1-40 --save-text
    python run.py --input demo_data/episodes --no-llm      # baseline only, no API key needed

Writes outputs/raw/<run_id>/: results.json (one record per episode),
results.csv (same, flat), run_meta.json (model, counts, tokens, cost estimate).
Results are the tool's unedited output. Never hand-edit them.
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.aggregate import final_score, flag_reasons, line_times
from src.baseline import baseline_score
from src.config import ROOT, load_config
from src.parser import ParseError, parse_folder
from src.schemas import Episode, EpisodeWindows
from src.scorer import score_episode
from src.windows import build_windows

# Model-written text that paraphrases the screenplay. Only written to disk when save_text is on.
TEXT_FIELDS = ["reason", "suggestion_reason", "raw_response"]
DIMS = ["unresolved_question", "emotional_spike", "stakes", "pull_to_next", "next_opening_strength"]


def audit_episode(win: EpisodeWindows, episodes: list[Episode], cfg: dict, use_llm: bool) -> dict:
    """LLM score + validation + aggregation + baseline for one episode, as one flat record."""
    row = {"episode": win.episode, "next_episode": win.next_episode,
           "ending_window": f"{win.ending[0].id}..{win.ending[-1].id}", "window_warnings": win.warnings}

    if use_llm:
        rec = score_episode(win, cfg)
        row.update(status=rec.status, model=rec.model, attempts=rec.attempts, api_failures=rec.api_failures,
                   invalid_outputs=rec.invalid_outputs, input_tokens=rec.input_tokens,
                   output_tokens=rec.output_tokens, errors=rec.errors,
                   daily_quota_exhausted=rec.daily_quota_exhausted)
        out = rec.output
        if out:
            final = final_score(out.scores, cfg)
            reasons = flag_reasons(final, out.scores, cfg)
            cut = out.suggested_cut
            row.update(
                ending_type=out.ending_type, none_kind=out.none_kind, **out.scores.model_dump(),
                final=final, flagged=bool(reasons), flag_reasons=reasons,
                weakest_dimension=out.weakest_dimension,
                confidence_model_reported_uncalibrated=out.confidence,
                low_confidence=out.confidence < cfg["aggregate"]["low_confidence_below"],
                confusing_not_suspenseful=out.confusing_not_suspenseful,
                # Timestamps come from the parser via line_times(), never from the model.
                evidence=line_times(out.evidence_line_ids, episodes),
                suggested_cut=cut,
                suggested_cut_time=(line_times([cut], episodes) or [None])[0],
            )
            row.update(reason=out.reason, suggestion_reason=out.suggestion_reason, raw_response=rec.raw_response)
    else:
        row["status"] = "llm_skipped"

    b = baseline_score(win, cfg)
    b_final = final_score(b["scores"], cfg)
    row.update(baseline_ending_type=b["ending_type"],
               **{f"baseline_{k}": v for k, v in b["scores"].model_dump().items()},
               baseline_final=b_final, baseline_flagged=bool(flag_reasons(b_final, b["scores"], cfg)),
               baseline_rules=b["rules"])
    return row


def episode_range(text: str | None) -> set[int] | None:
    """'1-40' -> {1..40}; '3,5,9' -> {3,5,9}; None -> all."""
    if not text:
        return None
    chosen = set()
    for part in text.split(","):
        lo, _, hi = part.partition("-")
        chosen.update(range(int(lo), int(hi or lo) + 1))
    return chosen


def cost_estimate(rows: list[dict], cfg: dict) -> dict:
    """Cost from the REAL token counts of this run, at the paid-tier prices in config.yaml."""
    scored = [r for r in rows if r.get("input_tokens")]
    if not scored:
        return {}
    c = cfg["cost"]
    tin = sum(r["input_tokens"] for r in scored)
    tout = sum(r["output_tokens"] for r in scored)
    per_ep = (tin * c["input_per_million"] + tout * c["output_per_million"]) / 1e6 / len(scored)
    return {"episodes_with_tokens": len(scored), "input_tokens_total": tin, "output_tokens_total": tout,
            "avg_input_tokens_per_episode": round(tin / len(scored)),
            "avg_output_tokens_per_episode": round(tout / len(scored)),
            "usd_per_episode": round(per_ep, 5), "usd_per_50_episodes": round(per_ep * 50, 3),
            "usd_per_100_shows": round(per_ep * c["episodes_per_show"] * 100, 2),
            "prices_used_usd_per_million": {"input": c["input_per_million"], "output": c["output_per_million"]},
            "note": "paid-tier list prices from config.yaml; this run itself used the free tier"}


def run(folder: str, episodes_filter: set[int] | None, use_llm: bool, save_text: bool,
        out_root: Path = ROOT / "outputs" / "raw", progress=None, model: str | None = None) -> tuple[Path, list[dict]]:
    """Returns the output folder and the full rows (rows keep reasons in memory even if save_text is off)."""
    cfg = load_config()
    if model:   # one-off model swap without editing config.yaml
        cfg["llm"]["model"] = model
    episodes = parse_folder(folder)   # raises ParseError with a clear message on bad input
    windows = [w for w in build_windows(episodes, cfg) if episodes_filter is None or w.episode in episodes_filter]
    if not windows:
        raise ParseError(f"No episodes in {folder} match the --episodes filter")

    # Model name in the folder name: two runs with different models can start in the same second.
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + (cfg["llm"]["model"] if use_llm else "baseline")
    out_dir = out_root / run_id
    out_dir.mkdir(parents=True)
    started, rows, quota_hit = time.time(), [], False
    for i, win in enumerate(windows, 1):
        row = audit_episode(win, episodes, cfg, use_llm and not quota_hit)
        if quota_hit:   # listed explicitly, never silently skipped
            row["status"] = "not_run_quota"
        elif row.get("daily_quota_exhausted"):
            quota_hit = True
            print("DAILY API QUOTA EXHAUSTED: no more LLM calls this run; "
                  "remaining episodes get baseline scores only (status not_run_quota).", flush=True)
        rows.append(row)
        print(f"[{i}/{len(windows)}] episode {win.episode}: {row['status']}"
              + (f", final {row['final']}, {'FLAGGED' if row['flagged'] else 'ok'}" if "final" in row else "")
              + f" | baseline {row['baseline_final']}", flush=True)
        if progress:
            progress(i, len(windows))
        # Save after every episode, so a crash or quota stop never loses finished work.
        to_disk = [r if save_text else {k: v for k, v in r.items() if k not in TEXT_FIELDS} for r in rows]
        (out_dir / "results.json").write_text(json.dumps(to_disk, indent=2, ensure_ascii=False), encoding="utf-8")

    pd.json_normalize(to_disk, sep=".").to_csv(out_dir / "results.csv", index=False)
    meta = {"run_id": run_id, "input_folder": str(folder), "episodes": [w.episode for w in windows],
            "llm": cfg["llm"] if use_llm else None, "save_text": save_text,
            "seconds": round(time.time() - started, 1),
            "status_counts": pd.Series([r["status"] for r in rows]).value_counts().to_dict(),
            "api_failures": sum(r.get("api_failures", 0) for r in rows),
            "invalid_outputs": sum(r.get("invalid_outputs", 0) for r in rows),
            "retries": sum(max(r.get("attempts", 0) - 1, 0) for r in rows),
            "flagged_llm": [r["episode"] for r in rows if r.get("flagged")],
            "flagged_baseline": [r["episode"] for r in rows if r["baseline_flagged"]],
            "cost_estimate": cost_estimate(rows, cfg)}
    (out_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps({k: meta[k] for k in ["status_counts", "api_failures", "invalid_outputs", "retries",
                                          "flagged_llm", "cost_estimate"]}, indent=2))
    print(f"Saved to {out_dir}")
    return out_dir, rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Score episode endings in a screenplay folder.")
    ap.add_argument("--input", required=True, help="folder of screenplay .txt files")
    ap.add_argument("--episodes", help="subset, e.g. 1-40 or 3,5,9 (default: all)")
    ap.add_argument("--no-llm", action="store_true", help="baseline only (no API calls)")
    ap.add_argument("--save-text", action="store_true",
                    help="also save model reasons and raw responses (overrides save_text in config.yaml)")
    ap.add_argument("--model", help="override llm.model from config.yaml for this run (model-swap test)")
    args = ap.parse_args()
    try:
        run(args.input, episode_range(args.episodes), not args.no_llm,
            args.save_text or load_config()["save_text"], model=args.model)
    except ParseError as e:
        sys.exit(f"INPUT ERROR: {e}")
