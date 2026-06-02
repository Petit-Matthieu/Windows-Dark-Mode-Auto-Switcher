"""简单的GUI测试 - 直接运行看窗口是否出现"""
import tkinter as tk
from tkinter import ttk

def main():
    root = tk.Tk()
    root.title("Dark Mode Auto Switcher - 测试")
    root.geometry("400x300")

    # 设置窗口置顶
    root.attributes('-topmost', True)

    frame = ttk.Frame(root, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text="✅ GUI 测试成功！", font=("Segoe UI", 16, "bold")).pack(pady=10)
    ttk.Label(frame, text="如果你能看到这个窗口，说明 GUI 正常工作。", font=("Segoe UI", 10)).pack(pady=5)

    ttk.Label(frame, text="日出: 04:48", font=("Consolas", 12)).pack(pady=2)
    ttk.Label(frame, text="日落: 19:36", font=("Consolas", 12)).pack(pady=2)
    ttk.Label(frame, text="当前位置: 海淀", font=("Consolas", 12)).pack(pady=2)

    ttk.Button(frame, text="关闭测试", command=root.destroy).pack(pady=20)

    root.mainloop()
    print("GUI 测试完成")

if __name__ == "__main__":
    main()
