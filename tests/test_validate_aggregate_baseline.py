"""Tests for validators.py, aggregate.py and baseline.py, using invented lines only."""
from src.aggregate import final_score, flag_reasons
from src.baseline import baseline_score
from src.config import load_config
from src.schemas import EpisodeWindows, Line, Scores, ScorerOutput
from src.validators import validate

CFG = load_config()


def line(n: int, kind: str, text: str, ep: int = 1, speaker: str | None = None) -> Line:
    return Line(id=f"E{ep:03d}-L{n:03d}", episode=ep, position=n, scene=1, scene_heading="INT. ROOM",
                kind=kind, speaker=speaker, emotion="Calm" if speaker else None,
                start=float(n), end=float(n + 1), text=text)


WIN = EpisodeWindows(
    episode=1, next_episode=2,
    ending=[line(1, "camera", "Close-up on Mira."),
            line(2, "dialogue", '"Who are you really?"', speaker="MIRA"),
            line(3, "action", "The stranger smiles and steps into the dark.")],
    opening=[line(1, "dialogue", '"Run!"', ep=2, speaker="TOMAS")],
)


def output(**changes) -> ScorerOutput:
    base = dict(ending_type="withheld_reveal", none_kind=None,
                scores=dict(unresolved_question=5, emotional_spike=3, stakes=4, pull_to_next=5,
                            next_opening_strength=4),
                weakest_dimension="emotional_spike", confidence=0.8, reason="Question left open in E001-L002.",
                evidence_line_ids=["E001-L002", "E002-L001"], suggested_cut="E001-L002",
                suggestion_reason="End on the question.")
    base.update(changes)
    return ScorerOutput.model_validate(base)


def test_valid_output_has_no_problems():
    assert validate(output(), WIN) == []


def test_invented_and_out_of_episode_ids_are_rejected():
    problems = validate(output(evidence_line_ids=["E001-L099"], suggested_cut="E002-L001",
                               reason="See E001-L050."), WIN)
    assert len(problems) == 3
    assert "E001-L099" in problems[0] and "E001-L050" in problems[1] and "E002-L001" in problems[2]


def test_cut_on_current_last_line_is_rejected():
    assert "current last line" in validate(output(suggested_cut="E001-L003"), WIN)[0]


def test_flat_none_must_have_low_pull():
    problems = validate(output(ending_type="none", none_kind="flat"), WIN)
    assert any("flat ending must have pull_to_next <= 2" in p for p in problems)
    assert any("none_kind" in p for p in validate(output(ending_type="none"), WIN))


def test_wrong_weakest_dimension_is_rejected():
    assert "not the lowest score" in validate(output(weakest_dimension="stakes"), WIN)[0]


def test_final_score_and_flags():
    s = Scores(unresolved_question=2, emotional_spike=4, stakes=3, pull_to_next=2, next_opening_strength=4)
    final = final_score(s, CFG)   # 0.25*2 + 0.10*4 + 0.20*3 + 0.30*2 + 0.15*4 = 2.7
    assert final == 2.7
    assert len(flag_reasons(final, s, CFG)) == 2


def test_missing_opening_reweights():
    s = Scores(unresolved_question=5, emotional_spike=5, stakes=5, pull_to_next=5)
    assert final_score(s, CFG) == 5.0


def test_baseline_fires_explainable_rules():
    result = baseline_score(WIN, CFG)
    assert result["ending_type"] == "withheld_reveal"
    assert "last spoken line is a question" in result["rules"]
    assert result["scores"].unresolved_question == 5   # 2 + 2 (question) + 1 (reveal word "really")
