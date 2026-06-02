"""Windows Dark Mode Auto Switcher - Main Entry Point.

Automatically switches Windows dark/light mode based on sunrise/sunset times.
Supports: Windows system theme, VS Code, Edge + Dark Reader.
"""

import logging
import os
import signal
import sys
import threading
import tkinter as tk

# Set up logging
if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(_BASE_DIR, "app.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

from src.config import ensure_config_file
from src.scheduler import DarkModeScheduler
from src.tray import TrayManager
from src.gui import DarkModeGUI


def main():
    logger.info("=" * 50)
    logger.info("Dark Mode Auto Switcher starting")

    # Load config
    config = ensure_config_file()
    logger.info("Config loaded")

    # Shared state
    gui: DarkModeGUI | None = None
    tray: TrayManager | None = None
    scheduler: DarkModeScheduler | None = None
    root: tk.Tk | None = None

    def on_state_change(is_dark: bool):
        """Called by scheduler when mode changes."""
        mode = "dark" if is_dark else "light"
        logger.info("State changed to %s mode", mode)
        if tray:
            tray.update_icon(is_dark)
            mode_cn = "深色" if is_dark else "浅色"
            tray.show_notification("模式切换", f"已切换到{mode_cn}模式")
        # Update GUI if visible (thread-safe)
        if root and gui:
            def _update():
                gui.apply_theme_for_mode(is_dark)
                gui._update_display()
                # 更新窗口图标
                try:
                    icon_path = str(_ico_moon if is_dark else _ico_sun)
                    root.iconbitmap(icon_path)
                except Exception:
                    pass
            root.after(0, _update)

    def on_config_change(new_config):
        """Called when GUI saves settings."""
        nonlocal config
        config = new_config

    def on_toggle():
        """Toggle dark mode from tray menu or GUI button."""
        from src.dark_mode import toggle_dark_mode, broadcast_theme_change
        new_state = toggle_dark_mode()
        scheduler._is_dark = new_state
        scheduler.set_manual_override()
        if tray:
            tray.update_icon(new_state)
        if root and gui:
            def _update():
                gui._apply_theme(new_state)
                gui._update_display()
                try:
                    root.iconbitmap(str(_ico_moon if new_state else _ico_sun))
                except Exception:
                    pass
                # Second broadcast after GUI update
                broadcast_theme_change()
            root.after(10, _update)
        return new_state

    def on_exit():
        """Clean shutdown."""
        logger.info("Exit requested")
        if scheduler:
            scheduler.stop()
        if tray:
            tray.stop()
        if root:
            root.after(0, root.destroy)
        # Give tkinter time to clean up, then force exit
        threading.Timer(1.0, lambda: os._exit(0)).start()

    def on_close():
        """窗口关闭按钮行为：根据配置决定最小化到托盘还是真正退出。"""
        # 直接从 GUI 控件读取最新值（用户可能改了但没保存）
        if gui and gui._var_minimize_to_tray:
            minimize = gui._var_minimize_to_tray.get()
        else:
            minimize = config.get("minimize_to_tray", True)
        if minimize:
            if root and gui:
                root.after(0, gui.hide)
        else:
            on_exit()

    def show_window():
        """Show the GUI window (called from tray)."""
        if root and gui:
            root.after(0, gui.show)

    # Create scheduler
    def on_recalculate():
        """Called by scheduler after recalculation (city change, power event, etc.)."""
        if root and gui:
            root.after(0, gui._update_display)

    scheduler = DarkModeScheduler(
        config, on_state_change=on_state_change,
        on_recalculate=on_recalculate,
    )

    # Create tray (runs in background thread)
    tray = TrayManager(
        on_show_window=show_window,
        on_toggle=on_toggle,
        on_exit=on_exit,
    )
    tray.create_icon()

    # Handle signals
    def signal_handler(sig, frame):
        logger.info("Signal %s received", sig)
        on_exit()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create tkinter root (main thread)
    root = tk.Tk()
    root.withdraw()  # Start hidden

    # 设置窗口图标（太阳/月亮，而非 Python 默认图标）
    from src.icons import get_sun_ico_path, get_moon_ico_path
    _ico_moon = get_moon_ico_path()
    _ico_sun = get_sun_ico_path()
    try:
        root.iconbitmap(str(_ico_moon))
    except Exception:
        logger.debug("Failed to set window icon", exc_info=True)

    # Create GUI
    gui = DarkModeGUI(
        scheduler, config,
        on_config_change=on_config_change,
        on_toggle=on_toggle,
        on_close=on_close,
    )
    gui.root = root

    # Start scheduler
    scheduler.start()

    # Update tray icon with initial state
    if scheduler.is_dark is not None:
        tray.update_icon(scheduler.is_dark)
        # 同步 GUI 主题
        gui.apply_theme_for_mode(scheduler.is_dark)
        # 同步窗口图标
        try:
            root.iconbitmap(str(_ico_moon if scheduler.is_dark else _ico_sun))
        except Exception:
            pass

    # 开机自启动时直接最小化到托盘，不显示 GUI
    if config.get("autostart", False) and config.get("minimize_to_tray", True):
        logger.info("Autostart mode: starting minimized to tray")
    else:
        logger.info("Showing GUI on startup")
        root.after(500, gui.show)

    # Run tray in background thread
    tray_thread = threading.Thread(target=tray.run, daemon=True)
    tray_thread.start()

    # Run tkinter mainloop on main thread (blocking)
    logger.info("Starting tkinter mainloop")
    try:
        root.mainloop()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt")
        on_exit()

    # Cleanup after mainloop exits
    on_exit()


if __name__ == "__main__":
    main()
