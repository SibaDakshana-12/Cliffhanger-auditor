"""Tests for parser.py and windows.py.

Unit tests use tiny invented screenplays written to a temp folder (no Kuku content).
The last test runs on the real pack in data/episodes/ and is skipped if it isn't there.
"""
from pathlib import Path

import pytest

from src.config import ROOT
from src.parser import ParseError, parse_file, parse_folder
from src.windows import build_windows

CFG = {"windows": {"ending_seconds": 25, "opening_seconds": 10, "fallback_lines": 3}}


def block(tag: str, start: str, end: str, text: str) -> str:
    return f"**{tag}:**\nStart: ({start}) | End: ({end})\n{text}\n"


def script(number: int, blocks: list[str], scene_fields: str = "Scene heading: INT. ROOM – DAY\n"
           "Scene start: 00:00.00\nScene end: 00:40.00\n\nActions and dialogue:\n") -> str:
    return (f"EPISODE NUMBER: Episode {number}\nEPISODE LOGLINE: Test.\nCONTINUITY NOTES: Test.\n\n"
            f"--- SCRIPT START ---\n\nSCENE 01\n{scene_fields}\n" + "\n".join(blocks) + "\n--- SCRIPT END ---")


def write(folder: Path, number: int, blocks: list[str], **kw) -> Path:
    path = folder / f"episode-{number:03d}-Episode {9000 + number}.txt"
    path.write_text(script(number, blocks, **kw), encoding="utf-8")
    return path


# Invented 40-second episode used by several tests.
BLOCKS = [
    block("CAMERA", "00:00.00", "00:05.00", "Wide shot of a lighthouse."),
    block("MIRA (Nervous)", "00:05.50", "00:08.00", '"Did you hear that?"'),
    block("ACTION", "00:09.00", "00:20.00", "Mira climbs the stairs."),
    block("TOMAS (O.S.) (Calm)", "00:20.00", "00:30.00", '"Come up. I have something to show you."'),
    block("SOUND FX", "00:30.00", "00:40.00", "A door slams."),
]


def test_parses_lines_with_ids_and_attached_timestamps(tmp_path):
    ep = parse_file(write(tmp_path, 1, BLOCKS))
    assert ep.number == 1 and ep.duration == 40.0 and len(ep.lines) == 5
    second = ep.lines[1]
    assert (second.id, second.kind, second.speaker, second.emotion) == ("E001-L002", "dialogue", "MIRA", "Nervous")
    assert (second.start, second.end, second.text) == (5.5, 8.0, '"Did you hear that?"')
    assert ep.lines[3].emotion == "O.S., Calm"
    assert ep.lines[4].kind == "sfx"


def test_uppercase_scene_fields_accepted(tmp_path):
    fields = "SCENE HEADING: EXT. PIER – NIGHT\nSCENE START: 00:00.00\nSCENE END: 00:40.00\n\nACTIONS AND DIALOGUE:\n"
    ep = parse_file(write(tmp_path, 1, BLOCKS, scene_fields=fields))
    assert ep.lines[0].scene_heading == "EXT. PIER – NIGHT"


@pytest.mark.parametrize("bad_time, expected", [
    ("Start: (00:05.5) | End: (00:08.00)", "missing or malformed timestamp"),
    ("Start: (00:65.00) | End: (01:08.00)", "seconds must be under 60"),
    ("Start: (00:09.00) | End: (00:08.00)", "end time is before start time"),
])
def test_bad_timestamps_raise(tmp_path, bad_time, expected):
    blocks = BLOCKS[:1] + [f'**MIRA (Nervous):**\n{bad_time}\n"Hi."\n']
    with pytest.raises(ParseError, match=expected):
        parse_file(write(tmp_path, 1, blocks))


def test_missing_timestamp_line_raises(tmp_path):
    with pytest.raises(ParseError, match="line 19: missing or malformed timestamp"):
        parse_file(write(tmp_path, 1, BLOCKS[:1] + ['**MIRA (Nervous):**\n"Hi."\n']))


def test_wrong_format_file_raises(tmp_path):
    (tmp_path / "notes.txt").write_text("Just some notes, not a screenplay.", encoding="utf-8")
    with pytest.raises(ParseError, match="SCRIPT START"):
        parse_folder(tmp_path)


def test_same_kind_duplicate_timestamp_is_a_warning(tmp_path):
    ep = parse_file(write(tmp_path, 1, BLOCKS + [block("CAMERA", "00:00.00", "00:05.00", "Same shot again.")]))
    assert any("duplicate the timestamp" in w for w in ep.warnings)


def test_folder_rejects_duplicates_and_gaps(tmp_path):
    write(tmp_path, 1, BLOCKS)
    write(tmp_path, 3, BLOCKS)
    with pytest.raises(ParseError, match=r"gaps \(missing \[2\]\)"):
        parse_folder(tmp_path)
    (tmp_path / "episode-001-copy.txt").write_text(script(1, BLOCKS), encoding="utf-8")
    with pytest.raises(ParseError, match=r"Duplicate episode numbers: \[1\]"):
        parse_folder(tmp_path)


def test_all_bad_files_are_reported_together(tmp_path):
    write(tmp_path, 1, BLOCKS[:1] + ['**MIRA (Nervous):**\n"Hi."\n'])
    write(tmp_path, 2, ["**CAMERA:**\nStart: (00:00.00) | End: (00:01.00)\n"])
    with pytest.raises(ParseError) as err:
        parse_folder(tmp_path)
    assert "episode-001" in str(err.value) and "episode-002" in str(err.value)


def test_windows_select_by_time_and_last_episode_has_no_opening(tmp_path):
    write(tmp_path, 1, BLOCKS)
    write(tmp_path, 2, BLOCKS)
    w1, w2 = build_windows(parse_folder(tmp_path), CFG)
    # last 25s of a 40s episode = anything ending after 15s
    assert [l.id for l in w1.ending] == ["E001-L003", "E001-L004", "E001-L005"]
    # first 10s of episode 2 = anything starting before 10s
    assert [l.id for l in w1.opening] == ["E002-L001", "E002-L002", "E002-L003"]
    assert w2.next_episode is None and w2.opening == []


def test_short_episode_falls_back_to_last_n_lines(tmp_path):
    short = [block("ACTION", f"00:0{i}.00", f"00:0{i + 1}.00", f"Beat {i}.") for i in range(5)]
    write(tmp_path, 1, short)
    (w,) = build_windows(parse_folder(tmp_path), CFG)
    assert [l.id for l in w.ending] == ["E001-L003", "E001-L004", "E001-L005"]
    assert "only 5.0s long" in w.warnings[0]


REAL = ROOT / "data" / "episodes"


@pytest.mark.skipif(not REAL.is_dir(), reason="real input pack not present")
def test_real_pack_parses():
    episodes = parse_folder(REAL)
    assert [e.number for e in episodes] == list(range(1, 51))
    assert sum(len(e.lines) for e in episodes) == 3727   # matches the raw block count from inspection
    windows = build_windows(episodes, {"windows": {"ending_seconds": 25, "opening_seconds": 10,
                                                   "fallback_lines": 12}})
    assert all(w.ending for w in windows) and windows[-1].opening == []
    assert all(w.opening for w in windows[:-1])
