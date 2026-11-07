"""Cliffhanger Auditor: review screen for one editor.

    streamlit run app.py

Pick a screenplay folder (or upload .txt files), run the audit (or load a past
run), review the weakest endings first, and record Accept / Reject / Needs
review for each. Decisions are appended to outputs/decisions.csv.
"""
import json
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from run import episode_range, run
from src.config import ROOT, load_config
from src.llm import has_key
from src.parser import ParseError, parse_folder
from src.windows import build_windows, fmt

DECISIONS = ROOT / "outputs" / "decisions.csv"
RAW = ROOT / "outputs" / "raw"
CHOICES = ["Accept", "Reject", "Needs review"]

st.set_page_config(page_title="Cliffhanger Auditor", layout="wide")
st.title("Cliffhanger Auditor")
st.caption("Scores how each episode ends and how the next one opens, from the script only. "
           "Confidence is model-reported and uncalibrated. Treat low-confidence scores as unsure.")


# --- Sidebar: get results -----------------------------------------------------
with st.sidebar:
    st.header("1. Input")
    folder = st.text_input("Screenplay folder", "demo_data/episodes")
    uploads = st.file_uploader("...or upload .txt screenplays", type="txt", accept_multiple_files=True)
    subset = st.text_input("Episodes (optional, e.g. 1-40)", "")
    key_ok = has_key(load_config()["llm"])
    use_llm = st.checkbox("Use LLM (needs API key in .env)", value=key_ok, disabled=not key_ok,
                          help=None if key_ok else "No API key on this server: baseline scores only.")
    if st.button("Run audit", type="primary"):
        if uploads:   # upload-only mode: write files to a temp folder and run on that
            tmp = Path(tempfile.mkdtemp())
            for f in uploads:
                (tmp / f.name).write_bytes(f.getvalue())
            folder = str(tmp)
        bar = st.progress(0.0, "Scoring...")
        try:
            out_dir, rows = run(folder, episode_range(subset), use_llm, load_config()["save_text"],
                                progress=lambda i, n: bar.progress(i / n, f"Scored {i}/{n}"))
            st.session_state.update(rows=rows, run_id=out_dir.name, folder=folder)
        except ParseError as e:
            st.error(f"Input error: {e}")

    st.header("...or load a past run")
    past = sorted((p.name for p in RAW.glob("*") if (p / "results.json").exists()), reverse=True)
    chosen = st.selectbox("Run", [""] + past)
    if chosen and st.button("Load"):
        meta = json.loads((RAW / chosen / "run_meta.json").read_text(encoding="utf-8"))
        rows = json.loads((RAW / chosen / "results.json").read_text(encoding="utf-8"))
        st.session_state.update(rows=rows, run_id=chosen, folder=meta["input_folder"])

if "rows" not in st.session_state:
    st.info("Run an audit or load a past run from the sidebar.")
    st.stop()

rows, run_id = st.session_state["rows"], st.session_state["run_id"]
df = pd.DataFrame(rows)
for col in ["flagged", "final"]:   # missing when the LLM was skipped or failed for every episode
    if col not in df:
        df[col] = None
df["flagged"] = df["flagged"].fillna(False).astype(bool)


# --- Decisions log ------------------------------------------------------------
def load_decisions() -> pd.DataFrame:
    if DECISIONS.exists():
        return pd.read_csv(DECISIONS)
    return pd.DataFrame(columns=["run_id", "episode", "decision", "flagged", "suggested_cut", "decided_at"])


def save_decision(row: dict, decision: str):
    DECISIONS.parent.mkdir(parents=True, exist_ok=True)
    entry = pd.DataFrame([{"run_id": run_id, "episode": row["episode"], "decision": decision,
                           "flagged": row.get("flagged"), "suggested_cut": row.get("suggested_cut"),
                           "decided_at": datetime.now().isoformat(timespec="seconds")}])
    entry.to_csv(DECISIONS, mode="a", header=not DECISIONS.exists(), index=False)


decisions = load_decisions()
latest = (decisions[decisions["run_id"] == run_id].sort_values("decided_at")
          .groupby("episode").last()["decision"].to_dict())
df["decision"] = df["episode"].map(latest)


# --- Summary metrics ----------------------------------------------------------
decided = df[df["decision"].isin(["Accept", "Reject"])]
flagged_decided = decided[decided["flagged"]]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Episodes", len(df))
c2.metric("Flagged weak (LLM)", int(df["flagged"].sum()))
c3.metric("Acceptance rate", f"{(decided['decision'] == 'Accept').mean():.0%}" if len(decided) else "-",
          help="Accepted / (accepted + rejected) for this run")
c4.metric("Flags editor agrees with", f"{(flagged_decided['decision'] == 'Accept').mean():.0%}"
          if len(flagged_decided) else "-", help="Among flagged episodes you decided on, share accepted")


# --- Ranked table -------------------------------------------------------------
st.subheader(f"2. Episodes, weakest first (run {run_id})")
sort_col = "final" if df["final"].notna().any() else "baseline_final"
cols = [c for c in ["episode", "status", "final", "flagged", "ending_type", "none_kind",
                    "confidence_model_reported_uncalibrated", "low_confidence", "suggested_cut",
                    "baseline_final", "decision"] if c in df]
st.dataframe(df.sort_values(sort_col)[cols], hide_index=True, width="stretch")
st.download_button("Export CSV (results + decisions)", df.drop(columns=["raw_response"], errors="ignore")
                   .to_csv(index=False), f"cliffhanger_{run_id}.csv", "text/csv")


# --- Detail view --------------------------------------------------------------
st.subheader("3. Review one episode")
ep_no = st.selectbox("Episode", df.sort_values(sort_col)["episode"].tolist())
row = next(r for r in rows if r["episode"] == ep_no)

windows = None
try:   # screenplay text and timestamps come from the parser, not from the model
    windows = {w.episode: w for w in build_windows(parse_folder(st.session_state["folder"]), load_config())}
except (ParseError, FileNotFoundError):
    st.warning("Screenplay folder not available, so the line text can't be shown (IDs and scores only).")

left, right = st.columns([3, 2])
with right:
    if row.get("status") == "ok":
        st.markdown(f"**Final score:** {row['final']} / 5 {'  🚩 **flagged**' if row['flagged'] else ''}")
        if row["flagged"]:
            st.caption("Why flagged: " + "; ".join(row["flag_reasons"]))
        conf = row["confidence_model_reported_uncalibrated"]
        st.markdown(f"**Ending type:** {row['ending_type']}" + (f" ({row['none_kind']})" if row.get("none_kind") else ""))
        st.markdown(f"**Confidence (model-reported, uncalibrated):** {conf}" + ("  ⚠️ low, check by hand" if row["low_confidence"] else ""))
        st.table(pd.DataFrame({"LLM": [row.get(d) for d in ["unresolved_question", "emotional_spike", "stakes",
                                                             "pull_to_next", "next_opening_strength"]],
                               "Baseline": [row.get(f"baseline_{d}") for d in ["unresolved_question", "emotional_spike",
                                                                                "stakes", "pull_to_next",
                                                                                "next_opening_strength"]]},
                              index=["unresolved_question", "emotional_spike", "stakes", "pull_to_next",
                                     "next_opening_strength"]))
        st.markdown(f"**Reason:** {row.get('reason', '_not saved (save_text is off)_')}")
        cut = row["suggested_cut"]
        if cut == "no_valid_alternative":
            st.markdown("**Suggestion:** no_valid_alternative")
        else:
            t = row["suggested_cut_time"]
            st.markdown(f"**Suggested cut:** end after **{cut}** ({fmt(t['end'])})")
        st.caption(row.get("suggestion_reason", ""))
        if row.get("confusing_not_suspenseful"):
            st.warning("Model flagged this ending as confusing rather than suspenseful.")
    else:
        st.error(f"No valid LLM output: {row.get('status')}. Errors: {row.get('errors')}")
    st.caption("Baseline rules fired: " + "; ".join(row.get("baseline_rules", [])))

    st.markdown("**Your decision**")
    b1, b2, b3 = st.columns(3)
    for col, choice in zip([b1, b2, b3], CHOICES):
        if col.button(choice, key=f"{choice}-{ep_no}"):
            save_decision(row, choice)
            st.rerun()
    st.caption(f"Current: {latest.get(ep_no, 'none yet')}")

with left:
    if windows and ep_no in windows:
        win = windows[ep_no]
        evidence = {e["id"] for e in row.get("evidence", [])}
        cut = row.get("suggested_cut")

        def show(lines):
            for l in lines:
                who = f"{l.speaker} ({l.emotion})" if l.kind == "dialogue" else l.kind.upper()
                mark = " ✂️ **suggested cut**" if l.id == cut else ""
                text = f"`{l.id}` {fmt(l.start)}–{fmt(l.end)} **{who}:** {l.text}{mark}"
                st.markdown(f"> {text}" if l.id in evidence else text)

        st.markdown(f"**Ending of episode {ep_no}** (quoted lines = cited as evidence)")
        show(win.ending)
        if win.opening:
            st.markdown(f"**Opening of episode {win.next_episode}**")
            show(win.opening)
