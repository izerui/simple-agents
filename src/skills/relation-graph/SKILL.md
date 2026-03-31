---
name: relation-graph
description: `graph.md` 是知识建模图生成与编辑的唯一文件。适用于从内容新建建模图、基于已有 `graph.md` 继续调整，或先将用户提供的建模图 JSON 反向转换为 `graph.md` 后再调整。
---

# Relation Graph

## 1. 文档定位

本手册用于规范以 `graph.md` 作为唯一事实来源的知识建模图新生成、编辑更新、校验与导出过程。

本 skill 的核心要求是始终围绕 `graph.md` 工作；`graph.md` 是知识建模图生成与编辑的唯一文件，`result.json` 或按序递增的 `result-N.json` 只是由其导出的最终产物，不是编辑对象。

## 2. 适用范围

出现以下任一情况时，必须使用本 skill：
- 从知识点文本、课程内容、章节提纲生成知识建模图
- 修改已有知识建模图
- 追加节点、关系、步骤链、案例、策略节点
- 调整图结构后仍需基于 `graph.md` 生成最终结果
- 当前工作区已存在可编辑的 `graph.md`
- 用户提供了现有知识建模图 JSON

## 3. 职责边界

本 skill 负责以下事项：
- 新生成或编辑更新 `graph.md`
- 校验 `graph.md`
- 在需要交付时基于 `graph.md` 导出最终结果 JSON（默认文件名为 `result.json`，若已存在则顺延为 `result-2.json`、`result-3.json` ...）
- 在已有 `graph.md` 或已有建模图 JSON 的情况下执行稳定的编辑更新流程
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
- 最终文件：`/output/result.json`；若该文件已存在，则自动顺延为 `/output/result-2.json`、`/output/result-3.json` ...

路径要求如下：
- `/output/` 指当前任务工作目录下的输出目录，不是技能目录
- `graph.md` 默认写入 `/output/graph.md`
- 最终结果默认优先写入 `/output/result.json`
- 若 `/output/result.json` 已存在，则必须改为写入当前目录下下一个可用的递增文件名，如 `/output/result-2.json`、`/output/result-3.json`
- 不得写入技能目录或其他未约定路径

## 5. 总体执行原则

执行本 skill 时，必须遵守以下原则：
- 在首次生成 `graph.md` 之前，必须完整阅读本 skill 文档以及本 skill 明确要求的相关参考文件；不得未读完规则就开始生成
- 唯一主流程必须是：生成或修改 `graph.md` -> 校验 `graph.md` -> 生成最终结果 JSON
- 不允许绕过 `graph.md` 直接手写最终结果 JSON（包括 `result.json` 或任意 `result-N.json`）
- 不允许直接修改最终结果 JSON 作为修正手段
- 不允许在已有可编辑 `graph.md` 的情况下脱离原文件另起一版
- 只要用户提供了现有建模图 JSON，就必须先反向转换生成 `graph.md`，再基于该文件继续修改
- 不允许在用户提供现有建模图 JSON 后，不经转换直接重做整图
- 不允许在用户提供现有建模图 JSON 后，再重新生成一份新的 `graph.md` 替代反向转换得到的 `graph.md`
- 若任一步失败，只能回到 `graph.md` 继续修改，再重新执行后续步骤

## 6. 资源与脚本使用规范

执行本 skill 时，必须按以下顺序读取参考资源并调用脚本。

### 6.1 布局参考文件

资源：`references/layout.md`

执行要求：
- 任何需要生成或调整 `x/y/width/height`、阅读路径、分区布局、连线拓扑的任务，必须先读取该文件

### 6.3 校验与布局修复脚本

脚本：`scripts/validate_graph.py`

执行要求：
- 在生成最终结果 JSON 之前，必须先执行该脚本
- 该脚本先做结构与字段硬校验（表结构、字段合法性、父子引用），失败立即报错退出
- 硬校验通过后，脚本自动修复布局坐标：消除子树级别的重叠、保证最小间距、整体居中，并将修正后的坐标直接写回 `graph.md`
- 该脚本校验失败时，必须先修正 `graph.md`，否则不得进入后续步骤

标准命令：

```bash
python /skills/relation-graph/scripts/validate_graph.py /output/graph.md
```

### 6.4 生成脚本

脚本：`scripts/build_graph.py`

执行要求：
- 在完成 `validate_graph.py` 的校验与布局修复后，就允许执行该脚本
- 该脚本只负责基于 `graph.md` 生成最终结果 JSON
- 该脚本只接受文件路径参数

标准命令：

```bash
python /skills/relation-graph/scripts/build_graph.py /output/graph.md --pretty
```

默认行为说明：
- 未显式传入 `--output` 时，脚本优先写入 `/output/result.json`
- 若 `/output/result.json` 已存在，脚本必须自动选择下一个可用文件名，如 `/output/result-2.json`、`/output/result-3.json`

### 6.5 反向转换脚本

脚本：`scripts/reverse_json_to_md.py`

执行要求：
- 用户提供现有知识建模图 JSON 时，必须先执行该脚本将其转换为可编辑的 `graph.md`
- 转换完成后，该 `graph.md` 立即成为后续流程唯一允许编辑的事实来源
- 转换完成后，后续所有修改都必须基于该 `graph.md` 进行
- 不允许跳过该转换结果重新生成一份新的 `graph.md`

标准命令：

```bash
python /skills/relation-graph/scripts/reverse_json_to_md.py /output/result.json --output /output/graph.md
```

说明：
- 若用户提供的现有建模图 JSON 实际文件名为 `result-2.json`、`result-3.json` 或其他合法 JSON 路径，应以用户实际提供路径为准

## 7. 脚本调用强制规范

生成最终结果时，只允许调用本 skill 提供的现有脚本。

### 7.1 唯一允许的标准执行方式

```bash
# 1. 校验 graph.md 并自动修复布局坐标（直接写回 graph.md）
python /skills/relation-graph/scripts/validate_graph.py /output/graph.md

# 2. 生成最终结果 JSON
python /skills/relation-graph/scripts/build_graph.py /output/graph.md --pretty
```

若用户提供了现有建模图 JSON，需要先反向转换：

```bash
python /skills/relation-graph/scripts/reverse_json_to_md.py /output/result.json --output /output/graph.md
```

### 7.2 参数规则

- `validate_graph.py` 只接受一个参数：`graph.md` 文件路径
- `build_graph.py` 只接受 `graph.md` 文件路径，以及 `--output` 指定输出文件路径
- `reverse_json_to_md.py` 只接受现有建模图 JSON 文件路径，以及 `--output` 指定输出文件路径
- 输入输出必须是实际文件路径，不接受内联内容、stdin、字符串拼装内容或临时对象

### 7.3 明确禁止事项

禁止以下做法：
- 使用 `python <<EOF`、heredoc、内联 Python 或临时 `.py` 脚本解析 `graph.md`
- 自行编写 JSON 拼装逻辑替代 `build_graph.py`
- 自行从 Markdown 表格解析节点与关系，再手工拼装 `nodes` / `relations` 结构替代正式结果
- 绕过 `validate_graph.py` 直接生成最终结果
- 绕过 `build_graph.py` 手写或拼接最终结果 JSON
- 使用与本 skill 无关的其他脚本、工具或自定义命令替代上述脚本

错误示例：

```bash
# 错误：使用 heredoc 临时解析 graph.md
python <<'EOF'
print('temporary script')
EOF

# 错误：自己编写脚本拼接最终结果 JSON
python custom_build_result.py /output/graph.md

# 错误：自己解析 Markdown 表格并手工拼 nodes/relations
python <<'EOF'
with open('/output/graph.md', 'r', encoding='utf-8') as f:
    content = f.read()
print('parse markdown and build custom json')
EOF

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
- 单行节点高度默认按 `16` 估算：`12` 号字高 + 上下各 `2` 的边框留白
- 节点宽度必须按文本占位加左右留白估算，不得仅凭经验随意填写
- 必须再基于节点实际占位安排 `NodeX/NodeY`
- 不允许先拍坐标再压缩节点尺寸

### 8.5 完整性要求

- 必须先确定语义结构，再填写布局字段

## 9. 布局规范

生成坐标前，必须先读取 `references/layout.md`。

执行要求：
- 生成或调整 `NodeX`、`NodeY`、`NodeWidth`、`NodeHeight` 时，必须以 `references/layout.md` 作为唯一布局依据
- `x/y/width/height` 的取值必须按 `references/layout.md` 的规则统筹生成，不得脱离该文件自行另定布局标准
- 子节点布局方向必须相对其父节点做放射式外扩，优先形成向四面八方延展的分布，不得把同一父节点的大多数子节点机械地堆在单一方向
- 子节点数量为 `2-3` 时至少覆盖 `2` 个方向，`4-5` 时至少覆盖 `3` 个方向，`>=6` 时至少覆盖 `4` 个方向；不满足视为布局不合格

### 9.1 区块的概念

**区块（Branch Block）** 是指一个节点及其所有后代节点所占据的矩形范围，即该子树的最小外接矩形。

例如节点 A 有子节点 B、C，B 下还有 D：

```text
区块 A = 包围 A、B、C、D 所有节点的最小矩形
区块 B = 包围 B、D 的最小矩形
区块 C = C 节点自身的矩形
```

**区块不重叠**是布局的硬性约束，必须在填写坐标时主动保证：

- 同一父节点下，各子区块之间必须留出至少 `80px` 的可视间距
- 不同一级主干的区块之间，间距不得小于 `80px`
- 判断是否重叠时，必须把整个区块（含所有后代节点）的外接矩形算进去，不能只看当前节点自身的坐标

**常见错误**：只看父节点和直接子节点的坐标，忽略子节点下面还挂有后代节点，导致后代节点的区块伸入了相邻区块的范围。

**正确做法**：为每个子树预估区块高度和宽度（含所有后代），再据此分配各子树的起始坐标，保证区块间有足够间距。

## 10. 执行流程

### 10.1 场景判定

#### 新建场景

满足以下条件时，按新建处理：
- 用户未提供现有建模图 JSON
- 当前不存在可复用的 `graph.md`

只要用户提供了现有建模图 JSON，就不得按新建场景处理。

#### 编辑更新场景

满足以下任一条件时，按编辑更新处理：
- 当前已存在可编辑的 `graph.md`
- 用户提供了现有建模图 JSON

其中：
- 只要新生成流程已经产出了 `graph.md`，后续继续调整时就不再属于新建，而属于编辑更新
- 用户提供了现有建模图 JSON 的优先级高于“是否需要新建”，必须直接进入反向转换后的编辑更新流程

### 10.2 新建流程

新建流程必须按以下顺序执行：
1. 识别语义骨架
2. 依据布局规则规划坐标
3. 生成完整的 `graph.md`
4. 执行 `validate_graph.py`（校验 + 自动修复布局，直接写回 `graph.md`）
5. 执行 `build_graph.py`

### 10.3 编辑更新流程

编辑更新流程必须按以下顺序执行：
1. 若用户提供现有建模图 JSON，必须先执行 `reverse_json_to_md.py` 转成 `graph.md`
2. 反向转换得到的 `graph.md` 必须作为后续修改的唯一基础，不得重新生成新的 `graph.md`
3. 若用户未提供现有建模图 JSON，但已有可编辑 `graph.md`，则直接基于该文件修改
4. 所有修改均在当前唯一有效的 `graph.md` 上完成
5. 执行 `validate_graph.py`（校验 + 自动修复布局，直接写回 `graph.md`）
6. 执行 `build_graph.py`

### 10.4 编辑更新稳定性要求

编辑更新时，稳定性优先于重排美观。

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

若用户后续明确要求修改知识点内容、关系语义或结构层级，必须退出仅布局调整模式，恢复正常编辑更新流程。

## 11. 失败处理

- `validate_graph.py` 硬校验失败时，必须先修正结构与字段问题，再重新执行
- `validate_graph.py` 布局修复后 `graph.md` 已自动更新，无需手动调整坐标
- `build_graph.py` 生成失败时，不得手工拼接或修补最终 JSON，必须回到 `graph.md` 修正后重新生成
- `build_graph.py` 生成失败时，不得覆盖已有结果文件；只有成功生成后，才允许写入目标结果文件
- `graph.md` 始终是唯一可编辑事实来源，最终结果 JSON 只是由其生成的最终产物

## 12. 交付前检查

交付前至少确认以下事项：
1. 已读取 `references/layout.md`
2. 已先生成 `/output/graph.md`
3. 已使用 `scripts/validate_graph.py` 校验并自动修复布局
4. 若已有可编辑的 `graph.md`，已优先在该文件基础上修改
5. 若用户提供了现有建模图 JSON，已先使用 `scripts/reverse_json_to_md.py` 转成 `graph.md`
6. 已使用 `scripts/build_graph.py` 生成最终 JSON
7. 结果文件已写入 `/output/result.json`、自动顺延生成的 `/output/result-N.json`，或用户通过 `--output` 指定的合法路径
8. 若为编辑更新，未改动部分已尽量保持稳定
9. 若用户明确要求仅调整布局，已切换到仅布局调整模式

## 13. 交付要求

默认交付方式如下：
- `/output/graph.md`
- `/output/result.json`；若已存在，则为自动顺延生成的 `/output/result-N.json`

回复用户时应遵守以下要求：
- 以结果完成情况为主
- 不得用长篇解释替代最终文件
- 如用户额外要求说明，可附极简说明
