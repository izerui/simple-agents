## 附录：工具汇总表

| # | 工具名称 | 类型 | 提供者 | 传递方式 | 功能说明 | 自动注入 |
|---|---------|------|--------|---------|----------|---------|
| 1 | `think_tool` | 自定义 | `core/tools/think.py` | 显式传递 | 用于研究进度和决策的战略反思工具 | ❌ |
| 2 | `fetch_markdown` | 自定义 | `core/tools/fetch.py` | 显式传递 | 从 URL 获取内容并将 HTML 转换为 Markdown | ❌ |
| 3 | `convert_to_markdown` | 自定义 | `core/tools/converts.py` | 显式传递 | 将 PDF 文件转换为 Markdown，保留标题、段落、图片 | ❌ |
| 4 | `convert_docx_to_markdown` | 自定义 | `core/tools/converts.py` | 显式传递 | 将 DOCX 文件转换为 Markdown，保留标题、段落、表格 | ❌ |
| 5 | `ls` | 内置 | `FilesystemMiddleware` | 自动注入 | 列出指定目录中的文件和子目录 | ✅ |
| 6 | `read_file` | 内置 | `FilesystemMiddleware` | 自动注入 | 读取文件内容，支持分页读取 | ✅ |
| 7 | `write_file` | 内置 | `FilesystemMiddleware` | 自动注入 | 将内容写入指定文件，覆盖现有内容 | ✅ |
| 8 | `edit_file` | 内置 | `FilesystemMiddleware` | 自动注入 | 编辑文件，支持字符串替换操作 | ✅ |
| 9 | `glob` | 内置 | `FilesystemMiddleware` | 自动注入 | 使用模式匹配查找文件（如 `**/*.py`） | ✅ |
| 10 | `grep` | 内置 | `FilesystemMiddleware` | 自动注入 | 在文件中搜索文本模式（支持正则表达式） | ✅ |
| 11 | `execute` | 内置 | `FilesystemMiddleware` | 自动注入 | 在沙箱环境中运行 shell 命令 | ✅ (条件) |
| 12 | `write_todos` | 中间件 | `TodoListMiddleware` | 自动注入 | 管理待办事项列表，用于任务规划和跟踪 | ✅ |
| 13 | `task` | 中间件 | `SubAgentMiddleware` | 自动注入 | 调用子代理执行特定任务，实现上下文隔离 | ✅ |