import re
import subprocess
import sys

def extract_image_path(text):
    # 匹配 Markdown 图片路径
    match = re.search(r'代码如下：\n\n!\[\]\(([^)]+)\)', text, re.MULTILINE)
    return match.group(1) if match else None

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
    md_out_path = 'output.md'  # 请根据实际文件名修改
    if len(sys.argv) >= 3:
        md_out_path = sys.argv[2]

    imgs = []
    with open(md_file_path, 'r', encoding='utf-8') as f:
        snippet = f.read()
        imgs = re.findall(r'代码如下：\n\n!\[\]\(([^)]+)\)', snippet, re.MULTILINE)
        imgs = list(set(imgs))  # 去重图片路径
    total = len(imgs)
    for idx in range(total):
        img = imgs[idx]
        print(f"正在处理图片 {idx+1}/{total}: {img}")
        ocr_text = run_ocr(img)
        if len(ocr_text) > 0:
            if not ocr_text.startswith('```'):
                ocr_text = '```\n' + ocr_text  # 添加代码块开始标记
            if not ocr_text.endswith('```'):
                ocr_text += '\n```'  # 添加代码块结束标记
            snippet = replace_image_with_text(snippet, img, ocr_text)

    with open(md_out_path, 'w', encoding='utf-8') as f:
        f.write(snippet)