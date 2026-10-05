from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_rules() -> dict:
    return load_yaml(ROOT / "config" / "rules.yaml")


def load_watchlist() -> list[str]:
    return load_yaml(ROOT / "config" / "watchlist.yaml").get("watchlist", [])
