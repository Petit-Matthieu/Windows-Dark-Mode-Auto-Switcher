"""Core scheduler: calculates sun times and triggers mode switches."""

import logging
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import dark_mode, vscode, browser, word, netease
from .sunrise import SunTimes, get_today_sun_times, get_tomorrow_sun_times
from .geolocation import detect_location_with_fallback, GeoResult
from .power_monitor import PowerMonitor

logger = logging.getLogger(__name__)


class DarkModeScheduler:
    """Background scheduler that switches dark/light mode at sunrise/sunset.

    Switch triggers (event-driven, no polling):
    - Startup: apply correct mode immediately
    - Scheduled time: sleep until sunrise/sunset, then switch
    - Power resume: WM_POWERBROADCAST → recalculate
    - Display on: GUID_MONITOR_POWER_ON → recalculate
    - Session unlock: WTS_SESSION_UNLOCK → recalculate

    Manual toggle sets a flag so the scheduler won't override until
    the next scheduled switch time.
    """

    def __init__(self, config, on_state_change=None, on_recalculate=None):
        self.config = config
        self.on_state_change = on_state_change
        self.on_recalculate = on_recalculate  # Called after any recalculation

        self._running = False
        self._thread = None
        self._stop_event = threading.Event()
        self._recalc_event = threading.Event()

        self._power_monitor = PowerMonitor(on_resume=self._on_power_resume)

        self._sun_times = None
        self._geo = None
        self._next_switch_time = None
        self._next_switch_is_dark = None
        self._is_dark = None

        # Set when user manually toggles; cleared at next scheduled switch
        self._manual_override = False

    @property
    def is_dark(self):
        return self._is_dark

    @property
    def sun_times(self):
        return self._sun_times

    @property
    def next_switch_time(self):
        return self._next_switch_time

    @property
    def next_switch_is_dark(self):
        return self._next_switch_is_dark

    @property
    def geo(self):
        return self._geo

    def start(self):
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._recalc_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._power_monitor.start()
        logger.info("Scheduler started")

    def stop(self):
        self._running = False
        self._stop_event.set()
        self._recalc_event.set()
        self._power_monitor.stop()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("Scheduler stopped")

    def recalculate(self):
        """Signal the scheduler to recalculate (e.g., after config change)."""
        self._recalc_event.set()

    def recalculate_now(self):
        """Recalculate synchronously in the current thread. Returns new sun times.

        Use this when you need the result immediately (e.g., GUI city change).
        """
        self._refresh_sun_times()
        self._apply_current_mode()
        return self._sun_times

    def set_manual_override(self):
        """Called when user manually toggles mode.

        Prevents the scheduler from overriding the manual choice until
        the next scheduled switch time.
        """
        self._manual_override = True
        logger.info("Manual override set; scheduler will not switch "
                    "until next scheduled time")

    def _on_power_resume(self):
        """Called when the system resumes from sleep/hibernate/display-on."""
        logger.info("Power event detected, triggering recalculation")
        self._recalc_event.set()

    def _notify_recalculate(self):
        """Notify GUI that recalculation is complete."""
        if self.on_recalculate:
            try:
                self.on_recalculate()
            except Exception:
                logger.exception("Recalculate callback failed")

    def get_status(self):
        return {
            "is_dark": self._is_dark,
            "sunrise": self._sun_times.sunrise if self._sun_times else None,
            "sunset": self._sun_times.sunset if self._sun_times else None,
            "next_switch_time": self._next_switch_time,
            "next_switch_is_dark": self._next_switch_is_dark,
            "city": self._geo.city if self._geo else None,
        }

    def _run_loop(self):
        try:
            self._setup()
        except Exception:
            logger.exception("Scheduler setup failed")
            self._running = False
            return

        while self._running:
            try:
                self._wait_for_next_switch()
            except Exception:
                logger.exception("Scheduler iteration failed")
                self._stop_event.wait(60)

    def _setup(self):
        logger.info("Detecting location...")
        self._geo = detect_location_with_fallback(self.config)

        from . import config as cfg
        self.config = cfg.update_config(self.config, {
            "location": {
                "latitude": self._geo.latitude,
                "longitude": self._geo.longitude,
                "timezone": self._geo.timezone,
                "city": self._geo.city,
                "auto_detect": self.config.get("location", {}).get("auto_detect", True),
                "location_mode": self.config.get("location", {}).get("location_mode", "auto"),
            }
        })

        logger.info("Location: %s (%.4f, %.4f, %s)",
                     self._geo.city, self._geo.latitude,
                     self._geo.longitude, self._geo.timezone)

        self._refresh_sun_times()
        self._apply_current_mode()

    def _refresh_sun_times(self):
        if not self._geo:
            return

        # Sync _geo from config (user may have changed city in GUI)
        loc = self.config.get("location", {})
        lat = loc.get("latitude")
        lon = loc.get("longitude")
        tz = loc.get("timezone")
        city = loc.get("city")
        if lat is not None and lon is not None and tz:
            if (lat != self._geo.latitude or lon != self._geo.longitude
                    or tz != self._geo.timezone):
                self._geo = GeoResult(
                    latitude=lat, longitude=lon, timezone=tz,
                    city=city or self._geo.city,
                )
                logger.info("Location updated from config: %s", self._geo.city)

        self._sun_times = get_today_sun_times(
            self._geo.latitude, self._geo.longitude, self._geo.timezone
        )
        logger.info("Sun times - Sunrise: %s, Sunset: %s",
                     self._sun_times.sunrise.strftime("%H:%M"),
                     self._sun_times.sunset.strftime("%H:%M"))

    def _get_offset(self, key):
        minutes = self.config.get("offsets", {}).get(key, 0)
        return timedelta(minutes=minutes)

    def _apply_current_mode(self):
        if not self._sun_times:
            return
        now = datetime.now(ZoneInfo(self._geo.timezone))
        sunrise = self._sun_times.sunrise + self._get_offset("sunrise_offset_minutes")
        sunset = self._sun_times.sunset + self._get_offset("sunset_offset_minutes")
        should_be_dark = now < sunrise or now >= sunset
        self._apply_mode(should_be_dark)

    def _apply_mode(self, is_dark):
        if self._is_dark == is_dark:
            return

        self._is_dark = is_dark
        self._manual_override = False  # scheduled switch clears override
        mode_str = "dark" if is_dark else "light"
        logger.info("Switching to %s mode", mode_str)

        if self.config.get("features", {}).get("switch_system_theme", True):
            try:
                dark_mode.set_dark_mode(is_dark)
            except Exception:
                logger.exception("Failed to set system dark mode")

        if self.config.get("features", {}).get("switch_vscode", True):
            try:
                themes = self.config.get("themes", {})
                vscode.set_theme(
                    is_dark,
                    dark_theme=themes.get("vscode_dark", "Default Dark Modern"),
                    light_theme=themes.get("vscode_light", "Default Light Modern"),
                )
            except Exception:
                logger.exception("Failed to set VS Code theme")

        if self.config.get("features", {}).get("switch_edge_dark_reader", True):
            try:
                browser.setup_edge_integration()
            except Exception:
                logger.exception("Failed to configure Edge")

        if self.config.get("features", {}).get("switch_word", True):
            try:
                themes = self.config.get("themes", {})
                word.set_theme(
                    is_dark,
                    dark_theme=themes.get("word_dark", "深色"),
                    light_theme=themes.get("word_light", "浅色"),
                )
            except Exception:
                logger.exception("Failed to set Word theme")

        if self.config.get("features", {}).get("switch_wyy", True):
            # 只在网易云正在运行时才切换，不主动启动它
            if netease._is_app_running():
                try:
                    themes = self.config.get("themes", {})
                    netease.set_theme(
                        is_dark,
                        dark_theme=themes.get("wyy_dark", "深色模式"),
                        light_theme=themes.get("wyy_light", "浅色模式"),
                    )
                except Exception:
                    logger.exception("Failed to set NetEase Cloud Music theme")

        if self.on_state_change:
            try:
                self.on_state_change(is_dark)
            except Exception:
                logger.exception("State change callback failed")

    def _wait_for_next_switch(self):
        """Sleep until the next switch time. Woken by events (power, recalc).

        No polling — a single wait() until the target time. Power events
        and config changes set _recalc_event which wakes the wait() early.
        """
        if not self._sun_times or not self._geo:
            self._stop_event.wait(60)
            return

        tz = ZoneInfo(self._geo.timezone)
        now = datetime.now(tz)
        sunrise = self._sun_times.sunrise + self._get_offset("sunrise_offset_minutes")
        sunset = self._sun_times.sunset + self._get_offset("sunset_offset_minutes")

        if now < sunrise:
            next_time = sunrise
            next_is_dark = False
        elif now < sunset:
            next_time = sunset
            next_is_dark = True
        else:
            tomorrow = get_tomorrow_sun_times(
                self._geo.latitude, self._geo.longitude, self._geo.timezone
            )
            next_time = tomorrow.sunrise + self._get_offset("sunrise_offset_minutes")
            next_is_dark = False

        self._next_switch_time = next_time
        self._next_switch_is_dark = next_is_dark
        logger.info("Next switch: %s at %s",
                     "dark" if next_is_dark else "light",
                     next_time.strftime("%Y-%m-%d %H:%M"))

        # Single wait until switch time — woken early by power/recalc events
        seconds_until = max(1, (next_time - now).total_seconds())
        self._stop_event.wait(timeout=seconds_until)

        if not self._running:
            return

        # Woke up — check why
        if self._recalc_event.is_set():
            self._recalc_event.clear()

            if self._manual_override:
                # User manually toggled; just re-schedule, don't switch
                logger.info("Manual override active; re-scheduling")
                self._refresh_sun_times()
                self._notify_recalculate()
                return

            # Power event or config change: recalculate and apply
            self._refresh_sun_times()
            self._notify_recalculate()  # Notify GUI first (sun times changed)
            self._apply_current_mode()
            return

        # Timer expired — it's switch time
        if self._manual_override:
            # Clear override at scheduled switch time and apply
            self._manual_override = False

        if self._next_switch_is_dark is not None:
            self._apply_mode(self._next_switch_is_dark)

        # Refresh sun times at midnight
        if now.hour == 0 and now.minute < 5:
            self._refresh_sun_times()

        self._notify_recalculate()
