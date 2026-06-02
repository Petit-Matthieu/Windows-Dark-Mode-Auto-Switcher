"""Sunrise/sunset calculation using astral library."""

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from astral import Observer
from astral.sun import sun

logger = logging.getLogger(__name__)


@dataclass
class SunTimes:
    sunrise: datetime  # timezone-aware
    sunset: datetime   # timezone-aware
    target_date: date


def calculate_sun_times(
    latitude: float,
    longitude: float,
    timezone_str: str,
    target_date: date | None = None,
) -> SunTimes:
    """Calculate sunrise and sunset for given location and date."""
    if target_date is None:
        target_date = date.today()

    tz = ZoneInfo(timezone_str)
    observer = Observer(latitude=latitude, longitude=longitude)

    try:
        s = sun(observer, date=target_date, tzinfo=tz)
        return SunTimes(
            sunrise=s["sunrise"],
            sunset=s["sunset"],
            target_date=target_date,
        )
    except Exception:
        # Extreme latitude - no sunrise or sunset
        logger.warning(
            "No sunrise/sunset at (%.4f, %.4f) on %s. Using fallback.",
            latitude, longitude, target_date,
        )
        return SunTimes(
            sunrise=datetime.combine(target_date, time(6, 0), tzinfo=tz),
            sunset=datetime.combine(target_date, time(20, 0), tzinfo=tz),
            target_date=target_date,
        )


def get_today_sun_times(latitude: float, longitude: float, timezone_str: str) -> SunTimes:
    """Get today's sunrise and sunset times."""
    return calculate_sun_times(latitude, longitude, timezone_str)


def get_tomorrow_sun_times(latitude: float, longitude: float, timezone_str: str) -> SunTimes:
    """Get tomorrow's sunrise and sunset times."""
    tomorrow = date.today() + timedelta(days=1)
    return calculate_sun_times(latitude, longitude, timezone_str, tomorrow)
