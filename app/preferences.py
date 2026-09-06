"""Server-side workspace preferences with export/import."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from pydantic import BaseModel, Field

from app.config import DEFAULT_PRIVACY_LAYER, PREFERENCES_PATH

DEFAULT_PREFERENCES: dict[str, Any] = {
    "theme": "dark",
    "locale": "auto",
    "privacy_layer": DEFAULT_PRIVACY_LAYER,
    "country": "DE",
    "llm_provider": "auto",
    "llm_model": "",
    "reduced_motion": False,
    "copilot_dock_open": True,
    "keyboard_shortcuts": True,
    "dashboard_widgets": ["command", "stats", "suggestions", "activity"],
}


class Preferences(BaseModel):
    theme: str = Field(default="dark", pattern="^(dark|light|system)$")
    locale: str = Field(default="auto", pattern="^(auto|en|bg)$")
    privacy_layer: str = ""
    country: str = Field(default="DE", max_length=2)
    llm_provider: str = "auto"
    llm_model: str = ""
    reduced_motion: bool = False
    copilot_dock_open: bool = True
    keyboard_shortcuts: bool = True
    dashboard_widgets: list[str] = Field(
        default_factory=lambda: ["command", "stats", "suggestions", "activity"]
    )


def _read_raw() -> dict[str, Any]:
    if not PREFERENCES_PATH.exists():
        return deepcopy(DEFAULT_PREFERENCES)
    try:
        data = json.loads(PREFERENCES_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return deepcopy(DEFAULT_PREFERENCES)
        merged = deepcopy(DEFAULT_PREFERENCES)
        merged.update({k: v for k, v in data.items() if k in DEFAULT_PREFERENCES})
        return merged
    except (OSError, json.JSONDecodeError):
        return deepcopy(DEFAULT_PREFERENCES)


def load_preferences() -> dict[str, Any]:
    return Preferences(**_read_raw()).model_dump()


def save_preferences(payload: dict[str, Any]) -> dict[str, Any]:
    current = _read_raw()
    current.update({k: v for k, v in payload.items() if k in DEFAULT_PREFERENCES})
    prefs = Preferences(**current)
    PREFERENCES_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREFERENCES_PATH.write_text(
        json.dumps(prefs.model_dump(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return prefs.model_dump()


def export_workspace() -> dict[str, Any]:
    return {
        "format": "argoscout.workspace",
        "version": 1,
        "preferences": load_preferences(),
    }


def import_workspace(bundle: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(bundle, dict):
        raise ValueError("Workspace bundle must be an object")
    prefs = bundle.get("preferences", bundle)
    if not isinstance(prefs, dict):
        raise ValueError("Workspace preferences must be an object")
    return save_preferences(prefs)
