# pip install zai-sdk
from zai import ZhipuAiClient
import sys
import base64
from pathlib import Path
import os
from markdownify import markdownify as md
import re

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
        
    def ocr(self, image_url):
        if not image_url.startswith("http://") and not image_url.startswith("https://"):
            # If it's a file path, read and encode
            path = Path(image_url)
            if not path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            file_bytes = path.read_bytes()
            b64 = base64.b64encode(file_bytes).decode("utf-8")
            mime = _sniff_mime_from_bytes(file_bytes)
            image_url = _as_data_uri(mime, b64)
                    
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
        response = self.client.layout_parsing.create(
            model="glm-ocr",
            file=image_url
        )

        # 输出结果
        return response.md_results.replace("\n\n", "\n")

    def normalize_code(self, code):
        # 这里可以添加更多的正则表达式来处理不同的代码格式问题
        return code.replace("（", "(").replace("）", ")").replace("；", ";").replace(" ( ", "(").replace(" )", ")").replace(" ;", ";")

    def ocr_code(self, image_url):
        md_result = self.ocr(image_url)
        # table替换
        if md_result.startswith('<table'):
            return md(md_result, table_infer_header=True)

        # 判断markdown中是否包含代码块，如果有则直接返回代码块内容        
        start = md_result.find('```')
        if start != -1:
            end = md_result.find('```', start + 3)
            if end != -1:
                return self.normalize_code(md_result[start:end+3])

        # 采用关键字判断代码
        if re.search(r'(if|else|for|while|uint|void|function|def|class|import|return|switch|case|break|continue|try|catch|finally|var|let|const|public|private|static)', md_result):
            md_result = self.normalize_code(md_result)
            return '```\n' + md_result + '\n```'
        else:
            print(f"unknown code: {image_url}\n{md_result}\n", file=sys.stderr)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("请提供图片文件路径或URL作为参数。")
        sys.exit(1)
        
    ocr = ZaiOcr()
    result = ocr.ocr_code(sys.argv[1])
    print(result)