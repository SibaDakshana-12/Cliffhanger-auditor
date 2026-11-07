"""Data shapes shared across the pipeline (Pydantic validates types for us)."""
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class Line(BaseModel):
    """One screenplay block: a tag, its own Start/End timestamp, and its text."""
    id: str                  # stable ID, e.g. "E001-L042" (episode 1, 42nd block in the file)
    episode: int
    position: int            # 1-based order of the block in the file
    scene: int
    scene_heading: str
    kind: Literal["camera", "action", "sfx", "dialogue"]
    speaker: str | None      # dialogue only, e.g. "LADY JULIANA"
    emotion: str | None      # dialogue only, text inside the brackets, e.g. "Confused, Breathless"
    start: float             # seconds of script time
    end: float
    text: str


class Episode(BaseModel):
    number: int
    file: str
    duration: float          # latest End timestamp in the script (script time, not measured video length)
    lines: list[Line]
    warnings: list[str] = []


class EpisodeWindows(BaseModel):
    """What the scorer will see for one episode."""
    episode: int
    ending: list[Line]               # end of this episode
    next_episode: int | None         # None for the last episode in the folder
    opening: list[Line]              # start of the next episode (empty for the last one)
    warnings: list[str] = []


# --- Scorer output ---------------------------------------------------------
# Pydantic checks shape, types, allowed values and the 1-5 range.
# Whether cited line IDs really exist is checked later in validators.py.

ENDING_TYPES = Literal["withheld_reveal", "humiliation_status_reversal", "threat", "decision", "other", "none"]
DIMENSIONS = Literal["unresolved_question", "emotional_spike", "stakes", "pull_to_next", "next_opening_strength"]
Score = Annotated[int, Field(ge=1, le=5)]


class Scores(BaseModel):
    unresolved_question: Score
    emotional_spike: Score
    stakes: Score
    pull_to_next: Score
    next_opening_strength: int | None = Field(default=None, ge=1, le=5)   # None when there is no next episode


class ScorerOutput(BaseModel):
    """Exactly what the LLM must return (as JSON)."""
    ending_type: ENDING_TYPES
    none_kind: Literal["deliberate", "flat"] | None = None   # only when ending_type is "none"
    scores: Scores
    weakest_dimension: DIMENSIONS
    confidence: float = Field(ge=0, le=1)   # model-reported, uncalibrated
    reason: str
    evidence_line_ids: list[str] = Field(min_length=1)
    suggested_cut: str                      # a line ID, or "no_valid_alternative"
    suggestion_reason: str
    confusing_not_suspenseful: bool = False


class ScoreRecord(BaseModel):
    """One episode's scoring attempt, including what went wrong along the way."""
    episode: int
    status: Literal["ok", "invalid_output", "api_failed"]
    output: ScorerOutput | None = None
    model: str
    attempts: int = 0
    api_failures: int = 0
    invalid_outputs: int = 0
    errors: list[str] = []          # one message per failed attempt
    input_tokens: int = 0           # summed over all attempts (real counts reported by the API)
    output_tokens: int = 0          # includes the model's "thinking" tokens, which are billed as output
    raw_response: str | None = None # last raw model text, kept for debugging
    daily_quota_exhausted: bool = False  # tells run.py to stop instead of failing every remaining episode
