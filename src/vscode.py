"""VS Code theme switching via settings.json."""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

VSCODE_SETTINGS_PATH = Path(os.environ.get("APPDATA", "")) / "Code" / "User" / "settings.json"


def is_vscode_installed() -> bool:
    """Check if VS Code settings.json exists."""
    return VSCODE_SETTINGS_PATH.exists()


def get_current_theme() -> str | None:
    """Read the current VS Code color theme."""
    try:
        with open(VSCODE_SETTINGS_PATH, "r", encoding="utf-8") as f:
            settings = json.load(f)
        return settings.get("workbench.colorTheme")
    except (FileNotFoundError, json.JSONDecodeError, PermissionError) as e:
        logger.debug("Cannot read VS Code settings: %s", e)
        return None


def set_theme(dark: bool, dark_theme: str = "Default Dark Modern",
              light_theme: str = "Default Light Modern") -> bool:
    """Switch VS Code theme. Returns True on success."""
    if not is_vscode_installed():
        logger.debug("VS Code not installed, skipping")
        return False

    target_theme = dark_theme if dark else light_theme

    try:
        with open(VSCODE_SETTINGS_PATH, "r", encoding="utf-8") as f:
            settings = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, PermissionError) as e:
        logger.warning("Cannot read VS Code settings: %s", e)
        return False

    current = settings.get("workbench.colorTheme")
    if current == target_theme:
        logger.debug("VS Code theme already set to %s", target_theme)
        return True

    settings["workbench.colorTheme"] = target_theme

    try:
        with open(VSCODE_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
        logger.info("VS Code theme set to %s", target_theme)
        return True
    except PermissionError as e:
        logger.warning("Cannot write VS Code settings: %s", e)
        return False
