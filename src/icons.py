"""Generate tray icons programmatically using Pillow."""

import math
import sys
from pathlib import Path
from PIL import Image, ImageDraw


def _get_base_dir():
    """获取应用根目录：exe 模式下为 exe 所在目录，开发模式下为项目根目录。"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent.parent


_ASSETS_DIR = _get_base_dir() / "assets"

# 图标颜色定义
SUN_YELLOW = "#FFCC00"       # 太阳：明亮的黄色
SUN_DARK = "#B8860B"         # 太阳描边：深金色
MOON_WHITE = "#FFFFFF"       # 月亮：纯白色
MOON_DARK = "#808080"        # 月亮描边：灰色（保证在浅色背景可见）


def _hex_to_rgb(hex_color: str) -> tuple:
    """将十六进制颜色转换为 RGB 元组。"""
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def create_sun_icon(size: int = 64) -> Image.Image:
    """Create a sun icon for light mode — 黄色太阳带深色描边。

    先画深色描边层，再画黄色填充层，保证在浅色/深色背景下都清晰可见。
    """
    cx, cy = size // 2, size // 2
    r = size // 4

    # ── 描边层（深色） ──
    outline = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    od = ImageDraw.Draw(outline)
    outline_w = 2
    # 太阳主体描边
    od.ellipse(
        [cx - r - outline_w, cy - r - outline_w, cx + r + outline_w, cy + r + outline_w],
        fill=SUN_DARK,
    )
    # 射线描边
    ray_inner = r + 3
    ray_outer = r + 11
    for i in range(8):
        angle = math.radians(i * 45)
        x1 = cx + int(ray_inner * math.cos(angle))
        y1 = cy + int(ray_inner * math.sin(angle))
        x2 = cx + int(ray_outer * math.cos(angle))
        y2 = cy + int(ray_outer * math.sin(angle))
        od.line([x1, y1, x2, y2], fill=SUN_DARK, width=5)

    # ── 填充层（黄色） ──
    fill = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fill)
    # 太阳主体
    fd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=SUN_YELLOW)
    # 射线
    for i in range(8):
        angle = math.radians(i * 45)
        x1 = cx + int(ray_inner * math.cos(angle))
        y1 = cy + int(ray_inner * math.sin(angle))
        x2 = cx + int(ray_outer * math.cos(angle))
        y2 = cy + int(ray_outer * math.sin(angle))
        fd.line([x1, y1, x2, y2], fill=SUN_YELLOW, width=3)

    # 合成：描边在下，填充在上
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(outline, (0, 0), outline)
    result.paste(fill, (0, 0), fill)
    return result


def create_moon_icon(size: int = 64) -> Image.Image:
    """Create a moon icon for dark mode — 白色月牙带灰色描边。

    使用遮罩合成实现真正的月牙形状（PIL 的透明绘制无法擦除已有像素）。
    """
    cx, cy = size // 2, size // 2
    r = size // 4

    # ── 1) 画满月（白色）──
    moon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    moon_draw = ImageDraw.Draw(moon)
    moon_draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=MOON_WHITE)

    # ── 2) 画遮罩圆（用于切割出月牙）──
    #    将遮罩圆偏移到右上方，让切割后形成经典月牙
    cutout = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cutout_draw = ImageDraw.Draw(cutout)
    offset = r * 2 // 3
    cutout_draw.ellipse(
        [cx - r + offset + 2, cy - r - 2, cx + r + offset, cy + r + 2],
        fill=(255, 255, 255, 255),
    )

    # ── 3) 用遮罩合成：在 cutout 有像素的地方擦除 moon ──
    mask = cutout.split()[3]  # 取 alpha 通道作为遮罩
    bg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    moon_crescent = Image.composite(bg, moon, mask)

    # ── 4) 描边：画一个略大的深灰色月牙，再叠上白色月牙 ──
    # 先用同样方法画一个深色的月牙作为描边
    outline_moon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    outline_draw = ImageDraw.Draw(outline_moon)
    ow = 2  # 描边宽度
    outline_draw.ellipse(
        [cx - r - ow, cy - r - ow, cx + r + ow, cy + r + ow],
        fill=MOON_DARK,
    )
    # 用同一个 cutout mask 切割描边月牙
    outline_crescent = Image.composite(bg, outline_moon, mask)

    # 合成：描边在下，白色月牙在上
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(outline_crescent, (0, 0), outline_crescent)
    result.paste(moon_crescent, (0, 0), moon_crescent)
    return result


def _ensure_assets_dir() -> Path:
    """Ensure the assets directory exists."""
    _ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    return _ASSETS_DIR


def create_sun_ico(path=None):
    """Generate and save sun .ico file for window/taskbar icon."""
    path = path or (_ensure_assets_dir() / "sun.ico")
    img = create_sun_icon(64)
    # ICO needs multiple sizes for best quality
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64)]
    img.save(str(path), format="ICO", sizes=sizes)
    return path


def create_moon_ico(path=None):
    """Generate and save moon .ico file for window/taskbar icon."""
    path = path or (_ensure_assets_dir() / "moon.ico")
    img = create_moon_icon(64)
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64)]
    img.save(str(path), format="ICO", sizes=sizes)
    return path


def get_sun_ico_path():
    """Get path to sun .ico, generating it if needed."""
    _ensure_assets_dir()
    path = _ASSETS_DIR / "sun.ico"
    if not path.exists():
        create_sun_ico(path)
    return path


def get_moon_ico_path():
    """Get path to moon .ico, generating it if needed."""
    _ensure_assets_dir()
    path = _ASSETS_DIR / "moon.ico"
    if not path.exists():
        create_moon_ico(path)
    return path


# ── 应用图标颜色 ──
WORD_BLUE = "#2B579A"          # Word 蓝色
WORD_DARK = "#1B3A6B"          # Word 描边深蓝
WYY_RED = "#E84040"            # 网易云音乐红色
WYY_DARK = "#A02020"           # 网易云音乐描边深红
VSCODE_BLUE = "#007ACC"        # VS Code 蓝色
VSCODE_DARK = "#005A99"        # VS Code 描边深蓝
EDGE_BLUE = "#0078D4"          # Edge 蓝色
EDGE_DARK = "#005A9E"          # Edge 描边深蓝


def create_word_icon(size: int = 64) -> Image.Image:
    """Create a Word icon — 蓝色 'W' 字母。

    双层绘制：深色描边 + 蓝色填充。
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = size // 2, size // 2
    margin = size // 6

    # ── 描边层 ──
    outline = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    od = ImageDraw.Draw(outline)
    ow = 2
    # W 形状：4 条线段
    points_outline = [
        (margin, margin - ow),
        (margin + size // 6, size - margin + ow),
        (cx, margin + size // 5),
        (cx + size // 6 - 1, size - margin + ow),
        (size - margin, margin - ow),
    ]
    od.line(points_outline, fill=WORD_DARK, width=max(4, size // 8))

    # ── 填充层 ──
    fill = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fill)
    points_fill = [
        (margin, margin),
        (margin + size // 6, size - margin),
        (cx, margin + size // 5),
        (cx + size // 6 - 1, size - margin),
        (size - margin, margin),
    ]
    fd.line(points_fill, fill=WORD_BLUE, width=max(3, size // 10))

    # 合成
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(outline, (0, 0), outline)
    result.paste(fill, (0, 0), fill)
    return result


def create_wyy_icon(size: int = 64) -> Image.Image:
    """Create a NetEase Cloud Music icon — 红色音符。

    双层绘制：深色描边 + 红色填充。
    """
    cx, cy = size // 2, size // 2

    # ── 描边层 ──
    outline = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    od = ImageDraw.Draw(outline)
    ow = 2
    # 音符：竖线 + 圆形底部
    note_x = cx - size // 8
    note_top = size // 5 - ow
    note_bottom = cy + size // 6
    r = size // 7
    # 竖线描边
    od.line([(note_x, note_top), (note_x, note_bottom + r)], fill=WYY_DARK, width=max(4, size // 8))
    # 圆形底部描边
    od.ellipse(
        [note_x - r - ow, note_bottom - r - ow, note_x + r + ow, note_bottom + r + ow],
        fill=WYY_DARK,
    )
    # 横线（旗子）描边
    flag_x = note_x + size // 4
    od.line([(note_x, note_top), (flag_x, note_top + size // 8)], fill=WYY_DARK, width=max(4, size // 8))
    od.line([(note_x, note_top + size // 5), (flag_x, note_top + size // 5 + size // 8)], fill=WYY_DARK, width=max(4, size // 8))

    # ── 填充层 ──
    fill = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fill)
    # 竖线
    fd.line([(note_x, note_top), (note_x, note_bottom + r)], fill=WYY_RED, width=max(3, size // 10))
    # 圆形底部
    fd.ellipse(
        [note_x - r, note_bottom - r, note_x + r, note_bottom + r],
        fill=WYY_RED,
    )
    # 横线（旗子）
    fd.line([(note_x, note_top), (flag_x, note_top + size // 8)], fill=WYY_RED, width=max(3, size // 10))
    fd.line([(note_x, note_top + size // 5), (flag_x, note_top + size // 5 + size // 8)], fill=WYY_RED, width=max(3, size // 10))

    # 合成
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(outline, (0, 0), outline)
    result.paste(fill, (0, 0), fill)
    return result


def create_vscode_icon(size: int = 64) -> Image.Image:
    """Create a VS Code icon — 蓝色角度括号 '</>' 。

    双层绘制：深色描边 + 蓝色填充。
    """
    cx, cy = size // 2, size // 2

    # ── 描边层 ──
    outline = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    od = ImageDraw.Draw(outline)
    ow = 2
    m = size // 5  # 边距
    # 左括号 '<'
    od.line([(m + 4, cy), (cx - 2, m)], fill=VSCODE_DARK, width=max(4, size // 8))
    od.line([(cx - 2, m), (cx - 2, size - m)], fill=VSCODE_DARK, width=max(4, size // 8))
    # 右括号 '>'
    od.line([(cx + 2, m), (cx + 2, size - m)], fill=VSCODE_DARK, width=max(4, size // 8))
    od.line([(cx + 2, size - m), (size - m - 4, cy)], fill=VSCODE_DARK, width=max(4, size // 8))
    # 斜杠 '/'
    od.line([(size - m + 2, m + 2), (m - 2, size - m - 2)], fill=VSCODE_DARK, width=max(4, size // 8))

    # ── 填充层 ──
    fill = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fill)
    # 左括号 '<'
    fd.line([(m + 4, cy), (cx - 2, m)], fill=VSCODE_BLUE, width=max(3, size // 10))
    fd.line([(cx - 2, m), (cx - 2, size - m)], fill=VSCODE_BLUE, width=max(3, size // 10))
    # 右括号 '>'
    fd.line([(cx + 2, m), (cx + 2, size - m)], fill=VSCODE_BLUE, width=max(3, size // 10))
    fd.line([(cx + 2, size - m), (size - m - 4, cy)], fill=VSCODE_BLUE, width=max(3, size // 10))
    # 斜杠 '/'
    fd.line([(size - m + 2, m + 2), (m - 2, size - m - 2)], fill=VSCODE_BLUE, width=max(3, size // 10))

    # 合成
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(outline, (0, 0), outline)
    result.paste(fill, (0, 0), fill)
    return result


def create_edge_icon(size: int = 64) -> Image.Image:
    """Create an Edge icon — 蓝绿色波浪 'e' 。

    双层绘制：深色描边 + 蓝绿色填充。
    """
    cx, cy = size // 2, size // 2

    # ── 描边层 ──
    outline = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    od = ImageDraw.Draw(outline)
    ow = 2
    r = size // 4
    # 外圈
    od.ellipse(
        [cx - r - ow, cy - r - ow, cx + r + ow, cy + r + ow],
        fill=EDGE_DARK,
    )
    # 内部 "e" 的缺口（用背景色覆盖形成 e 形）
    od.arc(
        [cx - r + 4, cy - r + 4, cx + r - 4, cy + r - 4],
        start=30, end=330, fill=EDGE_DARK, width=max(4, size // 8),
    )

    # ── 填充层 ──
    fill = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fill)
    # 画一个渐变效果的 e 形
    fd.arc(
        [cx - r, cy - r, cx + r, cy + r],
        start=30, end=330, fill=EDGE_BLUE, width=max(3, size // 10),
    )
    # 横线
    fd.line([(cx - r, cy), (cx + r - 2, cy)], fill=EDGE_BLUE, width=max(3, size // 10))

    # 合成
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(outline, (0, 0), outline)
    result.paste(fill, (0, 0), fill)
    return result
