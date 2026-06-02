"""Microsoft Edge dark mode control via registry policies.

Edge Chromium follows the system theme by default when the user hasn't
overridden it. This module ensures no forced policy overrides exist,
and optionally forces dark mode via registry policy.

Dark Reader extension can be configured to follow the OS theme:
  Dark Reader popup -> Automation -> "By system's dark / light mode"
"""

import logging
import winreg

logger = logging.getLogger(__name__)

EDGE_POLICY_PATH = r"SOFTWARE\Policies\Microsoft\Edge"


def is_edge_installed() -> bool:
    """Check if Microsoft Edge is installed."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Edge\Main",
            0, winreg.KEY_READ,
        )
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False


def configure_edge_follow_system() -> None:
    """Remove any forced dark/light mode policy so Edge follows the system theme."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, EDGE_POLICY_PATH, 0, winreg.KEY_SET_VALUE
        )
        # Remove ForceDarkMode if it exists
        try:
            winreg.DeleteValue(key, "ForceDarkMode")
            logger.info("Removed Edge ForceDarkMode policy")
        except FileNotFoundError:
            pass
        winreg.CloseKey(key)
    except FileNotFoundError:
        # Policy key doesn't exist, which is fine
        pass
    except OSError as e:
        logger.warning("Could not configure Edge policy: %s", e)


def enable_edge_dark_mode_registry(enable: bool) -> None:
    """Force Edge dark/light mode via registry policy.

    Note: This overrides the user's Edge appearance setting.
    Use configure_edge_follow_system() to restore default behavior.
    """
    try:
        key = winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, EDGE_POLICY_PATH, 0, winreg.KEY_SET_VALUE
        )
        if enable:
            winreg.SetValueEx(key, "ForceDarkMode", 0, winreg.REG_DWORD, 1)
            logger.info("Edge dark mode forced via registry")
        else:
            try:
                winreg.DeleteValue(key, "ForceDarkMode")
                logger.info("Edge dark mode policy removed")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except OSError as e:
        logger.error("Failed to set Edge policy: %s", e)
        raise


def setup_edge_integration() -> None:
    """One-time setup: ensure Edge follows system theme."""
    if is_edge_installed():
        configure_edge_follow_system()
        logger.info("Edge configured to follow system theme")
