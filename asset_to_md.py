import subprocess
import sys
import os

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'}
def find_asset_files(asset_dir):
    asset_files = []
    for root, _, files in os.walk(asset_dir):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                asset_files.append(f)
    print(f"{asset_dir} Found {len(asset_files)} asset files.")
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
    return str.strip()


def main():
    if len(sys.argv) < 2:
        print("请提供 assets 文件路径作为参数。")
        sys.exit(1)
    ASSET_DIR = sys.argv[1]
    md_path = os.path.join(ASSET_DIR, 'files.md')
    
    asset_files = find_asset_files(ASSET_DIR)
    if len(asset_files) == 0:
        print("没有找到任何图片文件。")
        sys.exit(0)

    total = len(asset_files)
    with open(md_path, 'w', encoding='utf-8') as f:
        for pos in range(total):
            img = asset_files[pos]
            print(f"正在处理图片 {pos+1}/{total}: {img}")
            ocr_text = run_ocr(img)
            print(ocr_text)
            if len(ocr_text) > 0:
                if not ocr_text.startswith('```'):
                    ocr_text = '```\n' + ocr_text  # 添加代码块开始标记
                if not ocr_text.endswith('```'):
                    ocr_text += '\n```'  # 添加代码块结束标记
                f.write(f"- ![]({img})\n\n{ocr_text}\n\n")
            else:
                print("未识别到文本。\n")
                
if __name__ == '__main__':
    main()