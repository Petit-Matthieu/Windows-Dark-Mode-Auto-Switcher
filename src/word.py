r"""Microsoft Word/Office theme switching via Windows Registry.

Controls the Office UI theme through multiple registry paths for broad
compatibility with Office 2016, 2019, 2021, and Microsoft 365.

Primary key:
  HKEY_CURRENT_USER\SOFTWARE\Microsoft\Office\16.0\Common

Per-app keys (needed by some Office versions):
  HKEY_CURRENT_USER\SOFTWARE\Microsoft\Office\16.0\Word
  HKEY_CURRENT_USER\SOFTWARE\Microsoft\Office\16.0\Excel
  ...

Theme values (DWORD "UI Theme"):
  0 = Colorful (浅色)
  3 = Dark Gray
  4 = Black (深色/黑色)
  5 = White

Also writes "SharedTheme" to force shared theme across Office apps.
"""

import logging
import winreg

logger = logging.getLogger(__name__)

# ── 注册表路径 ──
OFFICE_BASE = r"SOFTWARE\Microsoft\Office"
OFFICE_COMMON_PATH = r"SOFTWARE\Microsoft\Office\16.0\Common"
THEME_VALUE_NAME = "UI Theme"
SHARED_THEME_NAME = "SharedTheme"

# 需要同步设置主题的 Office 应用列表
OFFICE_APPS = ["Word", "Excel", "PowerPoint", "Outlook", "Access", "Publisher"]

# 主题值映射
THEME_LIGHT = 0      # Colorful / 浅色
THEME_DARK = 4       # Black / 深色（黑色主题）


def _detect_office_versions() -> list[str]:
    """Detect installed Office versions by enumerating registry keys.

    Returns:
        List of version strings like ["16.0", "15.0"].
    """
    versions = []
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            OFFICE_BASE,
            0,
            winreg.KEY_READ,
        )
        i = 0
        while True:
            try:
                subkey_name = winreg.EnumKey(key, i)
                # Office versions look like "16.0", "15.0", etc.
                if subkey_name.endswith(".0") and subkey_name[0].isdigit():
                    versions.append(subkey_name)
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)
    except FileNotFoundError:
        pass
    return sorted(versions, reverse=True)  # newest first


def is_installed() -> bool:
    """Check if Microsoft Office is installed (any version)."""
    versions = _detect_office_versions()
    return len(versions) > 0


def get_current_theme() -> str | None:
    """Read the current Office UI theme value.

    Returns:
        Theme name string or None if unavailable.
    """
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            OFFICE_COMMON_PATH,
            0,
            winreg.KEY_READ,
        )
        value, _ = winreg.QueryValueEx(key, THEME_VALUE_NAME)
        winreg.CloseKey(key)

        if value == THEME_DARK:
            return "深色"
        elif value == THEME_LIGHT:
            return "浅色"
        else:
            return f"其他({value})"
    except FileNotFoundError:
        return None
    except OSError as e:
        logger.debug("Cannot read Word theme: %s", e)
        return None


def _write_theme_value(reg_path: str, value_name: str, value: int) -> bool:
    """Write a DWORD theme value to a registry path.

    Returns:
        True on success, False on failure.
    """
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            reg_path,
            0,
            winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key, value_name, 0, winreg.REG_DWORD, value)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False
    except OSError as e:
        logger.debug("Failed to write %s\\%s = %d: %s", reg_path, value_name, value, e)
        return False


def _broadcast_theme_change() -> None:
    """Broadcast WM_SETTINGCHANGE to notify Office apps of theme change.

    Uses ctypes to send the message without importing dark_mode module
    (avoids circular dependency).
    """
    try:
        import ctypes
        from ctypes import wintypes

        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002

        SendMessageTimeoutW = ctypes.windll.user32.SendMessageTimeoutW
        SendMessageTimeoutW.argtypes = [
            wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
            wintypes.LPVOID, wintypes.UINT, wintypes.UINT,
            ctypes.POINTER(wintypes.DWORD),
        ]
        SendMessageTimeoutW.restype = wintypes.LPARAM

        result = wintypes.DWORD()
        SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0,
            "ImmersiveColorSet", SMTO_ABORTIFHUNG, 5000,
            ctypes.byref(result),
        )
        logger.debug("Broadcast WM_SETTINGCHANGE for Office theme")
    except Exception as e:
        logger.debug("Failed to broadcast theme change: %s", e)


def _restart_office_apps() -> None:
    """Restart running Office apps so they pick up the new theme.

    Office only reads its UI theme from registry at startup. Changing the
    registry while Office is running has no effect until the process is
    restarted.
    """
    import subprocess
    import time

    office_exes = ["WINWORD.EXE", "EXCEL.EXE", "POWERPNT.EXE", "OUTLOOK.EXE", "MSACCESS.EXE"]

    for exe in office_exes:
        try:
            # Check if process is running
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {exe}"],
                capture_output=True, text=True, timeout=5,
            )
            if exe.lower() not in result.stdout.lower():
                continue

            logger.info("Office app %s is running, terminating for theme change", exe)

            # Graceful close (taskkill without /F sends WM_CLOSE)
            subprocess.run(
                ["taskkill", "/IM", exe],
                capture_output=True, timeout=10,
            )

            # Wait for graceful exit
            time.sleep(3)

            # Check if still running, force kill if needed
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {exe}"],
                capture_output=True, text=True, timeout=5,
            )
            if exe.lower() in result.stdout.lower():
                subprocess.run(
                    ["taskkill", "/IM", exe, "/F"],
                    capture_output=True, timeout=5,
                )
                logger.info("Force-killed %s", exe)
            else:
                logger.info("Gracefully closed %s", exe)

        except Exception as e:
            logger.debug("Error restarting %s: %s", exe, e)


def set_theme(dark: bool, dark_theme: str = "深色",
              light_theme: str = "浅色") -> bool:
    """Switch Word/Office UI theme via registry.

    Writes the theme value to multiple registry locations for maximum
    compatibility across Office 2016/2019/2021/365:

    1. Office Common key (primary)
    2. Per-app keys (Word, Excel, PowerPoint, etc.)
    3. Restarts running Office apps so they pick up the new theme.

    Args:
        dark: True for dark theme, False for light theme.
        dark_theme: Dark theme name (for logging, not used in registry).
        light_theme: Light theme name (for logging, not used in registry).

    Returns:
        True if at least one registry key was written successfully.
    """
    target_value = THEME_DARK if dark else THEME_LIGHT
    theme_name = dark_theme if dark else light_theme

    # Detect installed Office versions
    versions = _detect_office_versions()
    if not versions:
        logger.debug("Microsoft Office not installed, skipping")
        return False

    success_count = 0

    for version in versions:
        common_path = rf"SOFTWARE\Microsoft\Office\{version}\Common"

        # 1. Write to Common key (primary)
        # Check if already set
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                common_path,
                0,
                winreg.KEY_READ,
            )
            current, _ = winreg.QueryValueEx(key, THEME_VALUE_NAME)
            winreg.CloseKey(key)
            if current == target_value:
                logger.debug("Office %s theme already set to %s", version, theme_name)
                success_count += 1
                # Still write to per-app keys in case they're out of sync
        except (FileNotFoundError, OSError):
            pass

        if _write_theme_value(common_path, THEME_VALUE_NAME, target_value):
            success_count += 1
            logger.info("Office %s Common theme set to %s (value=%d)",
                        version, theme_name, target_value)

        # 2. Write SharedTheme to ensure all Office apps share the same theme
        _write_theme_value(common_path, SHARED_THEME_NAME, target_value)

        # 3. Write to per-app keys (needed by some Office builds)
        for app in OFFICE_APPS:
            app_path = rf"SOFTWARE\Microsoft\Office\{version}\{app}"
            # Try to write (will silently fail if app not installed)
            if _write_theme_value(app_path, THEME_VALUE_NAME, target_value):
                logger.debug("Office %s\\%s theme set to %s",
                             version, app, theme_name)

    if success_count > 0:
        # 4. Restart running Office apps so they pick up the new theme
        _restart_office_apps()
        return True
    else:
        logger.warning("Failed to set Office theme for any version")
        return False
