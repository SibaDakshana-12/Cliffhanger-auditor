"""Compare two models' outputs on the episodes both scored (model-swap test).

    python evaluation/model_swap.py gemini-3.5-flash gemini-3.5-flash-lite

Prints per-episode scores side by side plus how often the two models agree.
Uses the same merge rule as compare.py (latest valid record per episode).
"""
import sys

import pandas as pd

from compare import merge, runs_for_model

DIMS = ["unresolved_question", "emotional_spike", "stakes", "pull_to_next", "next_opening_strength"]


def main(model_a: str, model_b: str):
    a, b = merge(runs_for_model(model_a)), merge(runs_for_model(model_b))
    a, b = a[a["status"] == "ok"], b[b["status"] == "ok"]
    both = a.merge(b, on="episode", suffixes=("_a", "_b"))
    print(f"A = {model_a}, B = {model_b}; episodes scored validly by both: {both['episode'].tolist()} (n={len(both)})\n")
    for d in DIMS + ["final"]:
        diff = (both[f"{d}_a"] - both[f"{d}_b"]).abs()
        print(f"{d:<22} exact {int((diff == 0).sum())}/{len(both)}  within 1: {int((diff <= 1).sum())}/{len(both)}"
              f"  mean A {both[f'{d}_a'].mean():.2f}  mean B {both[f'{d}_b'].mean():.2f}")
    print(f"{'ending_type':<22} same {int((both['ending_type_a'] == both['ending_type_b']).sum())}/{len(both)}")
    print(f"{'flagged':<22} same {int((both['flagged_a'] == both['flagged_b']).sum())}/{len(both)}")
    cols = ["episode", "final_a", "final_b", "flagged_a", "flagged_b", "ending_type_a", "ending_type_b",
            "pull_to_next_a", "pull_to_next_b", "suggested_cut_a", "suggested_cut_b",
            "confidence_model_reported_uncalibrated_a", "confidence_model_reported_uncalibrated_b",
            "output_tokens_a", "output_tokens_b"]
    print("\n" + both[cols].to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
