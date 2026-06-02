"""简化版启动脚本 - 先显示GUI，再启动后台服务"""
import sys
import os
import threading
import logging
import tkinter as tk

# 设置日志
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
from src.gui import DarkModeGUI


def main():
    logger.info("=" * 50)
    logger.info("Dark Mode Auto Switcher starting (simplified)")

    # Load config
    config = ensure_config_file()
    logger.info("Config loaded")

    # 先创建 tkinter 窗口 (主线程)
    root = tk.Tk()
    root.title("Dark Mode Auto Switcher")
    root.geometry("460x700")
    root.resizable(False, False)

    # 设置窗口图标（太阳/月亮）
    from src.icons import get_moon_ico_path
    try:
        root.iconbitmap(str(get_moon_ico_path()))
    except Exception:
        logger.debug("Failed to set window icon", exc_info=True)

    # 设置窗口在最前面，方便首次使用
    root.attributes('-topmost', True)
    root.after(2000, lambda: root.attributes('-topmost', False))

    # 创建调度器
    scheduler = DarkModeScheduler(config)

    # 创建 GUI
    gui = DarkModeGUI(scheduler, config)
    gui.root = root
    gui._setup_window()

    # 状态变化回调
    from src.icons import get_sun_ico_path, get_moon_ico_path
    _ico_sun = get_sun_ico_path()
    _ico_moon = get_moon_ico_path()

    def on_state_change(is_dark):
        logger.info("State changed: %s", "dark" if is_dark else "light")
        def _update():
            gui._update_display()
            gui.apply_theme_for_mode(is_dark)
            try:
                root.iconbitmap(str(_ico_moon if is_dark else _ico_sun))
            except Exception:
                pass
        root.after(0, _update)

    scheduler.on_state_change = on_state_change

    # 启动调度器 (后台线程)
    scheduler.start()

    # 显示窗口
    gui.show()
    logger.info("GUI shown, starting mainloop")

    # 关闭处理
    def on_closing():
        logger.info("Window closed")
        scheduler.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    # 主循环
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass

    logger.info("Application exited")


if __name__ == "__main__":
    main()
