"""Choose the lines the scorer will see: the end of each episode and the start of the next.

Windows are chosen by timestamp, then kept in the screenplay's own order.
Times are *script time* (the latest End timestamp in the file), not a measured
video length: the final cut may differ.

Debug view:  python -m src.windows <folder> [--show EPISODE_NUMBER]
"""
import argparse
import logging

from src.config import load_config
from src.parser import parse_folder
from src.schemas import Episode, EpisodeWindows, Line

log = logging.getLogger(__name__)


def ending_window(ep: Episode, seconds: float, fallback_lines: int) -> tuple[list[Line], list[str]]:
    """Lines that overlap the last `seconds` of the episode."""
    if ep.duration < seconds:
        return ep.lines[-fallback_lines:], [
            f"episode is only {ep.duration:.1f}s long (< {seconds}s); ending window = last {fallback_lines} lines"]
    cutoff = ep.duration - seconds
    return [l for l in ep.lines if l.end > cutoff], []


def opening_window(ep: Episode, seconds: float, fallback_lines: int) -> tuple[list[Line], list[str]]:
    """Lines that start within the first `seconds` of the episode."""
    picked = [l for l in ep.lines if l.start < seconds]
    if not picked:
        return ep.lines[:fallback_lines], [
            f"no line of episode {ep.number} starts before {seconds}s; opening window = first {fallback_lines} lines"]
    return picked, []


def build_windows(episodes: list[Episode], cfg: dict) -> list[EpisodeWindows]:
    w = cfg["windows"]
    result = []
    for i, ep in enumerate(episodes):
        ending, warnings = ending_window(ep, w["ending_seconds"], w["fallback_lines"])
        nxt = episodes[i + 1] if i + 1 < len(episodes) else None   # last episode has no next opening
        opening = []
        if nxt:
            opening, more = opening_window(nxt, w["opening_seconds"], w["fallback_lines"])
            warnings += more
        for msg in warnings:
            log.warning("Episode %d: %s", ep.number, msg)
        result.append(EpisodeWindows(episode=ep.number, ending=ending, opening=opening,
                                     next_episode=nxt.number if nxt else None, warnings=warnings))
    return result


def fmt(seconds: float) -> str:
    return f"{int(seconds // 60):02d}:{seconds % 60:05.2f}"


def print_lines(lines: list[Line]) -> None:
    for l in lines:
        who = f"{l.speaker} ({l.emotion})" if l.kind == "dialogue" else l.kind.upper()
        print(f"  [{l.id}] {fmt(l.start)}-{fmt(l.end)}  {who}: {l.text}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="WARNING %(message)s")
    ap = argparse.ArgumentParser(description="Show ending/opening windows for a screenplay folder.")
    ap.add_argument("folder")
    ap.add_argument("--show", type=int, help="print the full window text for this episode number")
    args = ap.parse_args()

    episodes = parse_folder(args.folder)
    windows = build_windows(episodes, load_config())
    by_number = {e.number: e for e in episodes}
    if args.show is not None:
        win = next(x for x in windows if x.episode == args.show)
        print(f"Episode {win.episode}: ENDING ({len(win.ending)} lines)")
        print_lines(win.ending)
        print(f"Episode {win.next_episode}: OPENING ({len(win.opening)} lines)" if win.next_episode
              else "No next episode in this folder.")
        print_lines(win.opening)
    else:
        print("ep  duration  scenes  lines  ending(lines, span)        opening(lines)")
        for win in windows:
            ep = by_number[win.episode]
            span = f"{fmt(min(l.start for l in win.ending))}-{fmt(ep.duration)}"
            print(f"{ep.number:>3}  {fmt(ep.duration)}  {len({l.scene for l in ep.lines}):>6}  {len(ep.lines):>5}"
                  f"  {len(win.ending):>3}  {span:<20}  {len(win.opening) if win.next_episode else '-':>6}")
