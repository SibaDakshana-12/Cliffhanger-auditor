"""Merge several runs of one model into a single run folder (e.g. when quota split a run).

    python evaluation/merge_runs.py gemini-3.5-flash-lite

Writes outputs/raw/merged-<model>/ with results.json, results.csv and run_meta.json.
Records are copied unchanged (latest valid record per episode, same rule as
compare.py); run_meta.json lists the source runs. The source runs are not modified.
"""
import json
import sys

import pandas as pd

from compare import ROOT, merge, runs_for_model


def main(model: str):
    paths = [p for p in runs_for_model(model) if not p.parent.name.startswith("merged-")]
    df = merge(paths)
    out = ROOT / "outputs" / "raw" / f"merged-{model}"
    out.mkdir(parents=True, exist_ok=True)
    rows = json.loads(df.to_json(orient="records"))
    (out / "results.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    pd.json_normalize(rows, sep=".").to_csv(out / "results.csv", index=False)
    meta = {"run_id": out.name, "merged_from": [p.parent.name for p in paths],
            "input_folder": json.loads((paths[-1].parent / "run_meta.json").read_text(encoding="utf-8"))["input_folder"],
            "llm": {"model": model}, "episodes": df["episode"].tolist(),
            "status_counts": df["status"].value_counts().to_dict(),
            "flagged_llm": df.loc[df["flagged"] == True, "episode"].tolist()}  # noqa: E712
    (out / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
