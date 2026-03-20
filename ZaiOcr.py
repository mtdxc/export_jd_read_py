import sys
import base64
from pathlib import Path
import requests
import os
from markdownify import markdownify as md
import sqlite3
import re
from io import BytesIO

def _sniff_mime_from_bytes(data: bytes) -> str:
    # PDF
    if data[:5] == b"%PDF-":
        return "application/pdf"
    # PNG
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    # JPEG
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    return "application/octet-stream"


def _as_data_uri(mime: str, b64: str) -> str:
    return f"data:{mime};base64,{b64}"

class ZaiOcr:
    def __init__(self, api_key = ''):
        if len(api_key) == 0:
            api_key = os.environ.get('ZAI_API_KEY', '')
        self.api_key = api_key
        self.cur = None
        self.db = None
        self.db_dir = None
        self.pattern = re.compile(r'\b(if|else|for|while|uint|void|function|def|class|import|return|switch|case|break|continue|try|catch|finally|var|let|const|public|private|static)\b')

    def normalize_db_path(self, path):
        """将传入路径转为相对db_dir的路径，并统一使用/分隔符。"""
        path_str = str(path)
        if path_str.startswith("http://") or path_str.startswith("https://"):
            return path_str
        if path_str.startswith("./"):
            return path_str[2:]
        if self.db_dir and path_str.startswith(self.db_dir):
            path_str = path_str[len(self.db_dir):]
        return path_str.replace("\\", "/")

    def initDb(self, db_name):
        try:
            self.db_dir = os.path.abspath(os.path.dirname(db_name)) + os.path.sep
            print(f"数据库目录: {self.db_dir}")
            self.db = sqlite3.connect(db_name)
            self.cur = self.db.cursor()
            self.cur.execute("CREATE TABLE IF NOT EXISTS ocr(url varchar(200) primary key, raw text, code text)")
            self.upgradeDb()
            return True
        except Exception as e:
            print(str(e))
            return False
        
    def upgradeDb(self):
        if self.cur and self.db_dir:
            try:
                self.cur.execute(
                    "update ocr set url = replace(replace(url, ?, ''), char(92), '/') where url like ?",
                    (self.db_dir, f'{self.db_dir}%')
                )
                if self.cur.rowcount > 0:
                    print(f"数据库升级完成，影响行数{self.cur.rowcount}。")
                    self.db.commit()
            except Exception as e:
                print(f"升级数据库失败: {str(e)}")

    def __del__(self):
        if self.cur:
            self.cur.close()
        if self.db:
            self.db.commit()
            self.db.close()

    def update(self, item):
        if self.cur:
            item[0] = self.normalize_db_path(item[0])
            self.cur.execute("INSERT OR REPLACE INTO ocr(url, raw, code) VALUES (?, ?, ?)", item)
            self.db.commit()


    def fetch_all(self):
        if self.cur:
            self.cur.execute(f'SELECT * FROM ocr')
            return self.cur.fetchall()
        return []

    def find(self, url):
        if self.cur:
            url = self.normalize_db_path(url)
            self.cur.execute(f'SELECT * FROM ocr WHERE url=?', (url,))
            return self.cur.fetchone()
        return None

    def remove(self, url):
        if self.cur:
            url = self.normalize_db_path(url)
            self.cur.execute("DELETE FROM ocr WHERE url=?", (url,))
            self.db.commit()
    
    def ocr(self, image):
        image_url = ""
        ret = None
        if isinstance(image, (str, Path)):
            image_url = str(image)
            if not image_url.startswith("http://") and not image_url.startswith("https://"):
                # Local file path: read and convert to data URI.
                path = Path(image_url)
                if not path.exists():
                    raise FileNotFoundError(f"File not found: {path}")
                file_bytes = path.read_bytes()
                b64 = base64.b64encode(file_bytes).decode("utf-8")
                mime = _sniff_mime_from_bytes(file_bytes)
                image_url = _as_data_uri(mime, b64)
            print(f"ocr image: {image}")
        elif hasattr(image, "save"):
            # PIL Image-like object: save to bytes and convert to data URI.
            buf = BytesIO()
            image.save(buf, format="PNG")
            print(f"ocr image: {image.width}x{image.height}")
            file_bytes = buf.getvalue()
            mime = _sniff_mime_from_bytes(file_bytes)
            image_url = _as_data_uri(mime, base64.b64encode(file_bytes).decode("utf-8"))
        else:
            raise TypeError("image must be URL/path string, pathlib.Path, or PIL Image-like object")
                    
        # 调用布局解析 API 
        """ https://docs.bigmodel.cn/cn/guide/models/vlm/glm-ocr#curl
        curl --location --request POST 'https://open.bigmodel.cn/api/paas/v4/layout_parsing' \
        --header 'Authorization: your_api_key' \
        --header 'Content-Type: application/json' \
        --data-raw '{
          "model": "glm-ocr",
          "file": "https://cdn.bigmodel.cn/static/logo/introduction.png"
        }'
        """
        response = requests.post("https://open.bigmodel.cn/api/paas/v4/layout_parsing", 
            headers={"Authorization": self.api_key}, 
            json={"model": "glm-ocr", "file": image_url})
        # 检查响应状态码并解析 JSON 数据
        if response.status_code == 200:
            data = response.json()
            # 输出结果 response.md_results.replace("\n\n", "\n")
            md_results = data.get("md_results", "")
            ret = md_results.replace("\n\n", "\n")
        else:
            print("请求失败，状态码:", response.status_code)
        return ret
    
    def normalize_code(self, code):
        # 这里可以添加更多的正则表达式来处理不同的代码格式问题
        return code.replace("（", "(").replace("）", ")").replace("；", ";").replace(" ( ", "(").replace(" )", ")").replace(" ;", ";")

    def html2md(self, html):
        return md(html, table_infer_header=True)

    def ocr_code(self, image, path=None):
        ret = self.ocr(image)
        if not path:
            path = str(image)
        return self.analyze(ret, path)

    def analyze(self, raw, path):
        code = ''
        # table替换
        if raw.find('<table') != -1 and raw.find('</table>') != -1:
            code = self.html2md(raw)
        elif -1 != raw.find('```'):
            # 判断markdown中是否包含代码块，如果有则直接返回代码块内容        
            start = raw.find('```')
            end = raw.find('```', start + 3)
            if end != -1:
                code = self.normalize_code(raw[start:end+3])
        elif raw.startswith('$') and raw.endswith('$'): # 数学公式
            code = raw
        else:
            # 采用关键字判断代码
            if self.pattern.search(raw):
                raw = self.normalize_code(raw)
                code = '```\n' + raw + '\n```'
        ret = [path, raw, code]
        if path and len(raw):
            self.update(ret)
        return ret

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("请提供图片文件路径或URL作为参数。")
        sys.exit(1)
        
    ocr = ZaiOcr()
    ocr.initDb("ocr.db")
    result = ocr.ocr_code(sys.argv[1])
    print(result[2])

    # print(ocr.fetch_all())