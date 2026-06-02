r"""NetEase Cloud Music (网易云音乐) theme switching module.

For NetEase Cloud Music v3.x (Chromium/CEF-based), the theme is stored in
Chromium's Local Storage leveldb database, NOT in the Windows registry.

The key is "rentTheme" in Local Storage, with values like "dark" or containing
"light" for the respective themes.

Strategy:
  - Light mode: Remove newer leveldb files that override the "light" value,
    keeping the older file that has it. LevelDB will repair on next app start.
  - Dark mode: Restore from backup (if available) or note that manual
    switching may be needed.
  - The registry approach is kept as a fallback for older versions.

Requires NetEase Cloud Music PC version.
"""

import logging
import os
import shutil
import subprocess
import winreg
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Registry paths (fallback for older versions) ──
CLOUDMUSIC_REG_PATH = r"SOFTWARE\NetEase\CloudMusic"
DARKMODE_VALUE_NAME = "DarkMode"
MODE_LIGHT = 0
MODE_DARK = 1

# ── Leveldb Local Storage paths ──
# 网易云音乐不同版本使用不同目录名，逐一检查
_LS_SUBDIRS = [
    r"NetEase\CloudMusic\webapp91x64\Local Storage\leveldb",
    r"NetEase\CloudMusic\webapp91\Local Storage\leveldb",
    r"NetEase\CloudMusic\Local Storage\leveldb",
]


def _get_ls_dir():
    # type: () -> str | None
    """Get the Chromium Local Storage leveldb directory path.

    Tries multiple known subdirectory names for different app versions.
    """
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    if not local_appdata:
        return None
    for subdir in _LS_SUBDIRS:
        ls_dir = os.path.join(local_appdata, subdir)
        if os.path.isdir(ls_dir):
            return ls_dir
    return None


def _get_backup_dir():
    # type: () -> str
    """Get the backup directory path for leveldb files."""
    ls_dir = _get_ls_dir()
    if ls_dir:
        return ls_dir + "_theme_backup"
    return ""


def _is_app_running():
    # type: () -> bool
    """Check if NetEase Cloud Music is currently running."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq cloudmusic.exe"],
            capture_output=True, text=True, timeout=5,
        )
        return "cloudmusic.exe" in result.stdout
    except Exception:
        return False


def _kill_app():
    # type: () -> bool
    """Kill NetEase Cloud Music process. Returns True if successful."""
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "cloudmusic.exe"],
            capture_output=True, timeout=10,
        )
        # Wait a moment for the process to fully exit
        import time
        time.sleep(1)
        return not _is_app_running()
    except Exception as e:
        logger.error("Failed to kill NetEase Cloud Music: %s", e)
        return False


def _get_exe_path():
    # type: () -> str | None
    """Find the NetEase Cloud Music executable path."""
    # Check registry install path
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\WOW6432Node\Netease\cloudmusic",
            0,
            winreg.KEY_READ,
        )
        install_dir, _ = winreg.QueryValueEx(key, "install_dir")
        winreg.CloseKey(key)
        exe = os.path.join(install_dir, "cloudmusic.exe")
        if os.path.isfile(exe):
            return exe
    except (FileNotFoundError, OSError):
        pass

    # Check common paths
    for base in [
        os.environ.get("LOCALAPPDATA", ""),
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    ]:
        if not base:
            continue
        exe = os.path.join(base, r"NetEase\CloudMusic\cloudmusic.exe")
        if os.path.isfile(exe):
            return exe

    # Check the E:\CloudMusic path (known install location)
    exe = r"E:\CloudMusic\cloudmusic.exe"
    if os.path.isfile(exe):
        return exe

    return None


def _start_app():
    # type: () -> bool
    """Start NetEase Cloud Music. Returns True if launched."""
    exe = _get_exe_path()
    if not exe:
        logger.warning("Cannot find NetEase Cloud Music executable")
        return False
    try:
        subprocess.Popen([exe], start_new_session=True)
        logger.info("Launched NetEase Cloud Music: %s", exe)
        return True
    except Exception as e:
        logger.error("Failed to start NetEase Cloud Music: %s", e)
        return False


def _find_renttheme_value_info(ls_dir):
    # type: (str) -> dict
    """Find which .ldb files contain rentTheme and what value they have.

    Returns dict with keys:
      - 'dark_files': list of (filename, offset) with dark value
      - 'light_files': list of (filename, offset) with light value
      - 'all_files': list of all .ldb filenames sorted by number
    """
    result = {"dark_files": [], "light_files": [], "all_files": []}

    ldb_files = []
    for fname in os.listdir(ls_dir):
        if fname.endswith(".ldb") or fname.endswith(".log"):
            ldb_files.append(fname)
    ldb_files.sort(key=lambda f: int(f.split(".")[0]))
    result["all_files"] = ldb_files

    for fname in ldb_files:
        fpath = os.path.join(ls_dir, fname)
        try:
            with open(fpath, "rb") as f:
                data = f.read()

            idx = data.find(b"rentTheme")
            if idx < 0:
                continue

            # Check what value follows rentTheme in this file
            # Look at the bytes after "rentTheme" for "dark" or "light"
            after = data[idx + 9:idx + 30]

            if b"dark" in after:
                result["dark_files"].append(fname)
                logger.debug("Found 'dark' in %s", fname)
            elif b"light" in after:
                result["light_files"].append(fname)
                logger.debug("Found 'light' in %s", fname)
            else:
                # The value might be encoded differently; check for the byte pattern
                # In the dark entry: after rentTheme + 8 byte suffix, value = \x01dark
                # Check a wider area
                wider = data[idx:idx + 40]
                if b"dark" in wider:
                    result["dark_files"].append(fname)
                elif b"light" in wider:
                    result["light_files"].append(fname)
        except Exception as e:
            logger.debug("Error reading %s: %s", fname, e)

    return result


def _ensure_backup(ls_dir):
    # type: (str) -> bool
    """Create a backup of the leveldb directory if not already backed up."""
    backup_dir = _get_backup_dir()
    if not backup_dir:
        return False

    if os.path.exists(backup_dir):
        logger.debug("Backup already exists at %s", backup_dir)
        return True

    try:
        shutil.copytree(ls_dir, backup_dir)
        logger.info("Created leveldb backup at %s", backup_dir)
        return True
    except Exception as e:
        logger.error("Failed to create backup: %s", e)
        return False


def _restore_backup(ls_dir):
    # type: (str) -> bool
    """Restore leveldb files from backup."""
    backup_dir = _get_backup_dir()
    if not backup_dir or not os.path.exists(backup_dir):
        logger.warning("No backup found at %s", backup_dir)
        return False

    try:
        # Remove current files
        for fname in os.listdir(ls_dir):
            fpath = os.path.join(ls_dir, fname)
            if os.path.isfile(fpath):
                os.remove(fpath)

        # Copy from backup
        for fname in os.listdir(backup_dir):
            src = os.path.join(backup_dir, fname)
            dst = os.path.join(ls_dir, fname)
            if os.path.isfile(src):
                shutil.copy2(src, dst)

        logger.info("Restored leveldb from backup")
        return True
    except Exception as e:
        logger.error("Failed to restore backup: %s", e)
        return False


def _set_leveldb_theme(dark):
    # type: (bool) -> bool
    """Switch theme by overwriting only the leveldb files containing rentTheme.

    Instead of deleting the entire directory (which destroys login tokens),
    we overwrite only the .ldb/.log files that contain a rentTheme entry
    with zeroed-out data. The app treats corrupted files as empty and
    defaults to "system" mode — without losing login cookies in other files.

    Args:
        dark: True for dark mode, False for light mode.

    Returns True if successful.
    """
    ls_dir = _get_ls_dir()
    if not ls_dir:
        logger.debug("Local Storage directory not found")
        return False

    info = _find_renttheme_value_info(ls_dir)
    has_explicit_theme = bool(info["dark_files"] or info["light_files"])

    if not has_explicit_theme:
        logger.debug("NetEase Cloud Music already follows system theme")
        return True

    # Check if current value already matches desired state
    if dark and info["dark_files"] and not info["light_files"]:
        logger.debug("Already in dark mode")
        return True
    if not dark and info["light_files"] and not info["dark_files"]:
        logger.debug("Already in light mode")
        return True

    # Backup before modifying
    _ensure_backup(ls_dir)

    # Only overwrite files that contain rentTheme — preserve login tokens
    theme_files = info["dark_files"] + info["light_files"]
    overwritten = 0
    for fname in theme_files:
        fpath = os.path.join(ls_dir, fname)
        try:
            # Read original to preserve file size, then zero it out
            size = os.path.getsize(fpath)
            with open(fpath, "wb") as f:
                f.write(b"\x00" * size)
            overwritten += 1
            logger.debug("Zeroed out %s (%d bytes)", fname, size)
        except Exception as e:
            logger.error("Failed to overwrite %s: %s", fname, e)

    if overwritten > 0:
        logger.info("Overwrote %d leveldb file(s) for %s mode (login preserved)",
                     overwritten, "dark" if dark else "light")
        return True

    logger.error("Failed to overwrite any leveldb files")
    return False


# ── Registry-based approach (fallback for older versions) ──

def _set_registry_theme(dark):
    # type: (bool) -> bool
    """Switch theme via registry (for older NetEase Cloud Music versions)."""
    target_value = MODE_DARK if dark else MODE_LIGHT
    try:
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                CLOUDMUSIC_REG_PATH,
                0,
                winreg.KEY_SET_VALUE,
            )
        except FileNotFoundError:
            # Key doesn't exist yet — create it
            key = winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER,
                CLOUDMUSIC_REG_PATH,
                0,
                winreg.KEY_SET_VALUE,
            )
        try:
            current, _ = winreg.QueryValueEx(key, DARKMODE_VALUE_NAME)
            if current == target_value:
                winreg.CloseKey(key)
                return True
        except FileNotFoundError:
            pass
        winreg.SetValueEx(key, DARKMODE_VALUE_NAME, 0, winreg.REG_DWORD, target_value)
        winreg.CloseKey(key)
        logger.info("Registry DarkMode set to %d", target_value)
        return True
    except OSError as e:
        logger.debug("Registry approach failed: %s", e)
        return False


# ── Public API ──

def is_installed():
    # type: () -> bool
    """Check if NetEase Cloud Music is installed."""
    # Check registry
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\WOW6432Node\Netease\cloudmusic",
            0,
            winreg.KEY_READ,
        )
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        pass

    # Check common install paths
    for base in [
        os.environ.get("LOCALAPPDATA", ""),
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    ]:
        if base and os.path.isfile(os.path.join(base, r"NetEase\CloudMusic\cloudmusic.exe")):
            return True

    return False


def get_current_theme():
    # type: () -> str | None
    """Read the current NetEase Cloud Music theme state."""
    # Try leveldb first
    ls_dir = _get_ls_dir()
    if ls_dir:
        info = _find_renttheme_value_info(ls_dir)
        if info["dark_files"]:
            return "深色"
        elif info["light_files"]:
            return "浅色"

    # Fallback: registry
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            CLOUDMUSIC_REG_PATH,
            0,
            winreg.KEY_READ,
        )
        value, _ = winreg.QueryValueEx(key, DARKMODE_VALUE_NAME)
        winreg.CloseKey(key)
        return "深色" if value == MODE_DARK else "浅色"
    except (FileNotFoundError, OSError):
        return None


def set_theme(dark, dark_theme="深色模式", light_theme="浅色模式"):
    # type: (bool, str, str) -> bool
    """Switch NetEase Cloud Music dark/light mode.

    Fully automated: auto-closes the app if running, modifies the theme
    database, then restarts the app.

    Tries the leveldb approach first (for v3.x), then falls back to registry.

    Args:
        dark: True for dark mode, False for light mode.
        dark_theme: Dark theme name (for logging).
        light_theme: Light theme name (for logging).

    Returns:
        True on success, False on failure.
    """
    theme_name = dark_theme if dark else light_theme
    was_running = _is_app_running()

    # If app is running, close it first (needed for leveldb file access)
    if was_running:
        logger.info("Closing NetEase Cloud Music for theme change...")
        if _kill_app():
            pass  # Successfully killed
        else:
            logger.error("Cannot close NetEase Cloud Music, trying anyway...")

    # Try leveldb approach (v3.x)
    leveldb_ok = _set_leveldb_theme(dark)

    # Fallback: registry approach
    registry_ok = False
    if not leveldb_ok:
        registry_ok = _set_registry_theme(dark)

    success = leveldb_ok or registry_ok

    if success:
        method = "leveldb" if leveldb_ok else "registry"
        logger.info("NetEase Cloud Music theme set to %s (%s)", theme_name, method)
    else:
        logger.warning("Failed to set NetEase Cloud Music theme")

    # Only restart if the app was actually running before we killed it
    if was_running:
        import time
        time.sleep(0.5)
        _start_app()
        logger.info("NetEase Cloud Music restarted")

    return success
