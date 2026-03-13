# pip install zai-sdk
from zai import ZhipuAiClient
import sys
import base64
from pathlib import Path
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
        self.client = ZhipuAiClient(api_key=api_key)
        self.cur = None

    def initDb(self, db_name):
        try:
            self.db = sqlite3.connect(db_name)
            self.cur = self.db.cursor()
            self.cur.execute("CREATE TABLE IF NOT EXISTS ocr(url varchar(200) primary key, raw text, code text)")
            return True
        except Exception as e:
            print(str(e))
            return False

    def __del__(self):
        if self.cur:
            self.cur.close()
        if self.db:
            self.db.commit()
            self.db.close()

    def update(self, item):
        if self.cur:
            self.cur.execute("INSERT OR REPLACE INTO ocr(url, raw, code) VALUES (?, ?, ?)", item)
            self.db.commit()


    def fetch_all(self):
        if self.cur:
            self.cur.execute(f'SELECT * FROM ocr')
            return self.cur.fetchall()
        return []

    def find(self, url):
        if self.cur:
            url = str(url)
            self.cur.execute(f'SELECT * FROM ocr WHERE url=?', (url,))
            return self.cur.fetchone()
        return None

    def remove(self, url):
        if self.cur:
            url = str(url)
            self.cur.execute("DELETE FROM ocr WHERE url=?", (url,))
            self.db.commit()

    def ocr(self, image, insert_db=True):
        image_url = ""
        if isinstance(image, (str, Path)):
            image_url = str(image)
            print(f"ocr image: {image_url}")
            if not image_url.startswith("http://") and not image_url.startswith("https://"):
                # Local file path: read and convert to data URI.
                path = Path(image_url)
                if not path.exists():
                    raise FileNotFoundError(f"File not found: {path}")
                file_bytes = path.read_bytes()
                b64 = base64.b64encode(file_bytes).decode("utf-8")
                mime = _sniff_mime_from_bytes(file_bytes)
                image_url = _as_data_uri(mime, b64)
        elif hasattr(image, "save"):
            # PIL Image-like object: save to bytes and convert to data URI.
            buf = BytesIO()
            image.save(buf, format="PNG")
            file_bytes = buf.getvalue()
            mime = _sniff_mime_from_bytes(file_bytes)
            image_url = _as_data_uri(mime, base64.b64encode(file_bytes).decode("utf-8"))
            insert_db = False  # 不直接存储data URI到数据库
        else:
            raise TypeError("image must be URL/path string, pathlib.Path, or PIL Image-like object")
                    
        # 调用布局解析 API
        response = self.client.layout_parsing.create(
            model="glm-ocr",
            file=image_url
        )

        # 输出结果
        ret = response.md_results.replace("\n\n", "\n")
        if insert_db and len(ret):
            self.insert(str(path), ret)
        return ret
    
    def normalize_code(self, code):
        # 这里可以添加更多的正则表达式来处理不同的代码格式问题
        return code.replace("（", "(").replace("）", ")").replace("；", ";").replace(" ( ", "(").replace(" )", ")").replace(" ;", ";")

    def html2md(self, html):
        return md(html, table_infer_header=True)

    def ocr_code(self, image_url):
        ret = None
        code = ''
        image_url = str(image_url)
        raw = self.ocr(image_url, False)
        # table替换
        if raw.find('<table') != -1 and raw.find('</table>') != -1:
            code = self.html2md(raw)
        elif -1 != raw.find('```'):
            # 判断markdown中是否包含代码块，如果有则直接返回代码块内容        
            start = raw.find('```')
            end = raw.find('```', start + 3)
            if end != -1:
                code = self.normalize_code(raw[start:end+3])
        else:
            # 采用关键字判断代码
            if re.search(r'(if|else|for|while|uint|void|function|def|class|import|return|switch|case|break|continue|try|catch|finally|var|let|const|public|private|static)', raw):
                raw = self.normalize_code(raw)
                code = '```\n' + raw + '\n```'
        if len(raw):
            ret = (image_url, raw, code)
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