1. 修改定义: [filesystem.py](../deepagents/middleware/filesystem.py)  EXECUTE_TOOL_DESCRIPTION  line: 199    
2. 定义类: [_summarization_helper.py](../deepagents/middleware/_summarization_helper.py)
3. 增加判断: [skills.py](../deepagents/middleware/skills.py) isinstance(raw_tools, list):  line: 325
4. 覆盖对象: [summarization.py](../deepagents/middleware/summarization.py) self._lc_helper  line: 239