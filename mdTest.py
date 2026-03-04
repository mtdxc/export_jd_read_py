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

# 测试表格输出
table_content = "<table><tr><td>术语</td><td>解释</td></tr><tr><td>固定优先级</td><td>描述为“固定优先级”的调度算法不会改变分配给被调度任务的优先级，但也不会阻止任务改变自己或其他任务的优先级</td></tr><tr><td>抢占式</td><td>如果一个任务的优先级高于运行状态的任务，而且该高优先级任务已进入就绪状态，抢占式调度算法会立即“抢占”运行状态的任务。被抢占意味着非自愿地（没有明确地让步或阻塞）从运行状态 转换到了就绪状态，从而允许不同任务进入运行状态</td></tr><tr><td>时间片</td><td>使用时间片在同等优先级的任务之间共享处理时间，即使任务没有明确地让步或进入阻塞状态。如果有其他就绪状态的任务与运行 任务具有相同优先级，那么描述为使用“时间片”的调度算法将在每个时间片结束时选择新任务进入运行状态。时间片等于实时操作系统两个滴答中断之间的时间</td></tr></table>"
print(md(table_content, table_infer_header=True))

# 这个格式不行
print(h.handle(table_content))
