# -*- coding: utf-8 -*-
"""
md图片识别器
"""

import re
import os
import sys
import zipfile
from pathlib import Path
from ZaiOcr import ZaiOcr
import importlib.util

if importlib.util.find_spec("PIL") is None:
    raise SystemExit("缺少依赖 Pillow，请先安装：pip install pillow, 如果是macOS请先使用：brew install python-tk")

import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
from queue import Queue, Empty
import threading
SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tiff"}

class FolderImageBrowser:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("md图片识别器")
        self.root.geometry("1000x700")
        self.root.minsize(600, 400)

        self.image_paths = []
        self.index = -1
        self._resize_after_id = None
        self.current_tk_image = None
        self.current_pil_image = None
        self.ocr = None
        self.item = ['','','']
        self.dir = None
        self.md_file = None
        self.selection_rect_id = None
        self.drag_start = None
        self.drag_mode = None
        self.resize_handle = None
        self.drag_origin_rect = None
        self.selection_bbox_image = None
        self.display_offset = (0, 0)
        self.display_size = (0, 0)
        self.works = Queue()
        self.ui_works = Queue()
        threading.Thread(target=self.doWorks, daemon=True).start()  # 异步初始化 OCR，避免界面卡顿
        self.root.after(50, self._drain_ui_works)
        # 顶部操作区
        top = tk.Frame(root)
        top.pack(fill=tk.X, padx=8, pady=8)

        tk.Button(top, text="打开asset", command=self.open_folder).pack(side=tk.LEFT)
        tk.Button(top, text="打开MD", command=self.open_md).pack(side=tk.LEFT)

        self.chk_formula = tk.IntVar(value=0)
        tk.Checkbutton(top, text="替换公式", variable=self.chk_formula).pack(side=tk.LEFT, padx=(8, 0))
        tk.Button(top, text="生成Zip", command=lambda: self.open_md2(True)).pack(side=tk.LEFT)
        tk.Button(top, text="生成MD", command=lambda: self.open_md2(False)).pack(side=tk.LEFT)

        tk.Button(top, text="<", command=lambda: self.prev_image()).pack(side=tk.LEFT, padx=(8, 0))
        tk.Button(top, text=">", command=lambda: self.next_image()).pack(side=tk.LEFT)

        tk.Button(top, text="识别", command=self.recognize_image).pack(side=tk.LEFT, padx=(5, 0))
        tk.Button(top, text="删除", command=self.delete_image).pack(side=tk.LEFT)

        self.index_var = tk.IntVar(value=0)
        text_index = tk.Entry(top, textvariable=self.index_var, width=3)
        text_index.pack(side=tk.LEFT, padx=(8, 0))
        text_index.bind("<Return>", self.jump_to_index)

        # 增加空按钮用于去除编辑框的焦点
        self.btn_pages = tk.Button(top, text="/")#, command=lambda: self.root.focus())
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
        # 移动多图相关控件到 image_frame 顶部
        image_top_frame = tk.Frame(image_frame)
        image_top_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))

        self.next_count_var = tk.IntVar(value=1)
        tk.Spinbox(image_top_frame, from_=1, to=5, width=2, textvariable=self.next_count_var, command=self.show_current_image).pack(side=tk.LEFT, padx=(8, 0))
        tk.Button(image_top_frame, text="多图识别", command=self.recognize_image2).pack(side=tk.LEFT, padx=(5, 0))
        tk.Button(image_top_frame, text="<<", command=lambda: self.prev_image(self.next_count_var.get())).pack(side=tk.LEFT, padx=(8, 0))
        tk.Button(image_top_frame, text=">>", command=lambda: self.next_image(self.next_count_var.get())).pack(side=tk.LEFT)

        self.image_canvas = tk.Canvas(image_frame, bg="#1e1e1e", highlightthickness=0)
        self.image_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.image_vscroll = tk.Scrollbar(image_frame, orient=tk.VERTICAL, command=self.image_canvas.yview)
        self.image_canvas.configure(yscrollcommand=self.image_vscroll.set)
        self.image_canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self.image_canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.image_canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.image_canvas.bind("<MouseWheel>", self._on_mouse_wheel)

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

        # 中间按钮行
        text_button_frame = tk.Frame(text_frame, height=36)
        text_button_frame.pack(side=tk.TOP, fill=tk.X, expand=False, pady=(0, 4))
        text_button_frame.pack_propagate(False)

        tk.Button(text_button_frame, text="html2md", command=self.html2md).pack(side=tk.LEFT, padx=(8, 0))
        tk.Button(text_button_frame, text="```", command=self.addQuate).pack(side=tk.LEFT)
        tk.Button(text_button_frame, text="del 1.", command=self.delete_lineNo).pack(side=tk.LEFT)

        tk.Button(text_button_frame, text="Pad", command=self.addPadding).pack(side=tk.LEFT, padx=(8, 0))
        tk.Button(text_button_frame, text="del |", command=self.delete_table).pack(side=tk.LEFT)
        tk.Button(text_button_frame, text="del \\", command=self.delete_quate).pack(side=tk.LEFT)
        tk.Button(text_button_frame, text="strip", command=self.delete_strip).pack(side=tk.LEFT)

        self.text_remove = tk.Text(text_button_frame, height=1, width=5)
        self.text_remove.pack(side=tk.LEFT, padx=(8, 0))
        tk.Button(text_button_frame, text="del", command=self.delete_text).pack(side=tk.LEFT)
        tk.Button(text_button_frame, text="```", command=self.addQuate2).pack(side=tk.LEFT)

        # 下方文本编辑框
        text_bottom_frame = tk.Frame(text_frame)
        text_bottom_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(4, 0))

        self.text_code = tk.Text(text_bottom_frame, undo=True, wrap=tk.WORD)
        self.text_code.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar_bottom = tk.Scrollbar(text_bottom_frame, command=self.text_code.yview)
        scrollbar_bottom.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_code.config(yscrollcommand=scrollbar_bottom.set)

        # 快捷键
        self._bind_shortcuts()
        self.root.bind("<Configure>", self._on_resize)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _bind_shortcuts(self):
        # macOS 上补充 Option/Command，其他平台保持 Alt/Control。
        alt_like_mods = ["Alt"]
        extra_control_mods = []
        if sys.platform == "darwin":
            alt_like_mods.insert(0, "Option")
            extra_control_mods.append("Command")

        alt_actions = {
            "Left": lambda e: self.prev_image(),
            "Right": lambda e: self.next_image(),
            "Delete": lambda e: self.delete_image(),
            "Up": lambda e: self.recognize_image(),
            "Down": lambda e: self.addQuate(),
            "r": lambda e: self.recognize_image(),
            "v": lambda e: self.recognize_image2(),
        }
        for key, handler in alt_actions.items():
            for mod in alt_like_mods:
                self.root.bind(f"<{mod}-{key}>", handler)

        control_actions = {
            "Up": lambda e: self.recognize_image2(),
            "Left": lambda e: self.prev_image(self.next_count_var.get()),
            "Right": lambda e: self.next_image(self.next_count_var.get()),
        }
        for key, handler in control_actions.items():
            self.root.bind(f"<Control-{key}>", handler)
            for mod in extra_control_mods:
                self.root.bind(f"<{mod}-{key}>", handler)

    def doWorks(self):
        while True:
            try:
                work = self.works.get(timeout=0.1)
                work()
            except Empty:
                continue
            except Exception as e:
                print(f"执行任务时发生错误: {str(e)}", file=sys.stderr)

    def addWork(self, func):
        self.works.put(func)

    def run_on_ui(self, func, *args, **kwargs):
        self.ui_works.put((func, args, kwargs))

    def _drain_ui_works(self):
        try:
            while True:
                func, args, kwargs = self.ui_works.get_nowait()
                func(*args, **kwargs)
        except Empty:
            pass
        except Exception as e:
            print(f"执行UI任务时发生错误: {str(e)}", file=sys.stderr)
        self.root.after(50, self._drain_ui_works)

    def getDisplayImage(self):
        if self.index < 0 or self.index >= len(self.image_paths):
            return None

        pos = []
        if self.next_count_var.get() < 2:
            with Image.open(self.image_paths[self.index]) as img:
                return (img.copy(), pos)

        end = self._get_end_index()
        images = []
        target_width = 0
        target_height = 0
        index = self.index
        while index < end:
            path = self.image_paths[index]
            with Image.open(path) as img:
                rgb = img.convert("RGB")
                images.append((index, rgb.copy()))
                target_width = max(target_width, rgb.width)
                target_height += rgb.height
            index += 1
        offset_y = 0
        merged = Image.new("RGB", (target_width, target_height), color=(255, 255, 255))
        for img_index, rgb in images:
            merged.paste(rgb, (0, offset_y))
            pos.append((img_index, offset_y/target_height))
            offset_y += rgb.height
        return (merged, pos)

    def _get_end_index(self):
        end = self.index + self.next_count_var.get()
        if end > len(self.image_paths):
            end = len(self.image_paths)
        return end

    def setdir(self, path):
        if self.ocr: #保存配置项
            self.ocr.setConfig("index", self.index)
            self.ocr.setConfig("next_count", self.next_count_var.get())
            
        if not path:
            return
        self.dir = path
        os.chdir(self.dir)
        self.ocr = ZaiOcr()
        self.ocr.initDb("ocr_cache.db")

        # 读取配置项
        index = self.ocr.getConfig("index")
        self.index = int(index) if index is not None else 0
        next_count = self.ocr.getConfig("next_count")
        self.next_count_var.set(int(next_count) if next_count is not None else 1)

    def _clear_selection(self):
        if self.selection_rect_id is not None:
            self.image_canvas.delete(self.selection_rect_id)
            self.selection_rect_id = None
        self.drag_start = None
        self.drag_mode = None
        self.resize_handle = None
        self.drag_origin_rect = None
        self.selection_bbox_image = None

    def _get_current_rect(self):
        if self.selection_rect_id is None:
            return None
        coords = self.image_canvas.coords(self.selection_rect_id)
        if len(coords) != 4:
            return None
        x0, y0, x1, y1 = coords
        return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)

    def _point_in_rect(self, x, y, rect):
        x0, y0, x1, y1 = rect
        return x0 <= x <= x1 and y0 <= y <= y1

    def _detect_resize_handle(self, x, y, rect, margin=8):
        x0, y0, x1, y1 = rect
        near_left = abs(x - x0) <= margin
        near_right = abs(x - x1) <= margin
        near_top = abs(y - y0) <= margin
        near_bottom = abs(y - y1) <= margin

        if near_left and near_top:
            return "nw"
        if near_right and near_top:
            return "ne"
        if near_left and near_bottom:
            return "sw"
        if near_right and near_bottom:
            return "se"
        if near_left:
            return "w"
        if near_right:
            return "e"
        if near_top:
            return "n"
        if near_bottom:
            return "s"
        return None

    def _move_rect_within_display(self, rect, dx, dy):
        x0, y0, x1, y1 = rect
        ox, oy = self.display_offset
        dw, dh = self.display_size
        min_x = ox
        min_y = oy
        max_x = ox + dw
        max_y = oy + dh

        nx0, ny0, nx1, ny1 = x0 + dx, y0 + dy, x1 + dx, y1 + dy

        if nx0 < min_x:
            shift = min_x - nx0
            nx0 += shift
            nx1 += shift
        if nx1 > max_x:
            shift = nx1 - max_x
            nx0 -= shift
            nx1 -= shift
        if ny0 < min_y:
            shift = min_y - ny0
            ny0 += shift
            ny1 += shift
        if ny1 > max_y:
            shift = ny1 - max_y
            ny0 -= shift
            ny1 -= shift
        return nx0, ny0, nx1, ny1

    def _resize_rect(self, rect, handle, x, y):
        x0, y0, x1, y1 = rect
        ox, oy = self.display_offset
        dw, dh = self.display_size
        min_x = ox
        min_y = oy
        max_x = ox + dw
        max_y = oy + dh
        min_size = 3

        if "w" in handle:
            x0 = min(max(x, min_x), x1 - min_size)
        if "e" in handle:
            x1 = max(min(x, max_x), x0 + min_size)
        if "n" in handle:
            y0 = min(max(y, min_y), y1 - min_size)
        if "s" in handle:
            y1 = max(min(y, max_y), y0 + min_size)
        return x0, y0, x1, y1

    def _clamp_to_display(self, x, y):
        ox, oy = self.display_offset
        dw, dh = self.display_size
        if dw <= 0 or dh <= 0:
            return x, y
        x = min(max(x, ox), ox + dw)
        y = min(max(y, oy), oy + dh)
        return x, y

    def _update_image_scrollbar(self, image_height, canvas_height):
        if image_height > canvas_height:
            if not self.image_vscroll.winfo_ismapped():
                self.image_vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        elif self.image_vscroll.winfo_ismapped():
            self.image_vscroll.pack_forget()

    def _on_mouse_wheel(self, event):
        if self.display_size[1] <= max(self.image_canvas.winfo_height(), 1):
            return
        step = -1 if event.delta > 0 else 1
        self.image_canvas.yview_scroll(step, "units")

    def _canvas_to_image_bbox(self, x0, y0, x1, y1):
        if self.current_pil_image is None:
            return None
        ow, oh = self.current_pil_image.size
        dw, dh = self.display_size
        if dw <= 0 or dh <= 0:
            return None

        sx = ow / dw
        sy = oh / dh
        ox, oy = self.display_offset

        ix0 = int(round((x0 - ox) * sx))
        iy0 = int(round((y0 - oy) * sy))
        ix1 = int(round((x1 - ox) * sx))
        iy1 = int(round((y1 - oy) * sy))

        ix0 = min(max(ix0, 0), ow)
        iy0 = min(max(iy0, 0), oh)
        ix1 = min(max(ix1, 0), ow)
        iy1 = min(max(iy1, 0), oh)
        return ix0, iy0, ix1, iy1

    def _on_canvas_press(self, event):
        if self.current_tk_image is None:
            return
        x = self.image_canvas.canvasx(event.x)
        y = self.image_canvas.canvasy(event.y)
        x, y = self._clamp_to_display(x, y)
        current_rect = self._get_current_rect()
        if current_rect and self._point_in_rect(x, y, current_rect):
            self.drag_start = (x, y)
            self.drag_origin_rect = current_rect
            handle = self._detect_resize_handle(x, y, current_rect)
            self.resize_handle = handle
            self.drag_mode = "resize" if handle else "move"
            return

        self.drag_start = (x, y)
        self.drag_mode = "create"
        self.resize_handle = None
        self.drag_origin_rect = None
        if self.selection_rect_id is not None:
            self.image_canvas.delete(self.selection_rect_id)
        self.selection_rect_id = self.image_canvas.create_rectangle(
            x, y, x, y, outline="#00d2ff", width=2
        )

    def _on_canvas_drag(self, event):
        if self.drag_start is None:
            return
        x = self.image_canvas.canvasx(event.x)
        y = self.image_canvas.canvasy(event.y)
        x, y = self._clamp_to_display(x, y)

        if self.drag_mode == "create":
            if self.selection_rect_id is None:
                return
            x0, y0 = self.drag_start
            self.image_canvas.coords(self.selection_rect_id, x0, y0, x, y)
            return

        if self.selection_rect_id is None or self.drag_origin_rect is None:
            return

        if self.drag_mode == "move":
            sx, sy = self.drag_start
            dx, dy = x - sx, y - sy
            nx0, ny0, nx1, ny1 = self._move_rect_within_display(self.drag_origin_rect, dx, dy)
            self.image_canvas.coords(self.selection_rect_id, nx0, ny0, nx1, ny1)
            return

        if self.drag_mode == "resize" and self.resize_handle:
            nx0, ny0, nx1, ny1 = self._resize_rect(self.drag_origin_rect, self.resize_handle, x, y)
            self.image_canvas.coords(self.selection_rect_id, nx0, ny0, nx1, ny1)

    def _on_canvas_release(self, event):
        if self.drag_start is None or self.selection_rect_id is None:
            return
        rect = self._get_current_rect()
        if rect is None:
            self._clear_selection()
            return

        x0, y0, x1, y1 = rect
        if abs(x1 - x0) < 5 or abs(y1 - y0) < 5:
            self._clear_selection()
            return

        image_bbox = self._canvas_to_image_bbox(x0, y0, x1, y1)
        if image_bbox:
            self.selection_bbox_image = image_bbox
            self.status_var.set(
                f"选区(原图): x={image_bbox[0]}-{image_bbox[2]}, y={image_bbox[1]}-{image_bbox[3]}"
            )
        self.drag_start = None
        self.drag_mode = None
        self.resize_handle = None
        self.drag_origin_rect = None

    def process_md(self, md_file_path, to_zip, formula):
        imgs = []
        alts = {}
        snippet = ""
        with open(md_file_path, 'r', encoding='utf-8') as f:
            # 去重
            simg = set()
            snippet = f.read()
            # 获取图片的alt文本
            alt_matches = re.findall(r'!\[(.*?)\]\(([^)]+)\)', snippet, re.MULTILINE)
            for match in alt_matches:
                alts[match[1]] = match[0] if len(match) > 1 else ""
                simg.add(match[1])
            imgs = list(simg)
        if snippet == "":
            messagebox.showwarning("提示", "未找到任何图片链接或文件内容为空。")
            return
        
        # 切换到 Markdown 文件所在目录，确保图片路径正确
        base_dir = os.path.dirname(md_file_path)
        os.chdir(base_dir)  # 切换到图片所在目录，确保 OCR 数据库使用相对路径
        zf = None
        if to_zip:
            dst_file = md_file_path.replace(".md", ".zip")
            zf = zipfile.ZipFile(dst_file, "w")
        else:
            dst_file = md_file_path.replace(".md", "_ocr.md")

        pos = 0
        print(f"正在处理 Markdown 文件: {md_file_path} 共 {len(imgs)} 张图片")
        for img in imgs:
            pos += 1
            try:
                item = self.ocr.find(img) if self.ocr else None
                if item and len(item[2]) > 0:
                    code = item[2]
                    if code.startswith("$") and code.endswith("$") and not formula:
                        raise ValueError(f"跳过公式")
                    if code == "``": # 空注释直接删除图片
                        code = ""
                    # 直接替换整个图片标签，避免 alt 文本干扰, 但部分节点会抛异常
                    #snippet = re.sub(r'!\[.*?\]\(' + re.escape(img) + r'\)', code, snippet)
                    snippet = snippet.replace(f'![{alts.get(img, "")}]({img})', code)  
                    continue  # 已替换文本，不再添加图片到 ZIP 中
            except Exception as e:
                print(f"处理图片{pos} {img} 时发生错误: {str(e)}")
                
            # 没有找到 OCR 记录或记录为空，才添加图片到 ZIP 中
            if zf and Path(img).is_file():
                print(f"添加图片{pos}: {img}")
                zf.write(img)
        if zf:
            zf.writestr(os.path.basename(md_file_path), snippet)
            zf.close()
        else:
            with open(dst_file, 'w', encoding='utf-8') as f:
                f.write(snippet)
        print(f"已生成文件: {dst_file}")

    def open_md2(self, to_zip):
        if not self.md_file:
            self.md_file = filedialog.askopenfilename(
                title="选择md文件",
                filetypes=[("Markdown files", "*.md")]
                )
        if not self.md_file:
            return
        self.process_md(self.md_file, to_zip, bool(self.chk_formula.get()))

    def open_md(self):
        md_file = filedialog.askopenfilename(
            title="选择md文件",
            filetypes=[("Markdown files", "*.md")],
            initialdir=self.dir if hasattr(self, 'dir') else None,
        )
        if not md_file:
            return
        self.md_file = md_file
        self.setdir(os.path.dirname(md_file))
        imgs = []
        with open(md_file, 'r', encoding='utf-8') as f:
            snippet = f.read()
            # 获取markdown中的图片链接
            # !\[(.*?)\]\((.*?)(?:\s+"(.*?)")?\) 
            # 分组1：alt文本
            # 分组2：图片URL
            # 分组3：title（可选）
            md_imgs = re.findall(r'!\[.*?\]\(([^)]+)\)', snippet, re.MULTILINE)
            print(f"{md_file} 找到 {len(md_imgs)} 张图片链接，正在检查图片文件...")
            simg = set()
            for img in md_imgs: 
                # 去重
                if img in simg:
                    continue
                simg.add(img)
                f = Path(img)
                if f.is_file():  # 触发文件存在检查，提前捕获潜在的路径问题
                    imgs.append(f)
                else:
                    print(f"略过不存在的图片: {img}")
        if len(imgs) == 0:
            messagebox.showwarning("提示", "未找到任何图片链接或文件内容为空。")
            return

        self.btn_pages.config(text=f" / {len(imgs)} :")
        self.root.title(f'asset浏览器 - {self.dir}')

        self.image_paths = imgs
        self.show_current_image()

    def open_folder(self):
        folder = filedialog.askdirectory(title="选择图片文件夹")
        if not folder:
            return

        self.dir = os.path.dirname(folder)
        dirname = os.path.basename(folder)
        self.setdir(self.dir)
        paths = []
        for p in sorted(Path(dirname).iterdir(), key=lambda x: x.name.lower()):
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
                paths.append(p)

        if not paths:
            messagebox.showwarning("提示", "该文件夹中没有可显示的图片。")
            return

        self.btn_pages.config(text=f" / {len(paths)} :")
        self.root.title(f'asset浏览器 - {self.dir}')
        self.md_file = None  # 切换到文件夹浏览时，重置当前 Markdown 文件状态
        self.image_paths = paths
        self.show_current_image()

    def delete_image(self):
        if self.index < 0 or self.index >= len(self.image_paths):
            return

        img_path = str(self.image_paths[self.index])
        if self.ocr:
            print(f"删除记录: {img_path}")
            self.ocr.remove(img_path)

        self.item[1] = ''
        self.item[2] = ''
        self.updateText(self.item)
        self.root.focus()  # 删除后焦点回到窗口，避免误触文本编辑框快捷键

    def recognize_image2(self):
        if self.ocr is None:
            return
        if self.index < 0 or self.index >= len(self.image_paths):
            return
        max_size = 2000
        merge = self.current_pil_image # self.getDisplayImage()  # 获取合并后的大图进行 OCR 识别
        if merge is None:
            return
        if (merge.width > max_size or merge.height > max_size):
            scale = min(max_size / merge.width, max_size / merge.height)
            print(f"图片过大{merge.width}x{merge.height}，缩放到 {scale:.2f} 进行 OCR 识别")
            merge = merge.resize((int(merge.width * scale), int(merge.height * scale)), Image.Resampling.LANCZOS)
        image_path = str(self.image_paths[self.index])
        index = self.index
        end = self._get_end_index()
        def ocr_done(code):
            item = self.ocr.analyze(code, image_path)
            if self.index == index:
                self.updateText(item)
            for i in range(index+1, end):
                img_path = str(self.image_paths[i])
                self.ocr.update([img_path, '', '``'])
        self.addWork(lambda: self.run_on_ui(ocr_done, self.ocr.ocr(merge)))

    def recognize_image(self):
        if self.index < 0 or self.index >= len(self.image_paths):
            return
        if self.ocr is None:
            return
        image_path = str(self.image_paths[self.index])
        # 调用 OCR 接口识别图片中的文字
        img = image_path
        if self.current_pil_image and self.selection_bbox_image:
            img = self.current_pil_image.crop(self.selection_bbox_image)
        else:
            with Image.open(image_path) as opened:
                img = opened.copy()
        if img.width > 1024 or img.height > 1024:
            scale = min(1024 / img.width, 1024 / img.height)
            print(f"图片过大{img.width}x{img.height}，缩放到 {scale:.2f} 进行 OCR 识别")
            img = img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)
        index = self.index
        def ocr_done(code):
            item = self.ocr.analyze(code, image_path)
            if self.index == index:
                self.updateText(item)
        self.addWork(lambda: self.run_on_ui(ocr_done, self.ocr.ocr(img)))

    def updateText(self, item):
        self.text_ocr.delete(1.0, tk.END)
        self.text_code.delete(1.0, tk.END)
        if item is None:
            return
        if item[0]:
            self.item = item
        self.text_ocr.insert(tk.END, item[1])
        self.text_code.insert(tk.END, item[2])

    def html2md(self):
        ocr = self.text_ocr.get(1.0, "end-1c")
        if self.ocr:
            code = self.ocr.html2md(ocr)
            self.text_code.delete(1.0, tk.END)
            self.text_code.insert(tk.END, code)

    def _get_selected_or_all(self, text_widget: tk.Text):
        try:
            start = text_widget.index(tk.SEL_FIRST)
            end = text_widget.index(tk.SEL_LAST)
        except tk.TclError:
            start = "1.0"
            end = "end-1c"
        return text_widget.get(start, end), start, end

    def processTextWithSelect(self, text_widget: tk.Text, func):
        content, start, end = self._get_selected_or_all(text_widget)
        new_content = func(content)
        text_widget.delete(start, end)
        text_widget.insert(start, new_content)

    def addQuate(self):
        ocr = self.text_ocr.get(1.0, "end-1c")
        if ocr.startswith('## '):
            ocr = ocr[3:]  # 去掉一级标题标记
        if ocr.startswith('$') and ocr.endswith('$'):
            pass
        else:
            if not ocr.startswith('```'):
                ocr = '```\n' + ocr  # 添加代码块开始标记
            if not ocr.endswith('```'):
                ocr += '\n```'  # 添加代码块结束标记
        self.text_code.delete(1.0, tk.END)
        self.text_code.insert(tk.END, ocr)
    
    def addQuate2(self):
        ocr = self.text_code.get(1.0, "end-1c")
        if ocr.startswith('$') and ocr.endswith('$'):
            return  # 已经是数学公式格式，不再添加代码块标记
        if not ocr.startswith('```'):
            ocr = '```\n' + ocr  # 添加代码块开始标记
        if not ocr.endswith('```'):
            ocr += '\n```'  # 添加代码块结束标记
        self.text_code.delete(1.0, tk.END)
        self.text_code.insert(tk.END, ocr)
        # 选中第二行
        self.text_code.mark_set(tk.INSERT, "2.0")
        self.text_code.see(tk.INSERT)
        self.text_code.focus_set()

    def addPadding(self):
        try:
            start = f"{int(float(self.text_code.index(tk.SEL_FIRST)))}.0"
            end = self.text_code.index(tk.SEL_LAST)
        except tk.TclError:
            start = "1.0"
            end = "end-1c"

        text = self.text_code.get(start, end)
        lines = text.split('\n')
        for i in range(len(lines)):
            if lines[i].startswith('```') or lines[i].startswith('$$'):
                continue
            lines[i] = '    ' + lines[i]
        text = '\n'.join(lines)
        self.text_code.delete(start, end)
        self.text_code.insert(start, text)
        # 保留之前选择行
        new_end = self.text_code.index(f"{start}+{len(text)}c")
        self.text_code.tag_remove(tk.SEL, "1.0", tk.END)
        self.text_code.tag_add(tk.SEL, start, new_end)
        self.text_code.mark_set(tk.INSERT, new_end)
        self.text_code.see(tk.INSERT)

    def delete_table(self):
        self.processTextWithSelect(self.text_code, lambda text: text.replace('|', ''))

    def delete_quate(self):
        self.processTextWithSelect(self.text_code, lambda text: text.replace('\\', ''))

    def delete_text(self): # 删除选中的文本
        txt = self.text_remove.get(1.0, "end-1c")
        if len(txt):
            self.processTextWithSelect(self.text_code, lambda text: text.replace(txt, ''))

    def delete_lineNo(self): # 删除行号
        self.processTextWithSelect(self.text_ocr, lambda text: 
                                   '\n'.join([re.sub(r'^\s*\d+[\.:]', '', line) for line in text.split('\n')]))

    def delete_strip(self):
        self.processTextWithSelect(self.text_code, lambda text: 
                                   '\n'.join([line.strip() for line in text.split('\n')]))

    def check_text_changed(self):
        if self.index < 0 or self.index >= len(self.image_paths):
            return False
        if self.ocr is None:
            return False
        img_path = self.image_paths[self.index]
        # Text 组件的 tk.END 会包含末尾换行，使用 end-1c 便于稳定比较。
        ocr = self.text_ocr.get(1.0, "end-1c")
        code = self.text_code.get(1.0, "end-1c")
        if ocr != self.item[1] or code != self.item[2]:
            print(f"更新记录: {self.item} {ocr} {code}")
            self.item[1] = ocr
            self.item[2] = code
            self.ocr.update(self.item)
            return True
        return False
        
    def show_current_image(self):
        if not self.image_paths or self.index < 0:
            return
        image, pos = self.getDisplayImage()
        if image is None:
            return
        self.current_pil_image = image
        img_path = self.image_paths[self.index]
        # 按画布宽度等比缩放，高度通过滚动查看
        w = max(self.image_canvas.winfo_width(), 300)
        h = max(self.image_canvas.winfo_height(), 200)
        ow, oh = image.size
        if ow > w:
            target_w = max(w, 1)
            target_h = max(int(oh * target_w / max(ow, 1)), 1)
            display_img = image.resize((target_w, target_h), Image.Resampling.LANCZOS)
        else:
            display_img = image.copy()
        self.current_tk_image = ImageTk.PhotoImage(display_img)
        self.image_canvas.delete("all")

        dw, dh = display_img.size
        ox = 0
        oy = 0
        self.display_offset = (ox, oy)
        self.display_size = (dw, dh)
        self.image_canvas.create_image(ox, oy, anchor=tk.NW, image=self.current_tk_image)
        self.image_canvas.configure(scrollregion=(0, 0, dw, dh))
        self.image_canvas.yview_moveto(0)
        self._update_image_scrollbar(dh, h)
        self._clear_selection()
        for idx, p in pos:
            px = int(p * display_img.height)
            self.image_canvas.create_line(0, px, display_img.width, px, fill="#00d2ff", width=2)
            self.image_canvas.create_text(display_img.width - 10, px + 10, text=f"{idx + 1}", fill="#00d2ff")

        self.index_var.set(self.index + 1)
        self.status_var.set(img_path.name)
        item = self.ocr.find(img_path) if self.ocr else None
        self.item[0] = str(img_path)
        if item:
            self.item[1] = item[1]
            self.item[2] = item[2]
        else:
            self.item[1] = ''
            self.item[2] = ''
        self.updateText(self.item)

    def prev_image(self, delta = 1):
        if self.index > 0:
            self.check_text_changed()
            self.index -= delta
            if self.index < 0:
                self.index = 0
            self.show_current_image()

    def next_image(self, delta = 1):
        if self.index < len(self.image_paths) - 1:
            self.check_text_changed()
            self.index += delta
            if self.index >= len(self.image_paths):
                self.index = len(self.image_paths) - 1
            self.show_current_image()

    def jump_to_index(self, _event):
        try:
            idx = self.index_var.get() - 1
            if 0 <= idx < len(self.image_paths):
                self.check_text_changed()
                self.index = idx
                self.show_current_image()
            else:
                messagebox.showwarning("提示", f"请输入有效的图片序号（1-{len(self.image_paths)}）")
        except ValueError:
            messagebox.showwarning("提示", "请输入有效的数字序号")

    def _on_resize(self, _event):
        # 窗口尺寸变化触发频繁，这里使用防抖避免反复重绘导致卡顿。
        if self._resize_after_id is not None:
            self.root.after_cancel(self._resize_after_id)
        self._resize_after_id = self.root.after(120, self._refresh_after_resize)

    def _refresh_after_resize(self):
        self._resize_after_id = None
        if self.image_paths and self.index >= 0:
            self.show_current_image()

    def on_close(self):
        self.check_text_changed()
        self.setdir('')
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = FolderImageBrowser(root)
    root.mainloop()