"""System tray icon management."""

import logging
from typing import Callable

import pystray
from pystray import Menu, MenuItem

from .icons import create_sun_icon, create_moon_icon

logger = logging.getLogger(__name__)


class TrayManager:
    """Manages the system tray icon and its menu."""

    def __init__(
        self,
        on_show_window: Callable[[], None],
        on_toggle: Callable[[], None],
        on_exit: Callable[[], None],
    ):
        self._show_cb = on_show_window
        self._toggle_cb = on_toggle
        self._exit_cb = on_exit
        self._icon: pystray.Icon | None = None
        self._is_dark: bool = True

        self._icon_sun = create_sun_icon()
        self._icon_moon = create_moon_icon()

    def create_icon(self) -> pystray.Icon:
        """Create the tray icon with menu."""
        menu = Menu(
            MenuItem("显示窗口", self._show_window_action, default=True),
            MenuItem("切换模式", self._toggle_action),
            Menu.SEPARATOR,
            MenuItem("退出", self._exit_action),
        )

        self._icon = pystray.Icon(
            name="DarkModeSwitcher",
            icon=self._icon_moon,
            title="Dark Mode Auto Switcher - 深色模式",
            menu=menu,
        )
        return self._icon

    def _show_window_action(self, icon=None, item=None):
        self._show_cb()

    def _toggle_action(self, icon=None, item=None):
        self._toggle_cb()

    def _exit_action(self, icon=None, item=None):
        self._exit_cb()

    def update_icon(self, is_dark: bool) -> None:
        """Update the tray icon to reflect current mode."""
        self._is_dark = is_dark
        if self._icon:
            self._icon.icon = self._icon_moon if is_dark else self._icon_sun
            mode = "深色模式" if is_dark else "浅色模式"
            self._icon.title = f"Dark Mode Auto Switcher - {mode}"

    def show_notification(self, title: str, message: str) -> None:
        """Show a Windows notification."""
        if self._icon:
            try:
                self._icon.notify(message)
            except Exception:
                logger.debug("Notification failed", exc_info=True)

    def run(self) -> None:
        """Run the tray icon (blocks main thread)."""
        if self._icon:
            self._icon.run()

    def stop(self) -> None:
        """Stop the tray icon."""
        if self._icon:
            self._icon.stop()
