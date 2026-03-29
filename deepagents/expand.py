EXPAND_EXECUTE_TOOL_DESCRIPTION = """在隔离沙箱环境（Python 3.12）中执行 **Python** 命令。

**执行前，请按以下步骤操作：**

**1. 目录验证：**
- 若命令会创建新目录或文件，请先使用 `ls` 工具确认父目录存在且路径正确

**2. 命令选择 — 按顺序匹配第一条适用规则：**

- 若 skill 文档提供 `scripts/script.py`：
  ```
  execute(command="python /skills/<skill_name>/scripts/script.py [args...]")
  ```
- 代码包含多行 / 缩进 / 多语句时：
  ```
  execute(command="python << 'EOF'\n<多行pyscript>\nEOF")
  ```
- 代码严格为单行表达式时：
  ```
  execute(command="python -c \"<单行pyscript>\"")
  ```
  > ⚠️ `python -c` **绝对禁止**用于多行代码。

**3. 依赖管理**仅允许：
```
execute(command="python -m pip install <pkg>")
execute(command="python -m pip list")
execute(command="python -m pip show <pkg>")
```

**使用说明：**
- 路径中含空格时，必须使用双引号包裹（如 `python "/path/with spaces/script.py"`）
- 返回 stdout/stderr 合并输出及 exit code；输出过大时可能被截断
- 长时间运行的命令可使用 timeout 参数（如 `execute(command="python script.py", timeout=300)`）
- 命令间依赖时用 `&&`，无依赖时用 `;`
- 全程使用绝对路径，避免使用 `cd`
- 推荐：脚本放 `/scripts/`，输出放 `/outputs/`"""

EXPAND_TOOL_DESCRIPTION = {
    "execute": EXPAND_EXECUTE_TOOL_DESCRIPTION
}
