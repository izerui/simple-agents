# Changelog

## [0.4.4] - 2026-03-01

### Breaking Changes

- **删除测试目录**: 移除了 `tests/` 目录下的所有单元测试和集成测试
- **删除 pyproject.toml 和 uv.lock**: 不再将这些文件包含在包中
- **删除 Makefile**: 移除了构建和测试命令
- **删除 README.md**: 不再在包中包含 README
- **删除 scripts/check_imports.py**: 移除了导入检查脚本

### New Features

- **新增 base_prompt.md**: 添加了完整的基础代理提示文件，包含核心行为指南、工具使用规范和最佳实践
- **版本升级**: 从 0.3.12 升级到 0.4.4

### Improvements

#### Backends

- **CompositeBackend**:
  - 添加了 `execute` 方法的 `timeout` 参数支持
  - 优化了路径路由逻辑，提取了 `_route_for_path` 函数
  - 改进了 `_remap_grep_path` 和 `_remap_file_info_path` 辅助函数
  - 优化了文件操作的路径处理

- **FilesystemBackend**:
  - `virtual_mode` 参数现在默认为 `None`，会发出弃用警告
  - 添加了 `_to_virtual_path` 方法改进路径转换
  - 改进了虚拟模式下的路径验证和错误处理
  - 优化了 glob 和 grep 操作的路径处理

- **Protocol**:
  - 添加了 `execute_accepts_timeout` 函数用于检查后端是否支持超时参数

#### Middleware

- **SummarizationMiddleware**:
  - 重写为 `_DeepAgentsSummarizationMiddleware`，基于新的 AgentMiddleware 接口
  - 添加了 `SummarizationState` 状态模式和 `SummarizationEvent` 事件类型
  - 添加了 `compact_conversation` 工具支持
  - 改进了消息截断和参数截断逻辑
  - 添加了 `wrap_model_call` 方法用于处理模型调用

- **FilesystemMiddleware**: 改进文件操作和路径处理

#### Graph

- **BASE_AGENT_PROMPT**: 扩展并改进了基础代理提示，包含:
  - 核心行为准则
  - 专业客观性指南
  - 任务执行流程（理解 -> 行动 -> 验证）
  - 进度更新规范
  - 工具使用最佳实践

- **OpenAI 模型支持**: 添加了 `openai:` 前缀的模型初始化逻辑，自动使用 Responses API

- **SubAgent 处理**: 改进了子代理的模型初始化和中间件配置

### Bug Fixes

- 修复了 CompositeBackend 中路径路由的边界情况
- 改进了 FilesystemBackend 在虚拟模式下的路径验证
- 修复了 summarization 中消息处理的边缘情况：
  - 添加了 `_apply_event_to_messages` 防御性检查，处理畸形事件数据和 cutoff 索引越界
  - 新增 `_compute_state_cutoff` 方法正确计算链式 summarization 的状态索引
