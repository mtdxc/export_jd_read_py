# https://zhuanlan.zhihu.com/p/1891202552101576893

from markdownify import markdownify as md

html_content = """<h1>标题</h1><p>这是一个<a href='https://example.com'>链接</a></p>"""
markdown_content = md(html_content, heading_style="ATX")  # 自定义标题风格为ATX
print(markdown_content)

import html2text

print("----------------\n")

h = html2text.HTML2Text()
# h.ignore_links = True  # 忽略链接
markdown = h.handle("<p>Hello <a href='http://example.com'>world</a>!</p>")
print(markdown)