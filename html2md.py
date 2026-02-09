import os
import json
from markdownify import markdownify as md
Data_Folder = "./output"

def bookToMd(name, folder):
    targetPath = os.path.join(folder, f"Data/{name}.md")   
    with open(targetPath, "w", encoding="utf-8") as output_file:
    
        html_folder = os.path.join(folder, "Data")
        json_path = os.path.join(folder, "index.json")
        if not os.path.exists(json_path):
            print(f"{json_path}不存在,跳过生成")
            return

        with open(json_path, "r") as f:
            jsonArray = json.load(f)
            
        last_chapter_item = ""
        last_chapter_content = ""
        lst_md_content = ""
        for i, it in enumerate(jsonArray):
            print(it)
            chapter_item = it["chapter_item"]  # +".html"
            if chapter_item != last_chapter_item:
                html_path = os.path.join(html_folder, chapter_item)

                #有的html内容一样,但是文件名不同,导致相同md生成
                with open(html_path,encoding='utf-8') as file:
                    chapter_content = file.read()
                    if chapter_content == last_chapter_content:
                        print(f"{i+1}/{len(jsonArray)} 内容相同,跳过")
                        continue
                    last_chapter_content = chapter_content
                    
                markdown_content = md(chapter_content, heading_style="ATX")  # 自定义标题风格为ATX
                if lst_md_content == markdown_content:
                    print(f"{i+1}/{len(jsonArray)} md内容相同,跳过")
                    continue
                else:
                    lst_md_content = markdown_content
                    output_file.write(markdown_content + "\n\n")

            last_chapter_item = chapter_item

    print(f"生成成功:{targetPath}")

def main():
    items = os.listdir(Data_Folder)
    for item in items:
        full_path = os.path.join(Data_Folder, item)
        if os.path.isdir(full_path):
            bookToMd(item, full_path)


if __name__ == "__main__":
    main()
