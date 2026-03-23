---
name: relation-graph
description: 生成或增量修改可直接导入前端的知识建模图 JSON。适用于把课程知识点、层级、关系、步骤链、案例、策略等内容转成最终图数据，并在需要时稳定调整布局。
---

# Relation Graph

生成最终可用的知识建模图 JSON，不输出草稿结构或待补字段。

## 职责边界

本 skill 负责知识建模图的执行落地，包括：
- 生成或增量修改 `graph.md`
- 校验 `graph.md`
- 基于 `graph.md` 生成最终 `result.json`
- 在已有 `graph.md` 或已有图谱 JSON 的情况下执行稳定的增量修改流程
- 按既定格式、字段、布局和文件要求完成落盘

本 skill 不负责课程信息追问、教学目标澄清、知识点粒度协商、课程类型判断或教学质量目标设定；这些由上层提示词负责。

一旦上层已经完成最小建模信息确认，或用户明确要求生成/修改知识建模图，本 skill 即作为最终执行规范生效。

默认交付物：
- 知识单表：`/output/graph.md`
- 最终产物：`/output/result.json`

默认工作方式：
- 先生成知识单表 Markdown
- 后续所有问题都只通过编辑 `graph.md` 解决
- 先用独立校验脚本校验 `graph.md`
- 再用生成脚本传入 `graph.md` 路径，生成最终 JSON
- 生成失败时回到 `graph.md` 继续修改；成功后覆盖 `/output/result.json`
- 如果当前已经存在可编辑的 `graph.md`，优先在该文件基础上继续修改
- 如果用户提供了现有建模图 JSON，先反向转换成 `graph.md`，再在该文件基础上做增量修改

## 什么时候用

当用户要你：
- 从知识点文本、课程内容、结构提纲生成知识建模图
- 修改已有知识建模图 JSON
- 追加节点、关系、步骤链、案例、策略节点
- 调整图结构但仍需输出最终 JSON

## 触发与优先级

出现以下任一情况时，应立即进入本 skill 流程：
- 用户要求生成新的知识建模图
- 用户要求修改已有知识建模图
- 用户要求输出可直接导入前端的最终图 JSON
- 当前工作区已存在可编辑的 `graph.md`
- 用户提供了现有知识建模图 JSON

优先级规则：
- 涉及 `graph.md`、`result.json`、增量修改、校验、导出、文件落盘等执行细节时，以本 skill 为准
- 上层提示词可定义教学目标、追问策略和质量要求，但不得覆盖本 skill 的表结构、字段规则、脚本流程和导出方式
- 若上层提示词与本 skill 在执行细节上存在重叠或冲突，以本 skill 为准

## 严格执行规则

禁止以下做法：
- 不经 `graph.md` 直接手写最终 `result.json`
- 跳过 `graph.md` 校验直接生成最终结果
- 通过直接修改 `result.json` 完成修正
- 在已有可编辑 `graph.md` 的情况下脱离原文件另起一版
- 在用户提供现有图谱 JSON 后，不经过反向转换直接重做整图

必须遵循的唯一主流程是：
1. 生成或修改 `graph.md`
2. 校验 `graph.md`
3. 基于 `graph.md` 生成 `result.json`

若任一步失败，只能回到 `graph.md` 继续修改，再重新执行后续步骤。

## 先读什么

按这个顺序加载资源：

1. `references/layout.md`
什么时候读：
- 任何需要生成或调整 `x/y/width/height`、阅读路径、分区布局、连线拓扑时

2. `references/example.md`
什么时候读：
- 需要参考现有图谱的节点密度、分区方式、外围挂接和坐标尺度时
- 它同时是可直接试跑的 `graph.md` 样本
- 只把它当文件样本和布局参考，不参与正式生成流程

3. `scripts/validate_graph.py`
什么时候用：
- 单独校验 `graph.md`
- 校验脚本只负责检查 `graph.md` 是否可用于生成最终 JSON
- 校验不通过时，只能回去修改 `graph.md`

用法：

```bash
python /skills/relation-graph/scripts/validate_graph.py /output/graph.md
```

4. `scripts/build_graph.py`
什么时候用：
- 在 `graph.md` 已通过校验后，传入 `graph.md` 路径生成最终 `result.json`
- 脚本只接受文件路径参数，不接受内联内容、stdin 或临时脚本替代
- 生成脚本本身不承担校验职责

用法：

```bash
python /skills/relation-graph/scripts/build_graph.py /output/graph.md --output /output/result.json --pretty
```

5. `scripts/reverse_json_to_md.py`
什么时候用：
- 用户提供了现有建模图 JSON，需要先转成可编辑的 `graph.md`
- 转换完成后，后续仍然只允许通过编辑 `graph.md` 做增量修改

用法：

```bash
python /skills/relation-graph/scripts/reverse_json_to_md.py /output/result.json --output /output/graph.md
```

## graph.md 生成规范

在进入工作流之前，先一次性完整生成可用的 `graph.md`。不要先写半成品，再指望后续步骤补齐。

固定表头：

```text
| NodeID | NodeText | NodeType | ParentID | RelationText | NodeX | NodeY | NodeWidth | NodeHeight | NodeSemantic |
```

固定规则：
- `graph.md` 必须是一张单一 Markdown 表
- 第一行必须是固定表头，不能改列名、列顺序、列数量
- 第二行必须是 Markdown 分隔行
- 第三行起每行表示一个节点定义加一条父关系记录
- 不允许生成第二张表
- 不允许把节点写成列表、段落、JSON 片段或半结构化草稿
- 节点文本和关系名称中不要出现 `|`
- 数值字段只能写数字，不能带单位、注释或额外文本
- 必须一次性生成完整可校验版本，不能故意留待后续补字段

每列要求：
- `NodeID` 非空
- 默认优先使用单父节点结构，尽量避免一个节点同时挂多个父节点
- 只有在确有必要且无法通过重构语义层级解决时，才允许同一个 `NodeID` 重复出现，用于表达多个父节点
- 同一个 `NodeID` 重复出现时，这些节点定义字段必须完全一致：`NodeText`、`NodeType`、`NodeX`、`NodeY`、`NodeWidth`、`NodeHeight`、`NodeSemantic`
- `NodeText` 非空，不允许换行
- `NodeType` 只能填 `DK`、`PK`、`CS`、`FC`
- `ParentID` 和 `RelationText` 必须同时为空，或同时非空
- `ParentID` 如果填写，必须引用表内有效节点
- `RelationText` 如果填写，不允许换行
- `RelationText` 只能使用以下 10 个关系名之一：
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
- `NodeX/NodeY/NodeWidth/NodeHeight` 都必须是数字
- `NodeSemantic` 只能是以下 4 个值之一：
  - `核心知识点`
  - `核心结构化知识框架`
  - `先决知识点`
  - `普通知识点`

完整性要求：
- 先确定语义结构，再填写布局字段
- `graph.md` 的内容必须足以直接生成最终 JSON

最小合法样本：

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

## 工作流

### 1. 判断是新建还是增量

新建：
- 用户没有提供现有图 JSON
- 当前也没有现成可复用的 `graph.md`
- 从头生成完整图

增量：
- 如果当前已经存在可编辑的 `graph.md`，直接在该文件基础上修改
- 用户提供了现有图 JSON
- 先使用 `scripts/reverse_json_to_md.py` 把现有图 JSON 转成 `graph.md`
- 再以该 `graph.md` 为基准修改
- 未明确要求改动的旧节点、旧连线尽量保持不变
- 未改动的节点、关系、坐标、尺寸尽量保持不变，只做局部变更和增量补充
- 不要为了新增少量内容重排整张图

### 1.1 增量修改稳定性要求

当任务属于增量修改时，稳定性优先于重排美观。

具体要求：
- 未被明确要求改动的旧节点、旧关系、旧坐标、旧尺寸应尽量保持不变
- 新增少量节点时，优先采用局部补充和局部挪位，不得为少量新增内容整体重排全图
- 若必须调整局部布局，应先保证原有主干阅读路径和原有分区语义稳定
- 只有在现有布局确实无法容纳新增内容，且不调整会导致明显重叠、遮挡或阅读路径断裂时，才允许有限范围重排
- 即使允许重排，也应尽量局限在受影响区域，避免牵动整张图

### 2. 先识别语义骨架

先判断这些结构，再落图：
- 一级主干
- 主要阅读路径
- 步骤链
- 枚举组
- 案例节点
- 策略节点
- 关系语义

不要先机械列节点，再临时补关系和坐标。

### 3. 依据 layout 规划坐标

生成坐标前必须先读 `references/layout.md`。

要求：
- 先定骨架，再定分区，再定节点坐标
- 坐标要服务可读性，而不是只满足不重叠
- 连线拓扑、阅读顺序、节点分区要一起考虑
- 根节点优先按语义中心判断，不要只按入度/出度机械判断
- 优先形成“中心主干 + 树内展开 + 外围挂接”的稳定阅读结构
- 不预设左/右/上/下方向优先级；只要求结构清晰、分区清晰、避免重叠和交叉，且展开节点与外挂节点必须分层分区
- 树内展开优先走上下左右正交方向，外挂优先斜向外侧；节点或子节点过多时，先拉开距离开辟新区域，再继续遵循这套结构偏好
- 开辟新区域承接放不下的子节点时，连线必须尽量避开原有子节点区域，不能从第一展开区中间斜穿或制造新的交叉
- 每个区域都要与其他区域明确分离，不能出现区域之间的重叠、压边或互相侵入
- 区域分布要尽量四周均衡，避免明显一边倒；左右和上下都应保持视觉平衡，但不要求机械对称

这句话要严格按这个意思理解：
- `x/y` 必须出现在最终 JSON 中
- `x/y` 的值必须依据 `references/layout.md` 生成

### 4. 先生成知识单表 Markdown

先按上面的 `graph.md` 生成规范，一次性生成完整单表，不要一上来直接写 JSON。

如果当前已经存在可编辑的 `graph.md`：
- 直接在该文件基础上继续编辑
- 不要重新生成整张表
- 未被要求改动的部分尽量保持不变，只做局部修改和增量补充

如果用户已经提供现有建模图 JSON：
- 先执行 `scripts/reverse_json_to_md.py` 转成 `graph.md`
- 必须继续遵循当前 `graph.md` 的格式规范和字段约束
- 后续编辑都基于该文件进行，不要脱离该文件另起一版
- 未被要求改动的部分尽量保持不变，只在现有文件上做局部修改和增量补充

### 4.1 graph.md 生成规则

这部分以上面的 `## graph.md 生成规范` 为准。生成出 `graph.md` 后，后续所有问题都只能通过编辑这个文件解决。

### 5. 先校验 graph.md

先用独立校验脚本检查 `graph.md`：

```bash
python /skills/relation-graph/scripts/validate_graph.py /output/graph.md
```

要求：
- 校验脚本只负责校验 `graph.md`
- 校验脚本不生成 `result.json`
- 校验不通过时，只能回去修改 `graph.md`
- 校验通过后，才能进入生成步骤

### 6. 再生成最终 JSON

用生成脚本传入 `graph.md` 路径，生成最终 JSON：

```bash
python /skills/relation-graph/scripts/build_graph.py /output/graph.md --output /output/result.json --pretty
```

要求：
- `graph.md` 是后续唯一工作面
- 所有修改只能通过 `edit` 修改现有 `graph.md`
- 一旦生成出 `graph.md`，后续所有问题都只能通过修改 `graph.md` 再尝试生成 `result.json`
- 如果 `graph.md` 来自已有 JSON 的反向转换，也只能在该文件基础上继续修改
- 不允许直接修改 `result.json`
- 不允许通过 AI 临时生成整段脚本、heredoc、内联代码或一次性脚本替代既有脚本执行
- 脚本必须只接受文件路径参数执行
- 生成脚本只负责生成，不承担独立校验流程
- 生成失败时不覆盖已有 `result.json`
- 只有成功生成后，才覆盖目标 `result.json`

## 失败处理

- `validate_graph.py` 校验失败时，不得继续执行生成步骤；必须回到 `graph.md` 修正
- `build_graph.py` 生成失败时，不得手工拼接或修补最终 JSON；必须回到 `graph.md` 修正后重新生成
- `graph.md` 始终是唯一可编辑事实来源，`result.json` 只是由其生成的最终产物

### 7. 输出位置

结果文件必须写到当前任务工作目录下的 `/output` 目录。

默认路径：

```text
/output/result.json
```

说明：
- `/output/` 指当前任务工作目录下的输出目录，不是技能目录下的路径
- `graph.md` 默认也应放在 `/output/graph.md`
- 不要写到技能目录或其他路径

## graph.md 固定规则

- 不允许重新生成整张 `graph.md`
- 只允许在现有表上做定点 edit

### 仅布局调整模式

仅当用户明确表示“知识点和语义关系已确认，只需要调整布局”时，才进入仅布局调整模式。

进入该模式后，默认只修改这些布局字段：
- `NodeX`
- `NodeY`
- `NodeWidth`
- `NodeHeight`

进入该模式后，默认不修改这些内容字段：
- `NodeID`
- `NodeText`
- `NodeType`
- `ParentID`
- `RelationText`
- `NodeSemantic`

若用户后续明确要求修改知识点内容、关系语义或结构层级，应退出仅布局调整模式，恢复正常增量修改流程。

## 增量修改要求

如果是增量修改：
- 如果当前已经存在可编辑的 `graph.md`，优先直接在该文件基础上修改
- 如果用户提供了现有建模图 JSON，必须先用 `scripts/reverse_json_to_md.py` 转成 `graph.md`
- 后续所有修改都在该 `graph.md` 上进行
- 仍需遵循 `graph.md` 的固定表头、字段规则和整体格式约束
- 优先保留已有节点位置
- 优先保留已有连线与 id
- 新增内容应在原图基础上自然追加
- 不要因为局部新增导致全图阅读路径被打散
- 没有被明确要求修改的节点、关系、坐标、尺寸，尽量保持不变
- 优先做局部变更和增量补充，不要整表重写

## 交付前检查

交付前至少确认：

1. 坐标生成前已读取 `references/layout.md`
2. 已先生成 `/output/graph.md` 单表，而不是直接拼超长最终 JSON
3. 已使用 `scripts/validate_graph.py` 单独校验 `graph.md`
4. 若当前已存在可编辑的 `graph.md`，已优先在该文件基础上修改
5. 若用户提供了现有建模图 JSON，已先使用 `scripts/reverse_json_to_md.py` 转成 `graph.md`
6. 已使用 `scripts/build_graph.py` 传入 `graph.md` 路径生成最终 JSON
7. 结果文件写在 `/output/result.json` 或用户通过 `--output` 显式指定的目标路径
8. 若为增量修改，未改动部分已尽量保持稳定
9. 若用户明确要求仅调整布局，已切换到仅布局调整模式

## 输出要求

默认交付：
- 先生成 `/output/graph.md`
- 再基于该文件生成 `/output/result.json`

回复用户时：
- 以结果完成情况为主
- 不要用长篇解释替代最终文件
- 如果用户额外要求说明，可以附一段极简说明
