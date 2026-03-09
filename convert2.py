import re
import subprocess
import sys
import os
from ZaiOcr import ZaiOcr

ASSET_DIR = 'asset'
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'}
def find_asset_files(asset_dir):
    asset_files = []
    for root, _, files in os.walk(asset_dir):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                asset_files.append(os.path.join(root, f))
    print(f"Found {len(asset_files)} asset files.")
    return asset_files

def run_ocr(image_path):
    # 调用 doskey ocr 命令
    cmd = f'ollama run glm-ocr Text Recognition: {image_path}'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8')
    str = result.stdout
    if str.startswith('Added image'):
        pos = str.find('\n')
        # 返回第二行及之后的所有行，如果存在
        str = str[pos+1:] if pos != -1 else ''
    # 去除前后空白字符
    return str.strip()

def replace_image_with_text(text, image_path, ocr_text):
    # 替换 Markdown 图片为识别文本
    pattern = re.escape(f'![]({image_path})')
    return re.sub(pattern, f'![rep]({image_path})\n{ocr_text}', text)

def remove_image_links(text):
    # 移除 Markdown 图片链接
    return re.sub(r'!\[rep\]\(([^)]+)\)', '', text)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("请提供 Markdown 文件路径作为参数。")
        sys.exit(1)
    
    md_file_path = sys.argv[1]
    chdir = os.path.dirname(md_file_path)
    os.chdir(chdir)  # 切换到 Markdown 文件所在目录，确保图片
    md_out_path = 'output.md'  # 请根据实际文件名修改
    if len(sys.argv) >= 3:
        md_out_path = sys.argv[2]

    imgs = []
    with open(md_file_path, 'r', encoding='utf-8') as f:
        snippet = f.read()
        imgs = re.findall(r'!\[\]\(([^)]+)\)', snippet, re.MULTILINE)
        imgs = list(set(imgs))  # 去重图片路径

    total = len(imgs)
    if total == 0:
        print("未找到任何图片链接。")
        sys.exit(0)
        
    with open(md_out_path, 'w', encoding='utf-8') as f:
        ocr = ZaiOcr()
        for idx in range(total):
            img = imgs[idx]
            print(f"正在处理图片 {idx+1}/{total}: {img}")
            try:
                item = ocr.ocr_code(img)
                if item and len(item[2]) > 0:
                    snippet = replace_image_with_text(snippet, img, item[2])
            except Exception as e:
                print(f"处理图片 {img} 时发生错误: {str(e)}\n", file=sys.stderr)
            if idx % 10 == 0:  # 每处理10张图片就写入一次文件，避免内存占用过大
                f.seek(0)
                f.write(snippet)
        f.seek(0)
        f.write(snippet)