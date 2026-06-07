r"""Extract native application icons from installed programs.

Uses win32api to extract icons from .exe files, converting them to
PIL Images for use in the tkinter GUI.

Falls back to a simple colored placeholder if the app is not installed.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)

# ── 应用路径查找 ──

def _find_exe_from_app_paths(exe_name):
    # type: (str) -> Optional[str]
    """Find exe path from Windows App Paths registry."""
    import winreg
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            key = winreg.OpenKey(
                root,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{}".format(exe_name),
                0,
                winreg.KEY_READ,
            )
            # Default value contains the full path
            path, _ = winreg.QueryValueEx(key, "")
            winreg.CloseKey(key)
            if path and os.path.isfile(path):
                return path
        except (FileNotFoundError, OSError):
            pass
    return None


def _find_word_exe():
    # type: () -> Optional[str]
    """Find Microsoft Word executable."""
    # Method 1: App Paths
    path = _find_exe_from_app_paths("Winword.exe")
    if path:
        return path

    # Method 2: Common install locations
    for base in [
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    ]:
        candidate = os.path.join(base, r"Microsoft Office\root\Office16\WINWORD.EXE")
        if os.path.isfile(candidate):
            return candidate
        candidate = os.path.join(base, r"Microsoft Office\Office16\WINWORD.EXE")
        if os.path.isfile(candidate):
            return candidate
    return None


def _find_vscode_exe():
    # type: () -> Optional[str]
    """Find VS Code executable."""
    # Method 1: App Paths
    path = _find_exe_from_app_paths("Code.exe")
    if path:
        return path

    # Method 2: User install (per-user install)
    local_app = os.environ.get("LOCALAPPDATA", "")
    if local_app:
        candidate = os.path.join(local_app, r"Programs\Microsoft VS Code\Code.exe")
        if os.path.isfile(candidate):
            return candidate

    # Method 3: System-wide install
    for base in [
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    ]:
        candidate = os.path.join(base, r"Microsoft VS Code\Code.exe")
        if os.path.isfile(candidate):
            return candidate
    return None


def _find_edge_exe():
    # type: () -> Optional[str]
    """Find Microsoft Edge executable."""
    # Method 1: App Paths
    path = _find_exe_from_app_paths("msedge.exe")
    if path:
        return path

    # Method 2: Common locations
    for base in [
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        os.environ.get("ProgramFiles", r"C:\Program Files"),
    ]:
        candidate = os.path.join(base, r"Microsoft\Edge\Application\msedge.exe")
        if os.path.isfile(candidate):
            return candidate
    return None


# ── 图标提取 ──

def _extract_icon_from_exe(exe_path, size=24):
    # type: (str, int) -> Optional[Image.Image]
    """Extract the first icon from an exe and return as PIL Image.

    Uses the large icon (typically 32x32) for better quality, rendered at
    48x48 then LANCZOS-downscaled to the target size to avoid pixelation.

    Args:
        exe_path: Path to the executable.
        size: Desired icon size (width and height).

    Returns:
        PIL RGBA Image or None on failure.
    """
    try:
        import ctypes
        import win32gui

        # Extract icon handles (large and small)
        large_icons, small_icons = win32gui.ExtractIconEx(exe_path, 0, 1)
        if not small_icons and not large_icons:
            logger.debug("No icons found in %s", exe_path)
            return None

        # Use large icon for higher resolution (32x32 vs 16x16)
        icon_handle = large_icons[0] if large_icons else small_icons[0]

        # Render at 48x48 for oversampling, then downscale
        render_size = 48

        # Create compatible DC and bitmap
        screen_dc = win32gui.GetDC(0)
        mem_dc = win32gui.CreateCompatibleDC(screen_dc)
        bmp = win32gui.CreateCompatibleBitmap(screen_dc, render_size, render_size)
        old_bmp = win32gui.SelectObject(mem_dc, bmp)

        # Draw icon onto bitmap
        DI_NORMAL = 0x0003
        win32gui.DrawIconEx(mem_dc, 0, 0, icon_handle, render_size, render_size, 0, 0, DI_NORMAL)

        # Get bitmap bits via ctypes
        gdi32 = ctypes.windll.gdi32
        gdi32.GetBitmapBits.argtypes = [
            ctypes.c_void_p, ctypes.c_long, ctypes.c_void_p
        ]
        gdi32.GetBitmapBits.restype = ctypes.c_long

        buf_size = render_size * render_size * 4
        buf = ctypes.create_string_buffer(buf_size)
        gdi32.GetBitmapBits(int(bmp), buf_size, buf)

        # Convert to PIL Image
        img = Image.frombuffer(
            "RGBA", (render_size, render_size), buf.raw, "raw", "BGRA", 0, 1
        ).copy()

        # Cleanup GDI resources
        win32gui.SelectObject(mem_dc, old_bmp)
        win32gui.DeleteObject(bmp)
        win32gui.DeleteDC(mem_dc)
        win32gui.ReleaseDC(0, screen_dc)
        for h in (small_icons or []):
            win32gui.DestroyIcon(h)
        for h in (large_icons or []):
            win32gui.DestroyIcon(h)

        # High-quality downscale to target size
        if render_size != size:
            img = img.resize((size, size), Image.LANCZOS)

        return img

    except Exception as e:
        logger.debug("Failed to extract icon from %s: %s", exe_path, e)
        return None


# ── 公共 API ──

def get_app_icon(app_name, size=24):
    # type: (str, int) -> Optional[Image.Image]
    """Get the native icon for a supported application.

    Args:
        app_name: One of "word", "vscode", "edge".
        size: Desired icon size in pixels.

    Returns:
        PIL RGBA Image or None if not found.
    """
    finders = {
        "word": _find_word_exe,
        "vscode": _find_vscode_exe,
        "edge": _find_edge_exe,
    }

    finder = finders.get(app_name)
    if not finder:
        logger.warning("Unknown app: %s", app_name)
        return None

    exe_path = finder()
    if not exe_path:
        logger.debug("App '%s' executable not found", app_name)
        return None

    logger.debug("Found %s at %s", app_name, exe_path)
    return _extract_icon_from_exe(exe_path, size)


def get_app_icon_with_fallback(app_name, size=24, fallback_color="#808080"):
    # type: (str, int, str) -> Image.Image
    """Get the native icon, falling back to a simple colored circle.

    Args:
        app_name: One of "word", "vscode", "edge".
        size: Desired icon size in pixels.
        fallback_color: Color for the fallback circle.

    Returns:
        PIL RGBA Image (never None).
    """
    icon = get_app_icon(app_name, size)
    if icon is not None:
        return icon

    # Fallback: simple colored circle
    from PIL import ImageDraw
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = max(1, size // 8)
    draw.ellipse([margin, margin, size - margin, size - margin], fill=fallback_color)
    return img
