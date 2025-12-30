deepagents 内置工具:

工具 | 来源 | 用途 |
|-----|------|------|
| `task()` | SubAgentMiddleware | 委托任务给子代理 |
| `write_todos`, `read_todos` | TodoListMiddleware | 任务规划 |
| `ls`, `read_file`, `write_file`, `edit_file` | FilesystemMiddleware | 文件操作 |
| `think_tool` | 自定义 | 深度思考 |
| `tavily_search` | 自定义 | 网络搜索