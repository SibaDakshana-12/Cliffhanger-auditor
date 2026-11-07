"""Load config.yaml once so every module reads settings the same way."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_config(path: Path | str = ROOT / "config.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)
