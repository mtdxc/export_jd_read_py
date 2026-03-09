# -*- coding: utf-8 -*-
"""
文件夹图片浏览器（支持上一张/下一张）
"""

import importlib.util
from ZaiOcr import ZaiOcr
if importlib.util.find_spec("PIL") is None:
    raise SystemExit("缺少依赖 Pillow，请先安装：pip install pillow")

import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from PIL import Image, ImageTk

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tiff"}


class FolderImageBrowser:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("文件夹图片浏览器")
        self.root.geometry("1000x700")
        self.root.minsize(600, 400)

        self.image_paths = []
        self.index = -1
        self.current_tk_image = None
        self.ocr = None
        self.item = None

        # 顶部操作区
        top = tk.Frame(root)
        top.pack(fill=tk.X, padx=8, pady=8)

        self.btn_open = tk.Button(top, text="打开文件夹", command=self.open_folder)
        self.btn_open.pack(side=tk.LEFT)

        self.btn_prev = tk.Button(top, text="上一张", command=self.prev_image, state=tk.DISABLED)
        self.btn_prev.pack(side=tk.LEFT, padx=(8, 0))

        self.btn_next = tk.Button(top, text="下一张", command=self.next_image, state=tk.DISABLED)
        self.btn_next.pack(side=tk.LEFT, padx=(8, 0))

        self.btn_recognize = tk.Button(top, text="识别", command=self.recognize_image)
        self.btn_recognize.pack(side=tk.LEFT, padx=(8, 0))

        self.btn_delete = tk.Button(top, text="删除", command=self.delete_image)
        self.btn_delete.pack(side=tk.LEFT, padx=(8, 0))

        self.text_index = tk.Text(top, height=1, width=3)
        self.text_index.pack(side=tk.LEFT, padx=(8, 0))
        self.text_index.bind("<Return>", self.jump_to_index)

        self.status_var = tk.StringVar(value="请选择图片文件夹")
        self.status_label = tk.Label(top, textvariable=self.status_var, anchor="w")
        self.status_label.pack(side=tk.LEFT, padx=12, fill=tk.X, expand=True)

        # 图片与文本并排显示区
        content_frame = tk.Frame(root)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        # 左侧：图片显示区
        image_frame = tk.Frame(content_frame)
        image_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        self.image_label = tk.Label(image_frame, bg="#1e1e1e")
        self.image_label.pack(fill=tk.BOTH, expand=True)

        # 右侧：文本编辑区
        text_frame = tk.Frame(content_frame, width=320)
        text_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False)
        text_frame.pack_propagate(False)

        # 上方文本编辑框
        text_top_frame = tk.Frame(text_frame)
        text_top_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 4))

        self.text_ocr = tk.Text(text_top_frame, wrap=tk.WORD)
        self.text_ocr.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar_top = tk.Scrollbar(text_top_frame, command=self.text_ocr.yview)
        scrollbar_top.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_ocr.config(yscrollcommand=scrollbar_top.set)

        # 下方文本编辑框
        text_bottom_frame = tk.Frame(text_frame)
        text_bottom_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(4, 0))

        self.text_code = tk.Text(text_bottom_frame, wrap=tk.WORD)
        self.text_code.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar_bottom = tk.Scrollbar(text_bottom_frame, command=self.text_code.yview)
        scrollbar_bottom.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_code.config(yscrollcommand=scrollbar_bottom.set)

        # 快捷键
        self.root.bind("<Left>", lambda e: self.prev_image())
        self.root.bind("<Right>", lambda e: self.next_image())
        self.root.bind("<Delete>", lambda e: self.delete_image())
        self.root.bind("<Configure>", self._on_resize)

    def open_folder(self):
        folder = filedialog.askdirectory(title="选择图片文件夹")
        if not folder:
            return

        paths = []
        for p in sorted(Path(folder).iterdir(), key=lambda x: x.name.lower()):
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
                paths.append(p)

        if not paths:
            messagebox.showwarning("提示", "该文件夹中没有可显示的图片。")
            return

        self.ocr = ZaiOcr()
        self.ocr.initDb("ocr_cache.db")
        self.image_paths = paths
        self.index = 0
        self.show_current_image()

    def delete_image(self):
        if self.index < 0 or self.index >= len(self.image_paths):
            return

        img_path = str(self.image_paths[self.index])
        if self.ocr:
            print(f"删除记录: {img_path}")
            self.ocr.remove(img_path)

        self.item = (str(img_path), '', '')
        self.updateText(self.item)

    def recognize_image(self):
        if self.index < 0 or self.index >= len(self.image_paths):
            return

        img_path = str(self.image_paths[self.index])
        # 调用 OCR 接口识别图片中的文字
        if self.ocr:
            self.updateText(self.ocr.ocr_code(img_path))

    def updateText(self, item):
        self.text_ocr.delete(1.0, tk.END)
        self.text_code.delete(1.0, tk.END)
        if item is None:
            return
        self.item = item
        self.text_ocr.insert(tk.END, item[1])
        self.text_code.insert(tk.END, item[2])
      
    def check_text_changed(self):
        if self.index < 0 or self.index >= len(self.image_paths):
            return False
        if self.ocr is None:
            return False
        img_path = self.image_paths[self.index]
        # Text 组件的 tk.END 会包含末尾换行，使用 end-1c 便于稳定比较。
        ocr = self.text_ocr.get(1.0, "end-1c")
        code = self.text_code.get(1.0, "end-1c")
        if self.item and (ocr != self.item[1] or code != self.item[2]):
            print(f"更新记录: {self.item} {ocr} {code}")
            self.ocr.update((str(img_path), ocr, code))
            return True
        return False
        
    def show_current_image(self):
        if not self.image_paths or self.index < 0:
            return

        img_path = self.image_paths[self.index]
        try:
            img = Image.open(img_path)
        except Exception as e:
            messagebox.showerror("错误", f"无法打开图片：\n{img_path}\n\n{e}")
            return

        # 按窗口大小等比缩放
        w = max(self.image_label.winfo_width(), 300)
        h = max(self.image_label.winfo_height(), 200)
        img.thumbnail((w - 20, h - 20), Image.Resampling.LANCZOS)

        self.current_tk_image = ImageTk.PhotoImage(img)
        self.image_label.config(image=self.current_tk_image)

        total = len(self.image_paths)
        self.text_index.delete(1.0, tk.END)
        self.text_index.insert(tk.END, str(self.index + 1))
        self.status_var.set(f"/ {total}  -  {img_path.name}")

        self.btn_prev.config(state=tk.NORMAL if self.index > 0 else tk.DISABLED)
        self.btn_next.config(state=tk.NORMAL if self.index < total - 1 else tk.DISABLED)
        self.item = self.ocr.find(img_path)
        if self.item is None:
            self.item = (str(img_path), "", "")
        self.updateText(self.item)

    def prev_image(self):
        if self.index > 0:
            self.check_text_changed()
            self.index -= 1
            self.show_current_image()

    def next_image(self):
        if self.index < len(self.image_paths) - 1:
            self.check_text_changed()
            self.index += 1
            self.show_current_image()

    def jump_to_index(self, _event):
        try:
            idx = int(self.text_index.get(1.0, "end-1c").strip()) - 1
            if 0 <= idx < len(self.image_paths):
                self.check_text_changed()
                self.index = idx
                self.show_current_image()
            else:
                messagebox.showwarning("提示", f"请输入有效的图片序号（1-{len(self.image_paths)}）")
        except ValueError:
            messagebox.showwarning("提示", "请输入有效的数字序号")

    def _on_resize(self, _event):
        # 窗口尺寸变化时刷新当前图片显示
        if self.image_paths and self.index >= 0:
            self.show_current_image()


if __name__ == "__main__":
    root = tk.Tk()
    app = FolderImageBrowser(root)
    root.mainloop()