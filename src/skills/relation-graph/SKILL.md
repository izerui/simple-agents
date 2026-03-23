---
name: relation-graph
description: 生成或增量修改可直接导入前端的知识建模图 JSON。适用于把课程知识点、层级、关系、步骤链、案例、策略等内容转成最终图数据，并在需要时稳定调整布局。
---

# Relation Graph

## 1. 文档定位

本手册用于规范知识建模图的生成、增量修改、校验与导出过程。

本 skill 的唯一目标是生成最终可用的知识建模图结果，不输出草稿结构、半成品字段或临时替代产物。

## 2. 适用范围

出现以下任一情况时，必须使用本 skill：
- 从知识点文本、课程内容、章节提纲生成知识建模图
- 修改已有知识建模图
- 追加节点、关系、步骤链、案例、策略节点
- 调整图结构但仍需输出最终可导入 JSON
- 当前工作区已存在可编辑的 `graph.md`
- 用户提供了现有知识建模图 JSON

## 3. 职责边界

本 skill 负责以下事项：
- 生成或增量修改 `graph.md`
- 校验 `graph.md`
- 基于 `graph.md` 生成最终 `result.json`
- 在已有 `graph.md` 或已有图谱 JSON 的情况下执行稳定的增量修改流程
- 按既定格式、字段、布局和文件要求完成落盘

本 skill 不负责以下事项：
- 课程信息追问
- 教学目标澄清
- 知识点粒度协商
- 课程类型判断
- 教学质量目标设定

上述事项由上层提示词负责；一旦进入图谱生成或修改阶段，凡涉及执行细节，均以本手册为准。

## 4. 交付物与默认路径

默认交付物如下：
- 中间文件：`/output/graph.md`
- 最终文件：`/output/result.json`

路径要求如下：
- `/output/` 指当前任务工作目录下的输出目录，不是技能目录
- `graph.md` 默认写入 `/output/graph.md`
- `result.json` 默认写入 `/output/result.json`
- 不得写入技能目录或其他未约定路径

## 5. 总体执行原则

执行本 skill 时，必须遵守以下原则：
- 唯一主流程必须是：生成或修改 `graph.md` -> 校验 `graph.md` -> 生成 `result.json`
- 不允许绕过 `graph.md` 直接手写最终 `result.json`
- 不允许直接修改 `result.json` 作为修正手段
- 不允许在已有可编辑 `graph.md` 的情况下脱离原文件另起一版
- 不允许在用户提供现有图谱 JSON 后，不经转换直接重做整图
- 若任一步失败，只能回到 `graph.md` 继续修改，再重新执行后续步骤

## 6. 资源与脚本使用规范

执行本 skill 时，必须按以下顺序读取参考资源并调用脚本。

### 6.1 布局参考文件

资源：`references/layout.md`

执行要求：
- 任何需要生成或调整 `x/y/width/height`、阅读路径、分区布局、连线拓扑的任务，必须先读取该文件

### 6.2 样例参考文件

资源：`references/example.md`

执行要求：
- 需要参考节点密度、分区方式、外围挂接方式和坐标尺度时，可以读取

### 6.3 校验脚本

脚本：`scripts/validate_graph.py`

执行要求：
- 在生成 `result.json` 之前，必须先执行该脚本校验 `graph.md`
- 该脚本只负责校验 `graph.md`，不负责生成最终结果
- 校验不通过时，必须立即停止后续生成，并回到 `graph.md` 修改

标准命令：

```bash
python /skills/relation-graph/scripts/validate_graph.py /output/graph.md
```

### 6.4 生成脚本

脚本：`scripts/build_graph.py`

执行要求：
- 只有在 `graph.md` 已通过 `validate_graph.py` 校验后，才允许执行该脚本
- 该脚本只负责基于 `graph.md` 生成最终 `result.json`
- 该脚本只接受文件路径参数

标准命令：

```bash
python /skills/relation-graph/scripts/build_graph.py /output/graph.md --output /output/result.json --pretty
```

### 6.5 反向转换脚本

脚本：`scripts/reverse_json_to_md.py`

执行要求：
- 用户提供现有知识建模图 JSON 时，必须先执行该脚本将其转换为可编辑的 `graph.md`
- 转换完成后，后续所有修改都必须基于该 `graph.md` 进行

标准命令：

```bash
python /skills/relation-graph/scripts/reverse_json_to_md.py /output/result.json --output /output/graph.md
```

## 7. 脚本调用强制规范

生成最终结果时，只允许调用本 skill 提供的现有脚本。

### 7.1 唯一允许的标准执行方式

```bash
# 1. 校验 graph.md
python /skills/relation-graph/scripts/validate_graph.py /output/graph.md

# 2. 校验通过后生成 result.json
python /skills/relation-graph/scripts/build_graph.py /output/graph.md --output /output/result.json --pretty
```

若用户提供了现有 JSON，需要先反向转换：

```bash
python /skills/relation-graph/scripts/reverse_json_to_md.py /output/result.json --output /output/graph.md
```

### 7.2 参数规则

- `validate_graph.py` 只接受一个参数：`graph.md` 文件路径
- `build_graph.py` 只接受 `graph.md` 文件路径，以及 `--output` 指定输出文件路径
- `reverse_json_to_md.py` 只接受现有 JSON 文件路径，以及 `--output` 指定输出文件路径
- 输入输出必须是实际文件路径，不接受内联内容、stdin、字符串拼装内容或临时对象

### 7.3 明确禁止事项

禁止以下做法：
- 使用 `python <<EOF`、heredoc、内联 Python 或临时 `.py` 脚本解析 `graph.md`
- 自行编写 JSON 拼装逻辑替代 `build_graph.py`
- 绕过 `validate_graph.py` 直接生成最终结果
- 绕过 `build_graph.py` 手写或拼接 `result.json`
- 使用与本 skill 无关的其他脚本、工具或自定义命令替代上述脚本

错误示例：

```bash
# 错误：使用 heredoc 临时解析 graph.md
python <<'EOF'
print('temporary script')
EOF

# 错误：自己编写脚本拼接 result.json
python custom_build_result.py /output/graph.md

# 错误：直接手写或覆盖最终结果
echo '{}' > /output/result.json
```

## 8. `graph.md` 文件规范

### 8.1 基本要求

在进入生成流程前，必须一次性生成完整可用的 `graph.md`，不得先写半成品再指望后续补齐。

固定表头如下：

```text
| NodeID | NodeText | NodeType | ParentID | RelationText | NodeX | NodeY | NodeWidth | NodeHeight | NodeSemantic |
```

### 8.2 表结构要求

- `graph.md` 必须是一张单一 Markdown 表
- 第一行必须是固定表头，不得改列名、列顺序、列数量
- 第二行必须是 Markdown 分隔行
- 第三行起每行表示一个节点定义及其父关系记录
- 不允许生成第二张表
- 不允许把节点写成列表、段落、JSON 片段或半结构化草稿
- 节点文本和关系名称中不得出现 `|`
- 数值字段只能填写数字，不得带单位、注释或额外文本

### 8.3 字段约束

- `NodeID` 非空
- 默认优先使用单父节点结构
- 只有在确有必要且无法通过重构语义层级解决时，才允许同一个 `NodeID` 重复出现表达多个父节点
- 同一个 `NodeID` 重复出现时，`NodeText`、`NodeType`、`NodeX`、`NodeY`、`NodeWidth`、`NodeHeight`、`NodeSemantic` 必须完全一致
- `NodeText` 非空，不允许换行
- `NodeType` 只能填写 `DK`、`PK`、`CS`、`FC`
- `ParentID` 与 `RelationText` 必须同时为空，或同时非空
- `ParentID` 如填写，必须引用表内有效节点
- `RelationText` 如填写，不允许换行
- `RelationText` 只能使用以下 10 个关系名：
  - `包含`
  - `组成`
  - `构成`
  - `是一种`
  - `具有属性`
  - `具有特征`
  - `定义`
  - `并列`
  - `是前提`
  - `支持`
- `NodeX`、`NodeY`、`NodeWidth`、`NodeHeight` 必须是数字
- `NodeSemantic` 只能填写以下 4 个值：
  - `核心知识点`
  - `核心结构化知识框架`
  - `先决知识点`
  - `普通知识点`

### 8.4 显示与尺寸约定

- 节点文字字号固定按 `12` 理解
- 连线关系文字字号固定按 `10` 理解
- 估算 `NodeWidth/NodeHeight` 和安排布局时，必须把上述字号对应的文本占位算进去
- 必须先按文本长度和显示占位估算 `NodeWidth/NodeHeight`
- 必须再基于节点实际占位安排 `NodeX/NodeY`
- 不允许先拍坐标再压缩节点尺寸

### 8.5 完整性要求

- 必须先确定语义结构，再填写布局字段

### 8.6 最小合法样本

```md
| NodeID | NodeText | NodeType | ParentID | RelationText | NodeX | NodeY | NodeWidth | NodeHeight | NodeSemantic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| root-1 | 函数 | DK |  |  | 0 | 0 | 88 | 36 | 核心结构化知识框架 |
| node-1 | 概念定义 | DK | root-1 | 包含 | -180 | 120 | 72 | 36 | 普通知识点 |
| node-2 | 分类 | DK | root-1 | 包含 | 140 | 120 | 72 | 36 | 普通知识点 |
| node-3 | 示例 | FC | root-1 | 支持 | 220 | 240 | 88 | 40 | 普通知识点 |
| node-4 | 使用步骤 | PK | root-1 | 包含 | -40 | 220 | 96 | 40 | 核心结构化知识框架 |
| node-5 | 明确参数 | PK | node-4 | 包含 | -40 | 300 | 96 | 40 | 普通知识点 |
| node-6 | 调用函数 | PK | node-4 | 包含 | -40 | 360 | 96 | 40 | 普通知识点 |
| node-7 | 复盘检查 | CS | root-1 | 支持 | 320 | 320 | 96 | 40 | 普通知识点 |
```

## 9. 布局规范

生成坐标前，必须先读取 `references/layout.md`。

执行要求：
- 生成或调整 `NodeX`、`NodeY`、`NodeWidth`、`NodeHeight` 时，必须以 `references/layout.md` 作为唯一布局依据
- `x/y/width/height` 的取值必须按 `references/layout.md` 的规则统筹生成，不得脱离该文件自行另定布局标准

## 10. 执行流程

### 10.1 场景判定

#### 新建场景

满足以下条件时，按新建处理：
- 用户未提供现有图 JSON
- 当前不存在可复用的 `graph.md`

#### 增量场景

满足以下任一条件时，按增量处理：
- 当前已存在可编辑的 `graph.md`
- 用户提供了现有图 JSON

### 10.2 新建流程

新建流程必须按以下顺序执行：
1. 识别语义骨架
2. 依据布局规则规划坐标
3. 生成完整的 `graph.md`
4. 执行 `validate_graph.py`
5. 执行 `build_graph.py`

### 10.3 增量流程

增量流程必须按以下顺序执行：
1. 若已有可编辑 `graph.md`，直接基于该文件修改
2. 若用户提供现有 JSON，先执行 `reverse_json_to_md.py` 转成 `graph.md`
3. 所有修改均在该 `graph.md` 上完成
4. 执行 `validate_graph.py`
5. 执行 `build_graph.py`

### 10.4 增量修改稳定性要求

增量修改时，稳定性优先于重排美观。

必须遵守以下要求：
- 未被明确要求改动的旧节点、旧关系、旧坐标、旧尺寸应尽量保持不变
- 新增少量节点时，优先采用局部补充和局部挪位
- 不得为少量新增内容整体重排全图
- 若必须调整局部布局，应优先保证原有主干阅读路径和分区语义稳定

### 10.5 仅布局调整模式

仅当用户明确表示“知识点和语义关系已确认，只需要调整布局”时，才允许进入仅布局调整模式。

进入该模式后：
- 允许修改字段：`NodeX`、`NodeY`、`NodeWidth`、`NodeHeight`
- 默认不修改字段：`NodeID`、`NodeText`、`NodeType`、`ParentID`、`RelationText`、`NodeSemantic`

若用户后续明确要求修改知识点内容、关系语义或结构层级，必须退出仅布局调整模式，恢复正常增量修改流程。

## 11. 失败处理

- `validate_graph.py` 校验失败时，不得继续执行生成步骤，必须回到 `graph.md` 修正
- `build_graph.py` 生成失败时，不得手工拼接或修补最终 JSON，必须回到 `graph.md` 修正后重新生成
- `build_graph.py` 生成失败时，不得覆盖已有 `result.json`；只有成功生成后，才允许覆盖目标结果文件
- `graph.md` 始终是唯一可编辑事实来源，`result.json` 只是由其生成的最终产物

## 12. 交付前检查

交付前至少确认以下事项：
1. 已读取 `references/layout.md`
2. 已先生成 `/output/graph.md`
3. 已使用 `scripts/validate_graph.py` 校验 `graph.md`
4. 若已有可编辑的 `graph.md`，已优先在该文件基础上修改
5. 若用户提供了现有建模图 JSON，已先使用 `scripts/reverse_json_to_md.py` 转成 `graph.md`
6. 已使用 `scripts/build_graph.py` 生成最终 JSON
7. 结果文件已写入 `/output/result.json` 或用户通过 `--output` 指定的合法路径
8. 若为增量修改，未改动部分已尽量保持稳定
9. 若用户明确要求仅调整布局，已切换到仅布局调整模式

## 13. 交付要求

默认交付方式如下：
- `/output/graph.md`
- `/output/result.json`

回复用户时应遵守以下要求：
- 以结果完成情况为主
- 不得用长篇解释替代最终文件
- 如用户额外要求说明，可附极简说明
