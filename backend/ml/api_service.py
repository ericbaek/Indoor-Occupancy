from __future__ import annotations

import json
from pathlib import Path

from .predict import load_bundle


class ModelUnavailableError(RuntimeError):
    pass


def model_status(model_dir: str | Path) -> dict:
    directory = Path(model_dir).resolve()
    bundle_path = directory / "model_bundle.joblib"
    metadata_path = directory / "metadata.json"
    if not bundle_path.exists():
        return {
            "status": "model_unavailable",
            "model_ready": False,
            "reason": "model_bundle.joblib was not found; run the training command first",
            "dry_run_only": True,
        }

    try:
        bundle = load_bundle(directory)
    except Exception as exc:
        return {
            "status": "model_unavailable",
            "model_ready": False,
            "reason": f"model bundle could not be loaded: {exc}",
            "dry_run_only": True,
        }

    metadata = _read_optional_json(metadata_path)
    return {
        "status": "ready",
        "model_ready": True,
        "model_name": metadata.get("model_name") or bundle["occupancy"].get("name"),
        "model_version": metadata.get("model_version") or bundle.get("model_version"),
        "trained_at": metadata.get("trained_at"),
        "dry_run_only": True,
    }


def require_model(model_dir: str | Path) -> dict:
    status = model_status(model_dir)
    if not status["model_ready"]:
        raise ModelUnavailableError(status["reason"])
    return status


def read_json_artifact(model_dir: str | Path, filename: str) -> dict:
    require_model(model_dir)
    path = Path(model_dir) / filename
    if not path.exists():
        raise ModelUnavailableError(f"{filename} was not found in the model directory")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelUnavailableError(f"{filename} could not be read") from exc
    if not isinstance(value, dict):
        raise ModelUnavailableError(f"{filename} must contain a JSON object")
    return value


def read_recommendation_history(model_dir: str | Path, limit: int) -> list[dict]:
    require_model(model_dir)
    path = Path(model_dir) / "recommendation_log.jsonl"
    if not path.exists():
        return []
    entries: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ModelUnavailableError("recommendation history could not be read") from exc
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            entries.append(value)
        if len(entries) >= limit:
            break
    return entries


def _read_optional_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}
