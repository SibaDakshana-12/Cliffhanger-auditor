"""Compare my manual scores with the LLM and the rule-based baseline.

    python evaluation/compare.py                          # merges all runs of the model in config.yaml
    python evaluation/compare.py --model gemini-2.5-flash # merges all runs of another model
    python evaluation/compare.py --results outputs/raw/<run_id>/results.json [more.json ...]

Quota limits can split one model's scoring over several runs, so results are
merged by episode: the latest valid ("ok") record wins, otherwise the latest record.

Reports exact agreement and agreement within 1 point per dimension, ending-type
agreement, and flag agreement (false positives / false negatives).
n = 10 is a tiny sample: treat every number here as a rough signal, not proof.
Writes evaluation/comparison.csv (numbers and labels only, no screenplay text).
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DIMS = ["unresolved_question", "emotional_spike", "stakes", "pull_to_next", "next_opening_strength"]


def runs_for_model(model: str) -> list[Path]:
    """All results.json files (oldest first) from runs that used this model."""
    found = []
    for meta_path in sorted((ROOT / "outputs" / "raw").glob("*/run_meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if (meta.get("llm") or {}).get("model") == model:
            found.append(meta_path.parent / "results.json")
    if not found:
        sys.exit(f"No runs of {model} found in outputs/raw/. Run run.py first.")
    return found


def merge(paths: list[Path]) -> pd.DataFrame:
    best = {}
    for path in paths:   # later files override earlier ones, but never replace "ok" with a failure
        for row in json.loads(path.read_text(encoding="utf-8")):
            old = best.get(row["episode"])
            if old is None or row.get("status") == "ok" or old.get("status") != "ok":
                best[row["episode"]] = row
    return pd.DataFrame(sorted(best.values(), key=lambda r: r["episode"]))


def agreement(a: pd.Series, b: pd.Series) -> tuple[str, str]:
    ok = a.notna() & b.notna()
    diff = (a[ok] - b[ok]).abs()
    return f"{(diff == 0).sum()}/{ok.sum()}", f"{(diff <= 1).sum()}/{ok.sum()}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, nargs="+", default=None)
    ap.add_argument("--model", default=None, help="default: llm.model in config.yaml")
    ap.add_argument("--manual", type=Path, default=ROOT / "evaluation" / "manual_scores.csv")
    args = ap.parse_args()
    if args.results:
        paths = args.results
    else:
        import yaml
        model = args.model or yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))["llm"]["model"]
        paths = runs_for_model(model)
    results_path = ", ".join(p.parent.name for p in paths)

    manual = pd.read_csv(args.manual)
    tool = merge(paths)
    df = manual.merge(tool, on="episode", how="left", suffixes=("", "_tool"))
    missing = df[df["status"] != "ok"]["episode"].tolist()

    print(f"Results: {results_path}\nManual episodes: {df['episode'].tolist()}  (n={len(df)}: tiny sample)")
    if missing:
        print(f"WARNING: no valid LLM output for episodes {missing}; they count as disagreements-missing")

    rows = []
    for dim in DIMS + ["overall"]:
        llm_col, base_col = (dim, f"baseline_{dim}") if dim != "overall" else ("final", "baseline_final")
        llm_vals = df[f"{dim}_tool"] if f"{dim}_tool" in df else df[llm_col]
        base_vals = df[base_col]
        if dim == "overall":   # compare my 1-5 overall with the weighted final rounded to a whole number
            llm_vals, base_vals = df["final"].round(), df["baseline_final"].round()
        le, l1 = agreement(df[dim], llm_vals)
        be, b1 = agreement(df[dim], base_vals)
        rows.append({"measure": dim, "llm_exact": le, "llm_within_1": l1, "baseline_exact": be, "baseline_within_1": b1})

    def match(col):
        ok = df[col].notna()
        return f"{(df.loc[ok, 'ending_type'] == df.loc[ok, col]).sum()}/{ok.sum()}"
    rows.append({"measure": "ending_type", "llm_exact": match("ending_type_tool"),
                 "baseline_exact": match("baseline_ending_type")})

    def flags(col):
        me, it = df["flagged"].astype(bool), df[col].fillna(False).astype(bool)
        return (f"{(me == it).sum()}/{len(df)}",
                f"FP {df.loc[it & ~me, 'episode'].tolist()} FN {df.loc[~it & me, 'episode'].tolist()}")
    (la, lerr), (ba, berr) = flags("flagged_tool"), flags("baseline_flagged")
    rows.append({"measure": "flagged", "llm_exact": la, "llm_within_1": lerr, "baseline_exact": ba,
                 "baseline_within_1": berr})
    summary = pd.DataFrame(rows)
    print("\n" + summary.to_string(index=False))
    print("(for 'flagged': FP = tool flags but I didn't, FN = I flag but the tool didn't)")

    per_ep = pd.DataFrame({
        "episode": df["episode"], "my_overall": df["overall"], "llm_final": df["final"],
        "baseline_final": df["baseline_final"], "my_flag": df["flagged"], "llm_flag": df["flagged_tool"],
        "baseline_flag": df["baseline_flagged"], "my_type": df["ending_type"], "llm_type": df["ending_type_tool"],
        "llm_none_kind": df["none_kind"], "baseline_type": df["baseline_ending_type"],
        "llm_confidence_uncalibrated": df["confidence_model_reported_uncalibrated"],
        "my_pull": df["pull_to_next"], "llm_pull": df["pull_to_next_tool"], "baseline_pull": df["baseline_pull_to_next"],
    })
    print("\n" + per_ep.to_string(index=False))
    out = ROOT / "evaluation" / f"comparison_{tool['model'].dropna().iloc[0] if 'model' in tool and tool['model'].notna().any() else 'baseline'}.csv"
    pd.concat([summary.assign(section="summary"), per_ep.assign(section="per_episode")]).to_csv(out, index=False)
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()
