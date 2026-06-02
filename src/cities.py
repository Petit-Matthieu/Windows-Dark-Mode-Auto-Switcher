"""City database with coordinates and timezones for sunrise/sunset calculation.

仅保留主要大城市，精简列表便于选择。
"""

# 格式: { "显示名": {"lat": 纬度, "lon": 经度, "timezone": 时区} }

CITIES = {
    # ── 直辖市 ──
    "北京": {"lat": 39.9042, "lon": 116.4074, "timezone": "Asia/Shanghai"},
    "上海": {"lat": 31.2304, "lon": 121.4737, "timezone": "Asia/Shanghai"},
    "天津": {"lat": 39.3434, "lon": 117.3616, "timezone": "Asia/Shanghai"},
    "重庆": {"lat": 29.5630, "lon": 106.5516, "timezone": "Asia/Shanghai"},

    # ── 省会 / 主要城市 ──
    "石家庄": {"lat": 38.0428, "lon": 114.5149, "timezone": "Asia/Shanghai"},
    "太原": {"lat": 37.8706, "lon": 112.5489, "timezone": "Asia/Shanghai"},
    "呼和浩特": {"lat": 40.8424, "lon": 111.7500, "timezone": "Asia/Shanghai"},
    "沈阳": {"lat": 41.8057, "lon": 123.4315, "timezone": "Asia/Shanghai"},
    "大连": {"lat": 38.9140, "lon": 121.6147, "timezone": "Asia/Shanghai"},
    "长春": {"lat": 43.8171, "lon": 125.3235, "timezone": "Asia/Shanghai"},
    "哈尔滨": {"lat": 45.8038, "lon": 126.5350, "timezone": "Asia/Shanghai"},
    "南京": {"lat": 32.0603, "lon": 118.7969, "timezone": "Asia/Shanghai"},
    "杭州": {"lat": 30.2741, "lon": 120.1551, "timezone": "Asia/Shanghai"},
    "合肥": {"lat": 31.8206, "lon": 117.2272, "timezone": "Asia/Shanghai"},
    "福州": {"lat": 26.0745, "lon": 119.2965, "timezone": "Asia/Shanghai"},
    "厦门": {"lat": 24.4798, "lon": 118.0894, "timezone": "Asia/Shanghai"},
    "济南": {"lat": 36.6512, "lon": 117.1201, "timezone": "Asia/Shanghai"},
    "青岛": {"lat": 36.0671, "lon": 120.3826, "timezone": "Asia/Shanghai"},
    "郑州": {"lat": 34.7466, "lon": 113.6254, "timezone": "Asia/Shanghai"},
    "武汉": {"lat": 30.5928, "lon": 114.3055, "timezone": "Asia/Shanghai"},
    "长沙": {"lat": 28.2282, "lon": 112.9388, "timezone": "Asia/Shanghai"},
    "广州": {"lat": 23.1291, "lon": 113.2644, "timezone": "Asia/Shanghai"},
    "深圳": {"lat": 22.5431, "lon": 114.0579, "timezone": "Asia/Shanghai"},
    "南宁": {"lat": 22.8170, "lon": 108.3665, "timezone": "Asia/Shanghai"},
    "成都": {"lat": 30.5728, "lon": 104.0668, "timezone": "Asia/Shanghai"},
    "贵阳": {"lat": 26.6470, "lon": 106.6302, "timezone": "Asia/Shanghai"},
    "昆明": {"lat": 25.0389, "lon": 102.7183, "timezone": "Asia/Shanghai"},
    "拉萨": {"lat": 29.6500, "lon": 91.1000, "timezone": "Asia/Shanghai"},
    "西安": {"lat": 34.3416, "lon": 108.9398, "timezone": "Asia/Shanghai"},
    "兰州": {"lat": 36.0611, "lon": 103.8343, "timezone": "Asia/Shanghai"},
    "乌鲁木齐": {"lat": 43.8256, "lon": 87.6168, "timezone": "Asia/Urumqi"},

    # ── 港澳台 ──
    "香港": {"lat": 22.3193, "lon": 114.1694, "timezone": "Asia/Hong_Kong"},
    "台北": {"lat": 25.0330, "lon": 121.5654, "timezone": "Asia/Taipei"},

    # ── 国际主要城市 ──
    "东京": {"lat": 35.6762, "lon": 139.6503, "timezone": "Asia/Tokyo"},
    "首尔": {"lat": 37.5665, "lon": 126.9780, "timezone": "Asia/Seoul"},
    "新加坡": {"lat": 1.3521, "lon": 103.8198, "timezone": "Asia/Singapore"},
    "伦敦": {"lat": 51.5074, "lon": -0.1278, "timezone": "Europe/London"},
    "纽约": {"lat": 40.7128, "lon": -74.0060, "timezone": "America/New_York"},
    "悉尼": {"lat": -33.8688, "lon": 151.2093, "timezone": "Australia/Sydney"},
}


def get_city_names():
    """返回所有城市名称列表，按拼音排序。"""
    return sorted(CITIES.keys())


def get_city_info(name):
    """根据城市名返回坐标信息，找不到返回 None。"""
    return CITIES.get(name)
