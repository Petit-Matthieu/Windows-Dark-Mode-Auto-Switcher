"""Configuration management for Dark Mode Auto Switcher."""

import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_base_dir():
    """获取应用根目录：exe 模式下为 exe 所在目录，开发模式下为项目根目录。"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后，sys.executable 指向 exe 文件
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent.parent


CONFIG_PATH = _get_base_dir() / "config.json"


def get_default_config() -> dict:
    return {
        "location": {
            "latitude": None,
            "longitude": None,
            "timezone": None,
            "city": None,
            "auto_detect": True,
            "location_mode": "auto",  # "auto" = IP检测, "city" = 选择城市
        },
        "offsets": {
            "sunrise_offset_minutes": 0,
            "sunset_offset_minutes": 0,
        },
        "themes": {
            "vscode_dark": "Default Dark Modern",
            "vscode_light": "Default Light Modern",
            "word_dark": "深色",
            "word_light": "浅色",
            "wyy_dark": "深色模式",
            "wyy_light": "浅色模式",
        },
        "features": {
            "switch_system_theme": True,
            "switch_vscode": True,
            "switch_edge_dark_reader": True,
            "switch_word": True,
            "switch_wyy": True,
        },
        "autostart": True,
        "minimize_to_tray": True,  # 关闭窗口时最小化到托盘而非退出
    }


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base, preserving nested structure."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config() -> dict:
    """Load config from file, merging with defaults."""
    default = get_default_config()
    if not CONFIG_PATH.exists():
        return default
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)
        return _deep_merge(default, saved)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load config, using defaults: %s", e)
        # Backup corrupt file
        backup = CONFIG_PATH.with_suffix(".json.bak")
        try:
            CONFIG_PATH.rename(backup)
            logger.info("Backed up corrupt config to %s", backup)
        except OSError:
            pass
        return default


def save_config(config: dict) -> None:
    """Save config to file."""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except OSError as e:
        logger.error("Failed to save config: %s", e)


def update_config(config: dict, updates: dict) -> dict:
    """Deep-merge updates into config and save."""
    merged = _deep_merge(config, updates)
    save_config(merged)
    return merged


def ensure_config_file() -> dict:
    """Load existing config or create default."""
    if not CONFIG_PATH.exists():
        default = get_default_config()
        save_config(default)
        logger.info("Created default config at %s", CONFIG_PATH)
        return default
    return load_config()
