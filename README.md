# Windows Dark Mode Auto Switcher

自动根据日出日落时间切换 Windows 深色/浅色模式的工具。

## 功能

- 🌍 **自动定位** - 通过 IP 地址自动获取位置
- 🌅 **日出日落** - 基于经纬度精确计算今日日出日落时间
- 🖥️ **系统主题** - 自动切换 Windows 系统深色/浅色模式
- 📝 **VS Code** - 自动切换 VS Code 编辑器主题
- 🌐 **Edge 浏览器** - 配合 Dark Reader 插件自动切换
- 🔔 **系统托盘** - 最小化到托盘，右键菜单操作
- ⏰ **定时调度** - 精确在日出/日落时间切换
- 🚀 **开机自启** - 可选开机自动启动

## 安装

```bash
pip install -r requirements.txt
```

## 运行

```bash
python main.py
```

## 使用说明

1. 启动后程序会在系统托盘显示图标
2. 双击托盘图标打开控制面板
3. 程序会自动检测你的位置并计算日出日落时间
4. 在日出时自动切换到浅色模式，日落时切换到深色模式

### Edge + Dark Reader 设置

为了使 Edge 浏览器跟随系统主题自动切换：

1. 打开 Edge 浏览器
2. 点击 Dark Reader 扩展图标
3. 进入 **Automation** 设置
4. 选择 **By system's dark / light mode**

### VS Code 主题

默认使用 `Default Dark Modern` 和 `Default Light Modern`。你可以在设置中自定义主题名称。

## 配置文件

`config.json` 会在首次运行时自动创建，包含以下配置：

- `location` - 位置信息（经纬度、时区）
- `offsets` - 日出/日落时间偏移（分钟）
- `themes` - VS Code 主题名称
- `features` - 功能开关
- `autostart` - 开机自启

## 技术栈

- Python 3.12+
- tkinter (GUI)
- pystray (系统托盘)
- astral (日出日落计算)
- requests (IP 定位)
- Pillow (图标生成)
- winreg (Windows 注册表)
