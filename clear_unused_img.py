import os
import re

ASSET_DIR = 'asset'
MD_DIR = '.'
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'}

def find_md_files(md_dir):
    md_files = []
    for root, _, files in os.walk(md_dir):
        for f in files:
            if f.endswith('.md'):
                md_files.append(os.path.join(root, f))
    print(f"Found {len(md_files)} markdown files.")
    return md_files

def find_asset_files(asset_dir):
    asset_files = []
    for root, _, files in os.walk(asset_dir):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                asset_files.append(os.path.join(root, f))
    print(f"Found {len(asset_files)} asset files.")
    return asset_files

def find_referenced_assets(md_files):
    referenced = set()
    pattern = re.compile(r'!\[.*?\]\((.*?)\)')
    for md_file in md_files:
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()
            for match in pattern.findall(content):
                referenced.add(os.path.normpath(match))
    return referenced

def main():
    md_files = find_md_files(MD_DIR)
    asset_files = find_asset_files(ASSET_DIR)
    referenced_assets = find_referenced_assets(md_files)

    unused_files = []
    for asset_file in asset_files:
        rel_path = os.path.relpath(asset_file, start=MD_DIR)
        if rel_path not in referenced_assets:
            unused_files.append(asset_file)

    print(f"Found {len(unused_files)} unused asset files.")
    for f in unused_files:
        print(f"Deleting: {f}")
        os.remove(f)

if __name__ == '__main__':
    main()