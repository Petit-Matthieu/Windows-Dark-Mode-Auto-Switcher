"""IP-based geolocation using ip-api.com."""

import logging
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

API_URL = "http://ip-api.com/json/?fields=status,lat,lon,timezone,city"


@dataclass
class GeoResult:
    latitude: float
    longitude: float
    timezone: str
    city: str


def detect_location(timeout: int = 10) -> GeoResult | None:
    """Detect location from public IP. Returns None on failure."""
    try:
        resp = requests.get(API_URL, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            logger.warning("ip-api returned status: %s", data.get("status"))
            return None
        return GeoResult(
            latitude=data["lat"],
            longitude=data["lon"],
            timezone=data["timezone"],
            city=data.get("city", "Unknown"),
        )
    except (requests.RequestException, KeyError, ValueError) as e:
        logger.warning("Geolocation failed: %s", e)
        return None


def detect_location_with_fallback(config: dict) -> GeoResult:
    """Detect location, falling back to cached values from config.

    如果 location_mode 为 "city" 或 auto_detect 为 False，
    直接使用 config 中缓存的坐标（由城市选择或手动输入提供）。
    """
    loc_cfg = config.get("location", {})
    location_mode = loc_cfg.get("location_mode", "auto")
    auto_detect = loc_cfg.get("auto_detect", True)

    # 城市模式或手动模式：跳过 IP 检测，直接用缓存
    if location_mode == "city" or not auto_detect:
        lat = loc_cfg.get("latitude")
        lon = loc_cfg.get("longitude")
        tz = loc_cfg.get("timezone")
        city = loc_cfg.get("city", "Unknown")
        if lat is not None and lon is not None and tz is not None:
            logger.info("Using configured location: %s (%.4f, %.4f)", city, lat, lon)
            return GeoResult(latitude=lat, longitude=lon, timezone=tz, city=city)
        # 缓存不完整，回退到 IP 检测
        logger.warning("Configured location incomplete, falling back to IP detection")

    # 自动模式：先尝试 IP 检测
    result = detect_location()
    if result:
        logger.info("Detected location: %s (%.4f, %.4f)", result.city, result.latitude, result.longitude)
        return result

    # IP 检测失败，回退到缓存
    lat = loc_cfg.get("latitude")
    lon = loc_cfg.get("longitude")
    tz = loc_cfg.get("timezone")
    city = loc_cfg.get("city", "Unknown")
    if lat is not None and lon is not None and tz is not None:
        logger.info("Using cached location: %s (%.4f, %.4f)", city, lat, lon)
        return GeoResult(latitude=lat, longitude=lon, timezone=tz, city=city)

    raise RuntimeError(
        "无法检测位置。请在设置中手动输入经纬度或选择城市。"
    )
