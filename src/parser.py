"""Parse screenplay .txt files into Episodes made of timestamped Lines.

Plain regex, no AI. Each block in the script looks like:

    **LADY JULIANA (Confused, Breathless):**
    Start: (00:13.50) | End: (00:14.30)
    "Why?"

and becomes one Line with an ID like E001-L042 and its own timestamp attached.
Anything that doesn't match the expected format raises ParseError naming the
file and line number. We never guess and never silently skip an episode.
"""
import logging
import re
from pathlib import Path

from src.schemas import Episode, Line

log = logging.getLogger(__name__)


class ParseError(Exception):
    """The input is not in the screenplay format this tool understands."""


EPISODE_NUMBER_RE = re.compile(r"^EPISODE NUMBER:\s*Episode\s+(\d+)$")
SCRIPT_START = "--- SCRIPT START ---"
SCRIPT_END = "--- SCRIPT END ---"
SCENE_RE = re.compile(r"^SCENE\s+(\d+)$")
# Field names are matched case-insensitively: episode 6 writes them in capitals.
SCENE_FIELD_RE = re.compile(
    r"^(scene heading|scene start|scene end|actions and dialogue):\s*(.*)$", re.IGNORECASE
)
CLOCK_RE = re.compile(r"^(\d{2}):(\d{2})\.(\d{2})$")
TAG_RE = re.compile(r"^\*\*(.+?):\*\*$")
TIME_RE = re.compile(
    r"^Start:\s*\((\d{2}:\d{2}\.\d{2})\)\s*\|\s*End:\s*\((\d{2}:\d{2}\.\d{2})\)$"
)
FILENAME_RE = re.compile(r"^episode-(\d+)-", re.IGNORECASE)
NON_DIALOGUE_TAGS = {"CAMERA": "camera", "ACTION": "action", "SOUND FX": "sfx"}


def to_seconds(clock: str) -> float | None:
    """'01:05.40' -> 65.4. Returns None if the text is not a valid MM:SS.cc time."""
    m = CLOCK_RE.match(clock.strip())
    if not m or int(m[2]) >= 60:
        return None
    return int(m[1]) * 60 + int(m[2]) + int(m[3]) / 100


def split_tag(tag: str) -> tuple[str, str | None, str | None]:
    """Return (kind, speaker, emotion) for a block tag such as 'MATRIARCH (O.S.) (Firm)'."""
    if tag.upper() in NON_DIALOGUE_TAGS:
        return NON_DIALOGUE_TAGS[tag.upper()], None, None
    speaker = tag.split("(")[0].strip()
    brackets = re.findall(r"\(([^)]*)\)", tag)
    return "dialogue", speaker, ", ".join(brackets) or None


def parse_file(path: Path | str) -> Episode:
    path = Path(path)
    try:
        rows = path.read_text(encoding="utf-8-sig").splitlines()
    except UnicodeDecodeError as e:
        raise ParseError(f"{path.name}: not UTF-8 text ({e})")

    def fail(row_index: int, message: str):
        raise ParseError(f"{path.name}, line {row_index + 1}: {message}")

    # --- Header: script markers and episode number -------------------------
    stripped = [r.strip() for r in rows]
    if stripped.count(SCRIPT_START) != 1 or stripped.count(SCRIPT_END) != 1:
        raise ParseError(f"{path.name}: needs exactly one '{SCRIPT_START}' and one '{SCRIPT_END}' line")
    start_at, end_at = stripped.index(SCRIPT_START), stripped.index(SCRIPT_END)
    if end_at < start_at:
        raise ParseError(f"{path.name}: '{SCRIPT_END}' comes before '{SCRIPT_START}'")

    numbers = [int(m[1]) for r in stripped[:start_at] if (m := EPISODE_NUMBER_RE.match(r))]
    if len(numbers) != 1:
        raise ParseError(f"{path.name}: needs exactly one 'EPISODE NUMBER: Episode N' line before the script")
    number = numbers[0]
    name_match = FILENAME_RE.match(path.name)
    if name_match and int(name_match[1]) != number:
        raise ParseError(f"{path.name}: file name says episode {int(name_match[1])} but header says {number}")

    # --- Script body: scenes and blocks ------------------------------------
    lines: list[Line] = []
    scene, heading = None, ""
    i = start_at + 1
    while i < end_at:
        row = stripped[i]
        if not row:
            i += 1
            continue

        if m := SCENE_RE.match(row):
            scene, heading = int(m[1]), ""
            i += 1
            continue

        if m := SCENE_FIELD_RE.match(row):
            if scene is None:
                fail(i, f"'{m[1]}' appears before any 'SCENE NN' line")
            field = m[1].lower()
            if field == "scene heading":
                heading = m[2].strip()
            elif field in ("scene start", "scene end") and to_seconds(m[2]) is None:
                fail(i, f"malformed time {m[2]!r} (expected MM:SS.cc)")
            i += 1
            continue

        if m := TAG_RE.match(row):
            if scene is None:
                fail(i, "block appears before any 'SCENE NN' line")
            # The timestamp must be on the very next line: that is what keeps it attached.
            time_row = stripped[i + 1] if i + 1 < end_at else ""
            t = TIME_RE.match(time_row)
            if not t:
                fail(i + 1, f"missing or malformed timestamp after {row!r}: found {time_row!r}, "
                            "expected 'Start: (MM:SS.cc) | End: (MM:SS.cc)'")
            start, end = to_seconds(t[1]), to_seconds(t[2])
            if start is None or end is None:
                fail(i + 1, f"invalid time in {time_row!r} (seconds must be under 60)")
            if end < start:
                fail(i + 1, f"end time is before start time in {time_row!r}")

            # Text = the non-blank rows after the timestamp, up to the next blank row.
            j, text_rows = i + 2, []
            while j < end_at and stripped[j] and not TAG_RE.match(stripped[j]) and not SCENE_RE.match(stripped[j]):
                text_rows.append(stripped[j])
                j += 1
            if not text_rows:
                fail(i, f"block {row!r} has no text")

            kind, speaker, emotion = split_tag(m[1].strip())
            if kind == "dialogue" and not speaker:
                fail(i, f"dialogue tag {row!r} has no speaker name")
            position = len(lines) + 1
            lines.append(Line(
                id=f"E{number:03d}-L{position:03d}", episode=number, position=position,
                scene=scene, scene_heading=heading, kind=kind, speaker=speaker, emotion=emotion,
                start=start, end=end, text=" ".join(text_rows),
            ))
            i = j
            continue

        fail(i, f"unrecognised line {row!r}")

    if not lines:
        raise ParseError(f"{path.name}: script contains no blocks")
    return Episode(number=number, file=path.name, duration=max(l.end for l in lines),
                   lines=lines, warnings=check_timing(lines))


def check_timing(lines: list[Line]) -> list[str]:
    """Non-fatal timing oddities. They don't break windows (which select by time), but we report them."""
    warnings = []
    backwards = [b.id for a, b in zip(lines, lines[1:]) if b.start < a.start]
    if backwards:
        warnings.append(f"{len(backwards)} block(s) start earlier than the block before them: {', '.join(backwards)}")
    # CAMERA and ACTION often share a time on purpose, so only same-kind repeats count as duplicates.
    seen, duplicates = set(), []
    for l in lines:
        key = (l.kind, l.start, l.end)
        if key in seen:
            duplicates.append(l.id)
        seen.add(key)
    if duplicates:
        warnings.append(f"{len(duplicates)} block(s) duplicate the timestamp of an earlier block of the same kind: "
                        f"{', '.join(duplicates)}")
    return warnings


def parse_folder(folder: Path | str) -> list[Episode]:
    """Parse every .txt file in a folder. Raises one ParseError listing every problem found."""
    folder = Path(folder)
    if not folder.is_dir():
        raise ParseError(f"Input folder not found: {folder}")
    files = sorted(folder.glob("*.txt"))
    if not files:
        raise ParseError(f"No .txt screenplay files in {folder}")
    ignored = [p.name for p in folder.iterdir() if p.is_file() and p.suffix.lower() != ".txt"]
    if ignored:
        log.warning("Ignoring non-.txt files: %s", ", ".join(ignored))

    episodes, errors = [], []
    for f in files:
        try:
            episodes.append(parse_file(f))
        except ParseError as e:
            errors.append(str(e))

    # Folder-level checks: each ending is paired with episode N+1, so numbering must be unique and gap-free.
    numbers = sorted(e.number for e in episodes)
    dupes = sorted({n for n in numbers if numbers.count(n) > 1})
    if dupes:
        errors.append(f"Duplicate episode numbers: {dupes}")
    elif numbers:
        missing = sorted(set(range(numbers[0], numbers[-1] + 1)) - set(numbers))
        if missing:
            errors.append(f"Episode numbers have gaps (missing {missing}); endings would be paired "
                          "with the wrong next episode")
    if errors:
        raise ParseError(f"{len(errors)} problem(s) in {folder}:\n  - " + "\n  - ".join(errors))

    for e in episodes:
        for w in e.warnings:
            log.warning("Episode %d: %s", e.number, w)
    return sorted(episodes, key=lambda e: e.number)
