"""Windows dark mode control via registry and WM_SETTINGCHANGE broadcast."""

import ctypes
import logging
import winreg

logger = logging.getLogger(__name__)

REG_PATH = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"
HWND_BROADCAST = 0xFFFF
WM_SETTINGCHANGE = 0x001A
SMTO_ABORTIFHUNG = 0x0002


def is_dark_mode() -> bool:
    """Check if Windows dark mode is enabled. Returns True if dark."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
        apps_value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        try:
            sys_value, _ = winreg.QueryValueEx(key, "SystemUsesLightTheme")
        except FileNotFoundError:
            sys_value = apps_value
        winreg.CloseKey(key)
        # If they disagree, treat as dark only if BOTH are 0
        return apps_value == 0 and sys_value == 0
    except FileNotFoundError:
        logger.warning("Theme registry key not found, assuming dark mode")
        return True
    except OSError as e:
        logger.error("Failed to read theme registry: %s", e)
        return True


def set_system_theme(dark: bool) -> None:
    """Set the system (taskbar, Start menu) theme."""
    value = 0 if dark else 1
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, value)
        winreg.CloseKey(key)
        logger.info("System theme set to %s", "dark" if dark else "light")
    except OSError as e:
        logger.error("Failed to set system theme: %s", e)
        raise


def set_apps_theme(dark: bool) -> None:
    """Set the apps (Explorer, Settings, etc.) theme."""
    value = 0 if dark else 1
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, value)
        winreg.CloseKey(key)
        logger.info("Apps theme set to %s", "dark" if dark else "light")
    except OSError as e:
        logger.error("Failed to set apps theme: %s", e)
        raise


def broadcast_theme_change() -> None:
    """Broadcast WM_SETTINGCHANGE so running apps refresh their theme."""
    result = ctypes.c_long(0)
    ctypes.windll.user32.SendMessageTimeoutW(
        HWND_BROADCAST,
        WM_SETTINGCHANGE,
        0,
        "ImmersiveColorSet",
        SMTO_ABORTIFHUNG,
        5000,
        ctypes.byref(result),
    )
    logger.debug("WM_SETTINGCHANGE broadcast sent")


def set_dark_mode(enable: bool) -> None:
    """Set both system and apps dark mode atomically, then broadcast."""
    value = 0 if enable else 1
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, value)
        winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, value)
        winreg.CloseKey(key)
    except OSError as e:
        logger.error("Failed to set theme: %s", e)
        raise
    # Broadcast twice: once immediately, once after a short delay
    # This ensures all components (taskbar, Start menu, apps) refresh
    broadcast_theme_change()
    logger.info("Dark mode %s", "enabled" if enable else "disabled")


def toggle_dark_mode() -> bool:
    """Toggle dark mode and return the new state (True=dark)."""
    current = is_dark_mode()
    new_state = not current
    set_dark_mode(new_state)
    return new_state
