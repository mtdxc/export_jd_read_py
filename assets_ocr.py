# -*- coding: utf-8 -*-
"""
asset浏览器（支持上一张/下一张）
"""

import importlib.util
from ZaiOcr import ZaiOcr
if importlib.util.find_spec("PIL") is None:
    raise SystemExit("缺少依赖 Pillow，请先安装：pip install pillow")
import re
import os
import sys
import zipfile
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from PIL import Image, ImageTk

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tiff"}

class FolderImageBrowser:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("asset浏览器")
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

        self.btn_open = tk.Button(top, text="打开assets", command=self.open_folder)
        self.btn_open.pack(side=tk.LEFT)

        self.btn_open_md = tk.Button(top, text="处理MD", command=self.open_md)
        self.btn_open_md.pack(side=tk.LEFT)

        self.btn_prev = tk.Button(top, text="上一张", command=self.prev_image, state=tk.DISABLED)
        self.btn_prev.pack(side=tk.LEFT, padx=(8, 0))

        self.btn_next = tk.Button(top, text="下一张", command=self.next_image, state=tk.DISABLED)
        self.btn_next.pack(side=tk.LEFT)

        self.btn_recognize = tk.Button(top, text="识别", command=self.recognize_image)
        self.btn_recognize.pack(side=tk.LEFT, padx=(8, 0))

        self.btn_delete = tk.Button(top, text="删除", command=self.delete_image)
        self.btn_delete.pack(side=tk.LEFT, padx=(8, 0))

        self.text_index = tk.Text(top, height=1, width=3)
        self.text_index.pack(side=tk.LEFT, padx=(8, 0))
        self.text_index.bind("<Return>", self.jump_to_index)

        # 增加空按钮用于去除编辑框的焦点
        self.btn_pages = tk.Button(top, text="/", command=lambda: self.root.focus())
        self.btn_pages.pack(side=tk.LEFT, padx=(8, 0))

        self.status_var = tk.StringVar(value="请选择asset文件夹")
        self.status_label = tk.Label(top, textvariable=self.status_var, anchor="w")
        self.status_label.pack(side=tk.LEFT, padx=12, fill=tk.X, expand=True)

        # 图片与文本并排显示区（支持拖拽分割）
        self.content_pane = tk.PanedWindow(
            root,
            orient=tk.HORIZONTAL,
            sashwidth=6,
            sashrelief=tk.RAISED,
        )
        self.content_pane.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        # 左侧：图片显示区
        image_frame = tk.Frame(self.content_pane)

        self.image_label = tk.Label(image_frame, bg="#1e1e1e")
        self.image_label.pack(fill=tk.BOTH, expand=True)

        # 右侧：文本编辑区
        text_frame = tk.Frame(self.content_pane, width=360)

        self.content_pane.add(image_frame, minsize=320, stretch="always")
        self.content_pane.add(text_frame, minsize=260)

        # 上方文本编辑框
        text_top_frame = tk.Frame(text_frame)
        text_top_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 4))

        self.text_ocr = tk.Text(text_top_frame, undo=True, wrap=tk.WORD)
        self.text_ocr.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar_top = tk.Scrollbar(text_top_frame, command=self.text_ocr.yview)
        scrollbar_top.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_ocr.config(yscrollcommand=scrollbar_top.set)

        # 下方文本编辑框
        text_bottom_frame = tk.Frame(text_frame)
        text_bottom_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(4, 0))

        self.text_code = tk.Text(text_bottom_frame, undo=True, wrap=tk.WORD)
        self.text_code.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar_bottom = tk.Scrollbar(text_bottom_frame, command=self.text_code.yview)
        scrollbar_bottom.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_code.config(yscrollcommand=scrollbar_bottom.set)

        # 快捷键
        self.root.bind("<Left>", self._on_prev_key)
        self.root.bind("<Right>", self._on_next_key)
        self.root.bind("<Delete>", lambda e: self.delete_image() if not self._focus_in_text_widget() else None)
        self.root.bind("<Configure>", self._on_resize)

    def _focus_in_text_widget(self):
        widget = self.root.focus_get()
        return isinstance(widget, tk.Text)

    def _on_prev_key(self, _event):
        if self._focus_in_text_widget():
            return
        self.prev_image()

    def _on_next_key(self, _event):
        if self._focus_in_text_widget():
            return
        self.next_image()

    def process_md(self, md_file_path):
        imgs = []
        snippet = ""
        with open(md_file_path, 'r', encoding='utf-8') as f:
            snippet = f.read()
            # 获取markdown中的图片链接
            imgs = re.findall(r'!\[\]\(([^)]+)\)', snippet, re.MULTILINE)
            # 去重
            imgs = list(set(imgs))
        if snippet == "":
            messagebox.showwarning("提示", "未找到任何图片链接或文件内容为空。")
            return
        
        # 切换到 Markdown 文件所在目录，确保图片路径正确
        dir = os.path.dirname(md_file_path)
        dst_file = md_file_path.replace(".md", ".zip")
        with zipfile.ZipFile(dst_file, "w") as zf:
            pos = 0
            print(f"正在处理 Markdown 文件: {md_file_path} 共 {len(imgs)} 张图片")
            for img in imgs:
                pos += 1
                img_path = Path(os.path.join(dir, img))
                if not img_path.is_file():
                    # 略过非本地文件
                    continue

                try:
                    item = self.ocr.find(img_path)
                    if item and len(item[2]) > 0:
                        print(f"替换图片{pos}: {img}")
                        pattern = re.escape(f'![]({img})')
                        snippet = re.sub(pattern, item[2], snippet)
                        continue  # 已替换文本，不再添加图片到 ZIP 中
                except Exception as e:
                    print(f"处理图片{pos} {img} 时发生错误: {str(e)}\n", file=sys.stderr)
                    
                # 没有找到 OCR 记录或记录为空，才添加图片到 ZIP 中
                print(f"添加图片{pos}: {img}")
                zf.write(img_path, arcname=img)  # 将图片添加到 ZIP 文件中，保持相对路径

            zf.writestr(os.path.basename(md_file_path), snippet)
            print(f"已生成 ZIP 文件: {dst_file}")

    def open_md(self):
        md_file = filedialog.askopenfile(title="选择md文件", 
                                         filetypes=[("Markdown files", "*.md")], 
                                         initialdir=self.dir if hasattr(self, 'dir') else None)
        if not md_file:
            return
        self.process_md(md_file.name)

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
        self.btn_pages.config(text=f" / {len(paths)} :")
        self.dir = os.path.dirname(folder)
        os.chdir(self.dir)  # 切换到图片所在目录，确保 OCR 数据库使用相对路径
        self.root.title(f'asset浏览器 - {self.dir}')
        
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
        self.root.focus()  # 删除后焦点回到窗口，避免误触文本编辑框快捷键

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
        self.status_var.set(img_path.name)

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