"""Score one episode's ending (and the next episode's opening) with the LLM.

Steps: format the window lines -> fill prompts/scorer_prompt.md -> call the LLM
-> parse the JSON with Pydantic. Failed calls and invalid outputs are retried
up to `max_retries` times and counted, never hidden.

Try it:  python -m src.scorer data/episodes --episodes 2 3
"""
import argparse
import json
import re
import time

from pydantic import ValidationError

from src.config import ROOT, load_config
from src.llm import call_llm, is_daily_quota, is_retryable
from src.parser import parse_folder
from src.schemas import EpisodeWindows, Line, ScoreRecord, ScorerOutput
from src.validators import validate
from src.windows import build_windows, fmt

PROMPTS = ROOT / "prompts"
RETRY_NOTE = "\n\nYour previous answer was rejected for these reasons. Return a corrected JSON object:\n"


def mask(text: str, cfg: dict) -> str:
    """Hide writer labels such as 'cliffhanger' so the model judges the scene, not the label."""
    words = "|".join(re.escape(w) for w in cfg["model_input"]["mask_words"])
    return re.sub(rf"\b({words})\b", cfg["model_input"]["mask_with"], text, flags=re.IGNORECASE)


def format_line(line: Line, cfg: dict) -> str:
    if line.kind == "dialogue":
        return f"{line.id} | {fmt(line.start)} | DIALOGUE {line.speaker} ({line.emotion}): {line.text}"
    # Masking applies to stage directions only; dialogue is never altered.
    return f"{line.id} | {fmt(line.start)} | {line.kind.upper()}: {mask(line.text, cfg)}"


def build_prompt(win: EpisodeWindows, cfg: dict) -> str:
    template = (PROMPTS / "scorer_prompt.md").read_text(encoding="utf-8")
    rubric = (PROMPTS / "rubric.md").read_text(encoding="utf-8")
    opening = "\n".join(format_line(l, cfg) for l in win.opening) or "(none: this is the last episode in the folder)"
    return (template
            .replace("{{RUBRIC}}", rubric)
            .replace("{{EPISODE}}", str(win.episode))
            .replace("{{LAST_LINE_ID}}", win.ending[-1].id)
            .replace("{{ENDING_LINES}}", "\n".join(format_line(l, cfg) for l in win.ending))
            .replace("{{OPENING_LINES}}", opening))


def score_episode(win: EpisodeWindows, cfg: dict) -> ScoreRecord:
    llm_cfg = cfg["llm"]
    record = ScoreRecord(episode=win.episode, status="api_failed", model=llm_cfg["model"])
    base_prompt = prompt = build_prompt(win, cfg)

    for attempt in range(1 + llm_cfg["max_retries"]):
        if attempt:
            time.sleep(llm_cfg["retry_wait_seconds"])
        record.attempts += 1
        try:
            resp = call_llm(prompt, llm_cfg)
        except Exception as e:  # network error, quota, server error...
            record.api_failures += 1
            record.errors.append(f"attempt {record.attempts}: API error: {type(e).__name__}: {str(e)[:300]}")
            if is_daily_quota(e):
                record.daily_quota_exhausted = True
            if not is_retryable(e):
                break
            continue
        record.input_tokens += resp.input_tokens
        record.output_tokens += resp.output_tokens
        record.raw_response = resp.text
        try:
            output = ScorerOutput.model_validate_json(resp.text)
            problems = validate(output, win)
        except ValidationError as e:
            problems = [f"JSON does not match the schema: {str(e)[:300]}"]
        if problems:
            record.invalid_outputs += 1
            record.status = "invalid_output"
            record.errors.append(f"attempt {record.attempts}: invalid output: {'; '.join(problems)}")
            # Retry once more with the problems spelled out, so the model can fix them.
            prompt = base_prompt + RETRY_NOTE + "\n".join(f"- {p}" for p in problems)
            continue
        record.output, record.status = output, "ok"
        return record
    return record   # all attempts used up; status says why


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Score a few episodes and print the raw records.")
    ap.add_argument("folder")
    ap.add_argument("--episodes", type=int, nargs="+", required=True)
    ap.add_argument("--show-prompt", action="store_true", help="print the prompt instead of calling the LLM")
    args = ap.parse_args()

    cfg = load_config()
    windows = {w.episode: w for w in build_windows(parse_folder(args.folder), cfg)}
    for n in args.episodes:
        if args.show_prompt:
            print(build_prompt(windows[n], cfg))
            continue
        rec = score_episode(windows[n], cfg)
        print(json.dumps(rec.model_dump(exclude={"raw_response"}), indent=2))
