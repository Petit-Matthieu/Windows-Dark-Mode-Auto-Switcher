"""Tkinter GUI window for Dark Mode Auto Switcher."""

import logging
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from zoneinfo import ZoneInfo

from . import config as cfg
from .cities import get_city_names, get_city_info
from .app_icons import get_app_icon_with_fallback

logger = logging.getLogger(__name__)

# ── 统一字体 ──
FONT_FAMILY = "Microsoft YaHei"
FONT_TITLE = (FONT_FAMILY, 16, "bold")
FONT_LABEL = (FONT_FAMILY, 10)
FONT_DATA = (FONT_FAMILY, 11)
FONT_DATA_SM = (FONT_FAMILY, 10)
FONT_SMALL = (FONT_FAMILY, 9)
FONT_GEAR = (FONT_FAMILY, 12)

# ── 窗口尺寸 ──
WIN_WIDTH = 460
WIN_HEIGHT_COLLAPSED = 280   # 折叠设置后的高度
WIN_HEIGHT_EXPANDED = 740    # 展开设置后的高度

# ── 亮色主题配色 ──
LIGHT_THEME = {
    "bg": "#f0f0f0",
    "fg": "#1a1a1a",
    "frame_bg": "#f0f0f0",
    "entry_bg": "#ffffff",
    "entry_fg": "#1a1a1a",
    "accent": "#0078d4",
    "label_fg": "#1a1a1a",
    "labelframe_fg": "#1a1a1a",
    "button_bg": "#e1e1e1",
    "button_fg": "#1a1a1a",
    "button_active": "#d0d0d0",
    "select_bg": "#0078d4",
    "select_fg": "#ffffff",
    "separator": "#c0c0c0",
}

# ── 暗色主题配色 ──
DARK_THEME = {
    "bg": "#1e1e1e",
    "fg": "#e0e0e0",
    "frame_bg": "#1e1e1e",
    "entry_bg": "#2d2d2d",
    "entry_fg": "#e0e0e0",
    "accent": "#1976D2",
    "label_fg": "#e0e0e0",
    "labelframe_fg": "#b0b0b0",
    "button_bg": "#3c3c3c",
    "button_fg": "#e0e0e0",
    "button_active": "#4a4a4a",
    "select_bg": "#1976D2",
    "select_fg": "#ffffff",
    "separator": "#3c3c3c",
}


class DarkModeGUI:
    """Main GUI window showing status, sun times, and settings."""

    def __init__(self, scheduler, config: dict, on_config_change=None, on_toggle=None, on_close=None):
        self.scheduler = scheduler
        self.config = config
        self.on_config_change = on_config_change
        self.on_toggle = on_toggle
        self._on_close_cb = on_close  # 外部传入的关闭回调（用于最小化到托盘）
        self.root = None  # type: tk.Tk
        self._update_job = None
        self._widgets_created = False
        self._is_dark_theme = False  # 当前 GUI 主题是否为暗色
        self._settings_visible = True  # 设置面板是否展开

        # Tkinter variables
        self._var_auto_detect = None
        self._var_location_mode = None  # "auto" or "city"
        self._var_selected_city = None
        self._var_lat = None
        self._var_lon = None
        self._var_sunrise_offset = None
        self._var_sunset_offset = None
        self._var_switch_vscode = None
        self._var_switch_edge = None
        self._var_switch_word = None
        self._var_switch_wyy = None
        self._var_autostart = None
        self._var_minimize_to_tray = None
        self._var_vscode_dark = None
        self._var_vscode_light = None

        # 应用图标（PIL ImageTk，需在窗口创建后初始化）
        self._app_icon_vscode = None
        self._app_icon_word = None
        self._app_icon_wyy = None
        self._app_icon_edge = None

        # Status labels
        self._lbl_status = None
        self._lbl_sunrise = None
        self._lbl_sunset = None
        self._lbl_next = None
        self._lbl_location = None

        # 用于主题切换的 widget 引用
        self._main_frame = None
        self._info_frame = None
        self._settings_frame = None
        self._separator = None
        self._city_combo = None
        self._city_frame = None
        self._loc_entries_frame = None
        self._all_frames = []

    def _setup_window(self):
        """Set up the window with widgets (called once)."""
        if self._widgets_created:
            return

        self.root.title("Dark Mode Auto Switcher")
        self.root.geometry(f"{WIN_WIDTH}x{WIN_HEIGHT_EXPANDED}")
        self.root.resizable(False, False)

        # 初始化应用图标（从 exe 提取原生图标，失败则用彩色圆圈）
        from PIL import ImageTk
        self._app_icon_vscode = ImageTk.PhotoImage(get_app_icon_with_fallback("vscode", 32, "#007ACC"))
        self._app_icon_word = ImageTk.PhotoImage(get_app_icon_with_fallback("word", 32, "#2B579A"))
        self._app_icon_wyy = ImageTk.PhotoImage(get_app_icon_with_fallback("wyy", 32, "#E84040"))
        self._app_icon_edge = ImageTk.PhotoImage(get_app_icon_with_fallback("edge", 32, "#0078D4"))

        # Style
        self._style = ttk.Style()
        self._style.theme_use("clam")

        # Main frame
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)
        self._main_frame = main

        self._create_status_frame(main)
        self._create_info_frame(main)
        self._separator = ttk.Separator(main, orient=tk.HORIZONTAL)
        self._separator.pack(fill=tk.X, pady=6)
        self._create_settings_frame(main)

        # 默认折叠设置面板
        self._settings_visible = False
        self._settings_frame.pack_forget()
        self._separator.pack_forget()
        self.root.geometry(f"{WIN_WIDTH}x{WIN_HEIGHT_COLLAPSED}")

        # Close behavior: use external callback if provided, otherwise hide
        if self._on_close_cb:
            self.root.protocol("WM_DELETE_WINDOW", self._on_close_cb)
        else:
            self.root.protocol("WM_DELETE_WINDOW", self.hide)

        # 应用当前主题（根据 scheduler 状态）
        is_dark = self.scheduler.is_dark
        if is_dark is not None:
            self._apply_theme(is_dark)

        self._widgets_created = True

    def _create_status_frame(self, parent):
        """Status section: current mode icon + label."""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=(0, 6))
        self._all_frames.append(frame)

        self._lbl_status = ttk.Label(
            frame, text="🌙 深色模式已激活",
            font=FONT_TITLE,
        )
        self._lbl_status.pack(side=tk.LEFT)

    def _create_info_frame(self, parent):
        """Info section: sun times, next switch, location."""
        frame = ttk.LabelFrame(parent, text=" 今日信息 ", padding=10)
        frame.pack(fill=tk.X, pady=(0, 8))
        self._info_frame = frame
        self._all_frames.append(frame)

        # Sunrise
        row1 = ttk.Frame(frame)
        row1.pack(fill=tk.X, pady=2)
        self._all_frames.append(row1)
        ttk.Label(row1, text="日出时间:", font=FONT_LABEL).pack(side=tk.LEFT)
        self._lbl_sunrise = ttk.Label(row1, text="--:--", font=FONT_DATA)
        self._lbl_sunrise.pack(side=tk.RIGHT)

        # Sunset
        row2 = ttk.Frame(frame)
        row2.pack(fill=tk.X, pady=2)
        self._all_frames.append(row2)
        ttk.Label(row2, text="日落时间:", font=FONT_LABEL).pack(side=tk.LEFT)
        self._lbl_sunset = ttk.Label(row2, text="--:--", font=FONT_DATA)
        self._lbl_sunset.pack(side=tk.RIGHT)

        # Next switch
        row3 = ttk.Frame(frame)
        row3.pack(fill=tk.X, pady=2)
        self._all_frames.append(row3)
        ttk.Label(row3, text="下次切换:", font=FONT_LABEL).pack(side=tk.LEFT)
        self._lbl_next = ttk.Label(row3, text="计算中...", font=FONT_DATA_SM)
        self._lbl_next.pack(side=tk.RIGHT)

        # Location
        row4 = ttk.Frame(frame)
        row4.pack(fill=tk.X, pady=2)
        self._all_frames.append(row4)
        ttk.Label(row4, text="当前位置:", font=FONT_LABEL).pack(side=tk.LEFT)
        self._lbl_location = ttk.Label(row4, text="检测中...", font=FONT_LABEL)
        self._lbl_location.pack(side=tk.RIGHT)

        # Buttons — 三按钮占满一行
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(8, 0))
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        btn_frame.columnconfigure(2, weight=1)
        self._all_frames.append(btn_frame)
        ttk.Button(
            btn_frame, text="🔄 手动切换", command=self._on_manual_toggle, width=14,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(
            btn_frame, text="💡 关于", command=self._on_about, width=14,
        ).grid(row=0, column=1, sticky="ew", padx=2)
        self._btn_gear = ttk.Button(
            btn_frame, text="⚙️ 设置",
            command=self._toggle_settings, width=14,
        )
        self._btn_gear.grid(row=0, column=2, sticky="ew", padx=(4, 0))

    def _toggle_settings(self):
        """切换设置面板的显示/隐藏。"""
        self._settings_visible = not self._settings_visible
        if self._settings_visible:
            self._separator.pack(fill=tk.X, pady=6, after=self._info_frame)
            self._settings_frame.pack(fill=tk.BOTH, expand=True)
            self.root.geometry(f"{WIN_WIDTH}x{WIN_HEIGHT_EXPANDED}")
        else:
            self._settings_frame.pack_forget()
            self._separator.pack_forget()
            self.root.geometry(f"{WIN_WIDTH}x{WIN_HEIGHT_COLLAPSED}")

    def _create_settings_frame(self, parent):
        """Settings section — 基本设置 + 应用主题两个子区域。"""
        frame = ttk.LabelFrame(parent, text=" 设置 ", padding=8)
        # 默认不 pack，由 _toggle_settings 控制
        self._settings_frame = frame
        self._all_frames.append(frame)

        # ══════════════════════════════════════════════
        # 子区域 A：基本设置（位置、偏移、启动选项）
        # ══════════════════════════════════════════════

        # ── 位置模式选择 ──
        ttk.Label(frame, text="位置获取方式:", font=FONT_LABEL).pack(anchor=tk.W, pady=(0, 2))

        mode_frame = ttk.Frame(frame)
        mode_frame.pack(fill=tk.X, pady=(0, 6))
        self._all_frames.append(mode_frame)

        self._var_location_mode = tk.StringVar(
            value=self.config.get("location", {}).get("location_mode", "auto")
        )
        ttk.Radiobutton(
            mode_frame, text="自动检测 (基于IP)",
            variable=self._var_location_mode, value="auto",
            command=self._on_location_mode_change,
        ).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Radiobutton(
            mode_frame, text="选择城市",
            variable=self._var_location_mode, value="city",
            command=self._on_location_mode_change,
        ).pack(side=tk.LEFT)

        # ── 城市选择（仅 city 模式显示） ──
        self._city_frame = ttk.Frame(frame)
        self._city_frame.pack(fill=tk.X, pady=(0, 6))
        self._all_frames.append(self._city_frame)

        ttk.Label(self._city_frame, text="城市:", font=FONT_LABEL).pack(side=tk.LEFT)
        city_names = get_city_names()
        self._var_selected_city = tk.StringVar(
            value=self.config.get("location", {}).get("city", "")
        )
        self._city_combo = ttk.Combobox(
            self._city_frame,
            textvariable=self._var_selected_city,
            values=city_names,
            state="normal",
            width=18,
            font=FONT_LABEL,
        )
        self._city_combo.pack(side=tk.LEFT, padx=(4, 0))
        # 绑定选择事件，选中后自动填入经纬度
        self._city_combo.bind("<<ComboboxSelected>>", self._on_city_selected)
        self._city_combo.bind("<KeyRelease>", self._on_city_typing)

        # 根据初始模式显示/隐藏城市选择
        if self._var_location_mode.get() == "auto":
            self._city_frame.pack_forget()

        # ── 手动经纬度（仅 auto 模式显示） ──
        self._loc_entries_frame = ttk.Frame(frame)
        self._loc_entries_frame.pack(fill=tk.X, pady=(0, 6))
        self._all_frames.append(self._loc_entries_frame)

        ttk.Label(self._loc_entries_frame, text="纬度:", font=FONT_LABEL).pack(side=tk.LEFT)
        self._var_lat = tk.StringVar(
            value=str(self.config.get("location", {}).get("latitude") or "")
        )
        _entry_lat = ttk.Entry(self._loc_entries_frame, textvariable=self._var_lat, width=10,
                  font=FONT_LABEL)
        _entry_lat.pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(self._loc_entries_frame, text="经度:", font=FONT_LABEL).pack(side=tk.LEFT)
        self._var_lon = tk.StringVar(
            value=str(self.config.get("location", {}).get("longitude") or "")
        )
        _entry_lon = ttk.Entry(self._loc_entries_frame, textvariable=self._var_lon, width=10,
                  font=FONT_LABEL)
        _entry_lon.pack(side=tk.LEFT, padx=(4, 0))
        # 输入经纬度时实时更新当前位置显示
        _entry_lat.bind("<KeyRelease>", lambda e: self._update_location_display())
        _entry_lon.bind("<KeyRelease>", lambda e: self._update_location_display())

        # 根据初始模式显示/隐藏经纬度
        if self._var_location_mode.get() == "city":
            self._loc_entries_frame.pack_forget()

        # ── 偏移量 ──
        offset_frame = ttk.Frame(frame)
        offset_frame.pack(fill=tk.X, pady=(0, 4))
        self._all_frames.append(offset_frame)

        ttk.Label(offset_frame, text="日出偏移 (分钟):", font=FONT_LABEL).pack(side=tk.LEFT)
        self._var_sunrise_offset = tk.StringVar(
            value=str(self.config.get("offsets", {}).get("sunrise_offset_minutes", 0))
        )
        ttk.Entry(offset_frame, textvariable=self._var_sunrise_offset, width=6,
                  font=FONT_LABEL).pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(offset_frame, text="日落偏移 (分钟):", font=FONT_LABEL).pack(side=tk.LEFT)
        self._var_sunset_offset = tk.StringVar(
            value=str(self.config.get("offsets", {}).get("sunset_offset_minutes", 0))
        )
        ttk.Entry(offset_frame, textvariable=self._var_sunset_offset, width=6,
                  font=FONT_LABEL).pack(side=tk.LEFT, padx=(4, 0))

        # ── 启动选项 ──
        self._var_autostart = tk.BooleanVar(
            value=self.config.get("autostart", True)
        )
        ttk.Checkbutton(
            frame, text="开机自启动", variable=self._var_autostart
        ).pack(anchor=tk.W, pady=2)

        self._var_minimize_to_tray = tk.BooleanVar(
            value=self.config.get("minimize_to_tray", True)
        )
        ttk.Checkbutton(
            frame, text="关闭时最小化到托盘", variable=self._var_minimize_to_tray
        ).pack(anchor=tk.W, pady=2)

        # ══════════════════════════════════════════════
        # 子区域 B：应用主题设置
        # ══════════════════════════════════════════════
        app_frame = ttk.LabelFrame(frame, text=" 应用主题 ", padding=6)
        app_frame.pack(fill=tk.X, pady=(8, 4))
        self._all_frames.append(app_frame)

        # ── VS Code ──
        self._var_switch_vscode = tk.BooleanVar(
            value=self.config.get("features", {}).get("switch_vscode", True)
        )
        vscode_row = ttk.Frame(app_frame)
        vscode_row.pack(fill=tk.X, pady=(0, 2))
        self._all_frames.append(vscode_row)
        if self._app_icon_vscode:
            ttk.Label(vscode_row, image=self._app_icon_vscode).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Checkbutton(
            vscode_row, text="VS Code 主题", variable=self._var_switch_vscode
        ).pack(side=tk.LEFT)

        # VS Code 主题名称（可展开）
        self._var_vscode_dark = tk.StringVar(
            value=self.config.get("themes", {}).get("vscode_dark", "Default Dark Modern")
        )
        self._var_vscode_light = tk.StringVar(
            value=self.config.get("themes", {}).get("vscode_light", "Default Light Modern")
        )
        vscode_detail = ttk.Frame(app_frame)
        vscode_detail.pack(fill=tk.X, pady=(0, 6), padx=(28, 0))
        self._all_frames.append(vscode_detail)
        ttk.Label(vscode_detail, text="深色:", font=FONT_SMALL).pack(side=tk.LEFT)
        ttk.Entry(vscode_detail, textvariable=self._var_vscode_dark, width=22,
                  font=FONT_SMALL).pack(side=tk.LEFT, padx=(4, 8))
        ttk.Label(vscode_detail, text="浅色:", font=FONT_SMALL).pack(side=tk.LEFT)
        ttk.Entry(vscode_detail, textvariable=self._var_vscode_light, width=22,
                  font=FONT_SMALL).pack(side=tk.LEFT, padx=(4, 0))

        # ── Word ──
        self._var_switch_word = tk.BooleanVar(
            value=self.config.get("features", {}).get("switch_word", True)
        )
        word_row = ttk.Frame(app_frame)
        word_row.pack(fill=tk.X, pady=(0, 6))
        self._all_frames.append(word_row)
        if self._app_icon_word:
            ttk.Label(word_row, image=self._app_icon_word).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Checkbutton(
            word_row, text="Word 主题", variable=self._var_switch_word
        ).pack(side=tk.LEFT)

        # ── 网易云音乐 ──
        self._var_switch_wyy = tk.BooleanVar(
            value=self.config.get("features", {}).get("switch_wyy", True)
        )
        wyy_row = ttk.Frame(app_frame)
        wyy_row.pack(fill=tk.X, pady=(0, 6))
        self._all_frames.append(wyy_row)
        if self._app_icon_wyy:
            ttk.Label(wyy_row, image=self._app_icon_wyy).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Checkbutton(
            wyy_row, text="网易云音乐 主题", variable=self._var_switch_wyy
        ).pack(side=tk.LEFT)

        # ── Edge + Dark Reader ──
        self._var_switch_edge = tk.BooleanVar(
            value=self.config.get("features", {}).get("switch_edge_dark_reader", True)
        )
        edge_row = ttk.Frame(app_frame)
        edge_row.pack(fill=tk.X, pady=(0, 2))
        self._all_frames.append(edge_row)
        if self._app_icon_edge:
            ttk.Label(edge_row, image=self._app_icon_edge).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Checkbutton(
            edge_row, text="Edge + Dark Reader", variable=self._var_switch_edge
        ).pack(side=tk.LEFT)

    # ── 位置模式切换 ──
    def _on_location_mode_change(self):
        """切换位置模式时显示/隐藏对应控件。"""
        mode = self._var_location_mode.get()
        # 找到 offset_frame 作为锚点（它在两个 frame 之后，位置固定）
        # settings frame 的子 widget 顺序：mode_frame, city_frame/loc_entries_frame, offset_frame, ...
        children = self._settings_frame.winfo_children()
        offset_widget = None
        for child in children:
            # offset_frame 是包含"日出偏移"标签的 frame
            try:
                for sub in child.winfo_children():
                    if isinstance(sub, ttk.Label) and "日出偏移" in sub.cget("text"):
                        offset_widget = child
                        break
            except Exception:
                pass
            if offset_widget:
                break

        if mode == "city":
            self._loc_entries_frame.pack_forget()
            if offset_widget:
                self._city_frame.pack(in_=self._settings_frame, before=offset_widget,
                                      fill=tk.X, pady=(0, 6))
            else:
                self._city_frame.pack(fill=tk.X, pady=(0, 6))
        else:
            self._city_frame.pack_forget()
            if offset_widget:
                self._loc_entries_frame.pack(in_=self._settings_frame, before=offset_widget,
                                             fill=tk.X, pady=(0, 6))
            else:
                self._loc_entries_frame.pack(fill=tk.X, pady=(0, 6))

        # 切换模式后立即刷新当前位置显示
        self._update_display()

    def _on_city_selected(self, event=None):
        """城市下拉选择后，自动填入经纬度并立即刷新。"""
        city_name = self._var_selected_city.get()
        info = get_city_info(city_name)
        if info:
            self._var_lat.set(str(info["lat"]))
            self._var_lon.set(str(info["lon"]))
            # 选城市 = 切到城市模式，停止 IP 检测
            self._var_location_mode.set("city")
            self._on_location_mode_change()
            # 立即保存位置配置并刷新
            self._save_location_and_refresh()

    def _on_city_typing(self, event=None):
        """城市输入框键入时，筛选下拉列表。"""
        typed = self._var_selected_city.get().strip()
        if not typed:
            self._city_combo["values"] = get_city_names()
            return
        # 简单的前缀/包含匹配筛选
        all_names = get_city_names()
        filtered = [n for n in all_names if typed in n]
        self._city_combo["values"] = filtered

    def _save_location_and_refresh(self):
        """保存当前 UI 中的位置配置到 config，并通知 scheduler 重新计算。"""
        location_mode = self._var_location_mode.get()
        city = self.config.get("location", {}).get("city")
        timezone = self.config.get("location", {}).get("timezone")

        try:
            lat = float(self._var_lat.get().strip()) if self._var_lat.get().strip() else None
            lon = float(self._var_lon.get().strip()) if self._var_lon.get().strip() else None
        except ValueError:
            return

        if location_mode == "city":
            selected = self._var_selected_city.get().strip()
            city_info = get_city_info(selected)
            if city_info:
                lat = city_info["lat"]
                lon = city_info["lon"]
                timezone = city_info["timezone"]
                city = selected

        if lat is None or lon is None or timezone is None:
            return

        updates = {
            "location": {
                "location_mode": location_mode,
                "auto_detect": location_mode == "auto",
                "latitude": lat,
                "longitude": lon,
                "timezone": timezone,
                "city": city,
            },
        }
        self.config = cfg.update_config(self.config, updates)
        self.scheduler.config = self.config

        # 同步重算（在当前线程，结果立即可用）
        self.scheduler.recalculate_now()

        if self.on_config_change:
            self.on_config_change(self.config)

        # 立即刷新完整显示
        self._update_display()

    # ── 主题切换 ──
    def _apply_theme(self, is_dark: bool):
        """应用暗色或亮色主题到整个窗口。"""
        if not self.root:
            return

        self._is_dark_theme = is_dark
        theme = DARK_THEME if is_dark else LIGHT_THEME
        style = self._style

        # 全局窗口背景
        self.root.configure(bg=theme["bg"])

        # ttk.Style 配置
        style.configure(".", background=theme["bg"], foreground=theme["fg"],
                         font=FONT_LABEL)
        style.configure("TFrame", background=theme["frame_bg"])
        style.configure("TLabel", background=theme["frame_bg"],
                         foreground=theme["label_fg"], font=FONT_LABEL)
        style.configure("TLabelframe", background=theme["frame_bg"],
                         foreground=theme["labelframe_fg"], font=FONT_LABEL)
        style.configure("TLabelframe.Label", background=theme["frame_bg"],
                         foreground=theme["labelframe_fg"], font=FONT_LABEL)
        style.configure("TButton", background=theme["button_bg"],
                         foreground=theme["button_fg"], font=FONT_LABEL)
        style.map("TButton",
                   background=[("active", theme["button_active"])],
                   foreground=[("active", theme["button_fg"]),
                               ("disabled", "#808080")])
        style.configure("Toolbutton", background=theme["button_bg"],
                         foreground=theme["button_fg"], font=FONT_LABEL)
        style.map("Toolbutton",
                   background=[("active", theme["button_active"])],
                   foreground=[("active", theme["button_fg"]),
                               ("disabled", "#808080")])
        style.configure("TCheckbutton", background=theme["frame_bg"],
                         foreground=theme["label_fg"], font=FONT_LABEL,
                         indicatorcolor=theme["entry_bg"])
        style.map("TCheckbutton",
                   indicatorcolor=[("selected", theme["accent"])])
        style.configure("TRadiobutton", background=theme["frame_bg"],
                         foreground=theme["label_fg"], font=FONT_LABEL)
        style.map("TRadiobutton",
                   background=[("active", theme["button_active"]),
                               ("selected", theme["accent"])],
                   foreground=[("active", theme["button_fg"]),
                               ("selected", theme["select_fg"])])
        style.configure("TEntry", fieldbackground=theme["entry_bg"],
                         foreground=theme["entry_fg"], font=FONT_LABEL)
        style.map("TEntry",
                   fieldbackground=[("focus", theme["entry_bg"])],
                   foreground=[("disabled", "#808080")])
        style.configure("TCombobox", fieldbackground=theme["entry_bg"],
                         foreground=theme["entry_fg"], background=theme["button_bg"],
                         font=FONT_LABEL, selectbackground=theme["select_bg"],
                         selectforeground=theme["select_fg"])
        style.map("TCombobox",
                   fieldbackground=[("readonly", theme["entry_bg"]),
                                    ("focus", theme["entry_bg"])],
                   foreground=[("readonly", theme["entry_fg"]),
                               ("disabled", "#808080")])
        style.configure("TSeparator", background=theme["separator"])

        # 特殊：状态标签字体
        if self._lbl_status:
            self._lbl_status.configure(font=FONT_TITLE)

        # Combobox 下拉列表颜色（需要通过 option_add 设置）
        self.root.option_add("*TCombobox*Listbox.background", theme["entry_bg"])
        self.root.option_add("*TCombobox*Listbox.foreground", theme["entry_fg"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", theme["select_bg"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", theme["select_fg"])

        # 强制刷新所有 widget（ttk style 变更不会自动刷新已有 widget）
        self._force_refresh_widgets(self.root, theme)

    def _force_refresh_widgets(self, widget, theme):
        """递归刷新所有 widget 的颜色。"""
        try:
            w_class = widget.winfo_class()
            if w_class in ("TLabel", "TFrame", "TCheckbutton", "TRadiobutton"):
                widget.configure(background=theme["frame_bg"])
                if w_class != "TFrame":
                    widget.configure(foreground=theme["label_fg"])
            elif w_class in ("TLabelframe",):
                widget.configure(background=theme["frame_bg"],
                                 foreground=theme["labelframe_fg"])
            elif w_class in ("TButton",):
                widget.configure(style="TButton")
            elif w_class == "TEntry":
                widget.configure(foreground=theme["entry_fg"])
        except Exception:
            pass
        for child in widget.winfo_children():
            self._force_refresh_widgets(child, theme)

    def show(self) -> None:
        """Show the GUI window."""
        if not self._widgets_created:
            self._setup_window()
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self._update_display()
        self._start_update_loop()

    def hide(self) -> None:
        """Hide the window (minimize to tray)."""
        if self.root:
            self.root.withdraw()
            self._stop_update_loop()

    def apply_theme_for_mode(self, is_dark: bool) -> None:
        """外部调用：根据当前深色/浅色模式切换 GUI 主题。"""
        if not self._widgets_created:
            return
        self._apply_theme(is_dark)

    def _start_update_loop(self):
        """Start periodic display updates."""
        self._update_display()
        self._update_job = self.root.after(30000, self._start_update_loop)

    def _stop_update_loop(self):
        """Stop periodic display updates."""
        if self._update_job and self.root:
            self.root.after_cancel(self._update_job)
            self._update_job = None

    def _update_display(self):
        """Update all status labels."""
        if not self._widgets_created:
            return

        status = self.scheduler.get_status()

        # Current mode
        is_dark = status.get("is_dark")
        if is_dark is not None:
            self._lbl_status.config(
                text="🌙 深色模式已激活" if is_dark else "☀️ 浅色模式已激活"
            )

        # Sun times (with timezone)
        sunrise = status.get("sunrise")
        sunset = status.get("sunset")
        tz_name = ""
        if self.scheduler.geo:
            tz_name = self.scheduler.geo.timezone

        if sunrise:
            time_str = sunrise.strftime("%H:%M:%S")
            if tz_name:
                time_str += f"  ({tz_name})"
            self._lbl_sunrise.config(text=time_str)
        if sunset:
            time_str = sunset.strftime("%H:%M:%S")
            if tz_name:
                time_str += f"  ({tz_name})"
            self._lbl_sunset.config(text=time_str)

        # Next switch
        next_time = status.get("next_switch_time")
        next_is_dark = status.get("next_switch_is_dark")
        if next_time and next_is_dark is not None:
            tz = None
            if self.scheduler.geo:
                tz = ZoneInfo(self.scheduler.geo.timezone)
            now = datetime.now(tz) if tz else datetime.now()
            delta = next_time - now
            total_secs = int(delta.total_seconds())
            if total_secs < 0:
                # Stale next_switch_time (e.g. after sleep/hibernate);
                # scheduler hasn't recalculated yet — show placeholder
                self._lbl_next.config(text="重新计算中...")
            else:
                hours, remainder = divmod(total_secs, 3600)
                minutes, seconds = divmod(remainder, 60)
                mode = "深色" if next_is_dark else "浅色"
                self._lbl_next.config(
                    text=f"{mode}模式 @ {next_time.strftime('%H:%M')} ({hours}h{minutes}m)"
                )

        # Location — 城市模式显示城市名，经纬度模式显示坐标
        mode = self._var_location_mode.get() if self._var_location_mode else "auto"
        city = status.get("city") or self.config.get("location", {}).get("city")
        geo = self.scheduler.geo
        if mode == "city" and city:
            self._lbl_location.config(text=city)
        elif mode == "auto" and geo and geo.latitude and geo.longitude:
            self._lbl_location.config(text=f"{geo.latitude:.4f}, {geo.longitude:.4f}")
        else:
            # 经纬度模式：显示输入框中的值
            lat_str = self._var_lat.get().strip() if self._var_lat else ""
            lon_str = self._var_lon.get().strip() if self._var_lon else ""
            if lat_str and lon_str:
                try:
                    self._lbl_location.config(text=f"{float(lat_str):.4f}, {float(lon_str):.4f}")
                except ValueError:
                    if city:
                        self._lbl_location.config(text=city)
            elif city:
                self._lbl_location.config(text=city)

    def _update_location_display(self):
        """经纬度输入框变化时，实时更新当前位置显示。"""
        lat_str = self._var_lat.get().strip()
        lon_str = self._var_lon.get().strip()
        if lat_str and lon_str:
            try:
                lat = float(lat_str)
                lon = float(lon_str)
                self._lbl_location.config(text=f"{lat:.4f}, {lon:.4f}")
            except ValueError:
                pass

    def _on_about(self):
        """Show about dialog with software info."""
        # Build sun time info
        sun_info = ""
        st = self.scheduler.sun_times
        geo = self.scheduler.geo
        if st and geo:
            sunrise = st.sunrise.strftime("%H:%M:%S")
            sunset = st.sunset.strftime("%H:%M:%S")
            sun_info = (
                f"\n📍 当前位置: {geo.city} ({geo.latitude:.2f}, {geo.longitude:.2f})\n"
                f"🌅 今日日出: {sunrise}\n"
                f"🌇 今日日落: {sunset}\n"
            )

        about_text = (
            f"☀️ Dark Mode Auto Switcher v1.0\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 灵感来源\n\n"
            f"Windows 系统没有好用的统一深色/浅色\n"
            f"模式自动切换工具，本软件根据日出日落\n"
            f"时间自动切换系统及各应用的主题。\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔧 支持应用\n\n"
            f"• Windows 系统主题\n"
            f"• VS Code\n"
            f"• Microsoft Word / Office\n"
            f"• Edge + Dark Reader\n"
            f"• 网易云音乐\n"
            f"{sun_info}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📐 计算原理\n\n"
            f"日出日落由 astral 库根据经纬度和日期\n"
            f"通过天文公式计算，精度 ±1 分钟，无需联网。\n\n"
            f"1. 太阳赤纬 δ（地球倾角）:\n"
            f"   δ = 23.45° × sin(360/365 × (284 + n))\n"
            f"   n = 当年的第几天\n\n"
            f"2. 时角 ω（日出日落对应角度）:\n"
            f"   cos(ω) = (sin(-0.833°) - sin(φ)×sin(δ))\n"
            f"                    / (cos(φ)×cos(δ))\n"
            f"   φ = 当地纬度\n"
            f"   -0.833° = 大气折射 + 太阳视半径修正\n\n"
            f"3. 日出日落时间:\n"
            f"   日出 = 12:00 - ω/15°\n"
            f"   日落 = 12:00 + ω/15°\n"
            f"   （15°/小时 = 地球自转角速度）\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍💻 开发者: Petit Matthieu\n"
            f"🛠️ 开发工具: Claude Code + Mimo V2.5 Pro\n"
            f"📌 版本: v1.0\n"
        )

        # Create dialog
        win = tk.Toplevel(self.root)
        win.title("关于")
        win.geometry("400x580")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        # Theme the dialog
        is_dark = self._is_dark_theme
        bg = DARK_THEME["bg"] if is_dark else LIGHT_THEME["bg"]
        fg = DARK_THEME["fg"] if is_dark else LIGHT_THEME["fg"]
        btn_bg = DARK_THEME["button_bg"] if is_dark else LIGHT_THEME["button_bg"]
        win.configure(bg=bg)

        # Text
        text_widget = tk.Text(
            win, wrap=tk.WORD, bg=bg, fg=fg,
            font=(FONT_FAMILY, 10), relief=tk.FLAT,
            padx=16, pady=16, cursor="arrow",
        )
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert("1.0", about_text)
        text_widget.config(state=tk.DISABLED)

        # Close button
        btn_frame = tk.Frame(win, bg=bg)
        btn_frame.pack(fill=tk.X, padx=16, pady=(0, 16))
        close_btn = tk.Button(
            btn_frame, text="关闭", command=win.destroy,
            bg=btn_bg, fg=fg, font=(FONT_FAMILY, 10),
            relief=tk.FLAT, padx=24, pady=4,
            activebackground=DARK_THEME["button_active"] if is_dark else LIGHT_THEME["button_active"],
        )
        close_btn.pack()

    def _on_manual_toggle(self):
        """Handle manual toggle button."""
        if self.on_toggle:
            self.on_toggle()
        # Sync GUI state from scheduler (on_toggle already updated it)
        is_dark = self.scheduler.is_dark
        if is_dark is not None:
            self._apply_theme(is_dark)
            self._update_display()
            # Update window icon
            try:
                from .icons import get_moon_ico_path, get_sun_ico_path
                ico = str(get_moon_ico_path() if is_dark else get_sun_ico_path())
                self.root.iconbitmap(ico)
            except Exception:
                pass

    def _on_save_settings(self):
        """Save all settings from GUI."""
        try:
            lat_str = self._var_lat.get().strip()
            lon_str = self._var_lon.get().strip()
            lat = float(lat_str) if lat_str else None
            lon = float(lon_str) if lon_str else None
        except ValueError:
            messagebox.showerror("错误", "经纬度必须是数字")
            return

        try:
            sunrise_offset = int(self._var_sunrise_offset.get() or "0")
            sunset_offset = int(self._var_sunset_offset.get() or "0")
        except ValueError:
            messagebox.showerror("错误", "偏移量必须是整数")
            return

        location_mode = self._var_location_mode.get()
        city = self.config.get("location", {}).get("city")
        timezone = self.config.get("location", {}).get("timezone")

        if location_mode == "city":
            selected = self._var_selected_city.get().strip()
            city_info = get_city_info(selected)
            if city_info:
                lat = city_info["lat"]
                lon = city_info["lon"]
                timezone = city_info["timezone"]
                city = selected
            else:
                # 没有精确匹配，保留用户输入的经纬度
                if not lat or not lon:
                    messagebox.showwarning("提示", f"未找到城市「{selected}」的坐标，请手动输入经纬度或从列表中选择。")
                    return

        updates = {
            "location": {
                "location_mode": location_mode,
                "auto_detect": location_mode == "auto",
                "latitude": lat,
                "longitude": lon,
                "timezone": timezone,
                "city": city,
            },
            "offsets": {
                "sunrise_offset_minutes": sunrise_offset,
                "sunset_offset_minutes": sunset_offset,
            },
            "themes": {
                "vscode_dark": self._var_vscode_dark.get().strip(),
                "vscode_light": self._var_vscode_light.get().strip(),
            },
            "features": {
                "switch_system_theme": True,
                "switch_vscode": self._var_switch_vscode.get(),
                "switch_edge_dark_reader": self._var_switch_edge.get(),
                "switch_word": self._var_switch_word.get(),
                "switch_wyy": self._var_switch_wyy.get(),
            },
            "autostart": self._var_autostart.get(),
            "minimize_to_tray": self._var_minimize_to_tray.get(),
        }

        self.config = cfg.update_config(self.config, updates)

        # Handle autostart registry
        _set_autostart(updates["autostart"])

        # Recalculate scheduler（同步，结果立即可用）
        self.scheduler.config = self.config
        self.scheduler.recalculate_now()

        # Notify
        if self.on_config_change:
            self.on_config_change(self.config)

        # 立即刷新完整显示
        self._update_display()

        logger.info("Settings saved")

        # Show confirmation
        messagebox.showinfo("保存成功", "设置已保存并生效。")


def _set_autostart(enable):
    """Set or remove Windows auto-start registry entry."""
    import sys
    import os
    import winreg

    APP_NAME = "DarkModeAutoSwitcher"
    REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE
        )
        if enable:
            if getattr(sys, 'frozen', False):
                # exe 模式：直接用 exe 路径
                value = f'"{sys.executable}"'
            else:
                # 开发模式：用 pythonw + 脚本路径
                python_exe = sys.executable.replace("python.exe", "pythonw.exe")
                script_path = os.path.abspath(sys.argv[0])
                value = f'"{python_exe}" "{script_path}"'
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, value)
            logger.info("Auto-start enabled: %s", value)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
                logger.info("Auto-start disabled")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except OSError as e:
        logger.error("Failed to set auto-start: %s", e)
