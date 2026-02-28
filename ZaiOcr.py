# pip install zai-sdk
from zai import ZhipuAiClient
import sys
import base64
from pathlib import Path

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
    def __init__(self, api_key):
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
        response = self.client.layout_parsing.create(
            model="glm-ocr",
            file=image_url
        )

        # 输出结果
        return response.md_results.replace("\n\n", "\n")
    
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("请提供图片文件路径或URL作为参数。")
        sys.exit(1)
        
    ocr = ZaiOcr('access_token')
    result = ocr.ocr(sys.argv[1])
    print(result)