---
name: relation-graph
description: 生成或增量修改可直接导入前端的知识建模图 JSON。适用于把课程知识点、层级、关系、步骤链、案例、策略等内容转成最终图数据，并在需要时稳定调整布局。
---

# Relation Graph

生成最终可用的知识建模图 JSON，不输出草稿结构或待补字段。

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
| NodeID | NodeText | NodeType | ParentID | RelationText | NodeX | NodeY | NodeWidth | NodeHeight | NodeColor |
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
- 同一个 `NodeID` 重复出现时，这些节点定义字段必须完全一致：`NodeText`、`NodeType`、`NodeX`、`NodeY`、`NodeWidth`、`NodeHeight`、`NodeColor`
- `NodeText` 非空，不允许换行
- `NodeType` 只能填 `DK`、`PK`、`CS`、`FC`
- 生成脚本内部固定映射为：
  - `DK -> 2`
  - `PK -> 3`
  - `CS -> 5`
  - `FC -> 6`
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
- `NodeColor` 只能是以下 4 个值之一：`#FF0000`、`#00B0F0`、`#00B050`、`#000000`
- `NodeColor` 必须根据节点文本表达的语义来选取，不能随意填写
- 颜色语义：
  - `#FF0000`：核心知识点
  - `#00B0F0`：核心结构化知识框架
  - `#00B050`：先决知识点
  - `#000000`：普通知识点

完整性要求：
- 先确定语义结构，再填写布局字段
- `graph.md` 的内容必须足以直接生成最终 JSON

最小合法样本：

```md
| NodeID | NodeText | NodeType | ParentID | RelationText | NodeX | NodeY | NodeWidth | NodeHeight | NodeColor |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| root-1 | 函数 | DK |  |  | 0 | 0 | 88 | 36 | #00B0F0 |
| node-1 | 概念定义 | DK | root-1 | 包含 | -180 | 120 | 72 | 36 | #000000 |
| node-2 | 分类 | DK | root-1 | 包含 | 140 | 120 | 72 | 36 | #000000 |
| node-3 | 示例 | FC | root-1 | 支持 | 220 | 240 | 88 | 40 | #000000 |
| node-4 | 使用步骤 | PK | root-1 | 包含 | -40 | 220 | 96 | 40 | #00B0F0 |
| node-5 | 明确参数 | PK | node-4 | 包含 | -40 | 300 | 96 | 40 | #000000 |
| node-6 | 调用函数 | PK | node-4 | 包含 | -40 | 360 | 96 | 40 | #000000 |
| node-7 | 复盘检查 | CS | root-1 | 支持 | 320 | 320 | 96 | 40 | #000000 |
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

输出要求：
- 脚本只接受 `graph.md` 文件路径作为输入
- 默认输出当前任务工作目录下的 `/output/result.json`
- 允许通过 `--output` 指定结果文件，但必须仍位于当前任务工作目录下的 `/output` 目录
- 失败时直接提示回去修改 `graph.md`

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

## 关键约束

这些约束要始终满足：

- `x/y` 必须按 `references/layout.md` 生成后直接写入最终 JSON
- `width/height` 必须直接写入最终 JSON，不能省略
- `graph.md` 保持固定表头，不要改格式
- 脚本只能接受 `graph.md` 文件路径作为输入

## 节点与关系的语义要求

节点关键要求：
- `text` 不允许换行
- `x/y` 必须按 `references/layout.md` 生成后直接写入最终 JSON
- `width/height` 必须直接写入最终 JSON，不能省略

节点：
- 颜色表达语义层次
- 形状表达知识类型
- 不要把颜色和形状的语义混用
- 颜色只能从四种允许颜色中选择，并根据既定颜色语义选择合适值

连线关键要求：
- `text` 不允许换行
- `from` 表示父节点，`to` 表示子节点
- 关系文本必须真实表达语义
- 关系文本只能使用这 10 个标准关系名：`包含`、`组成`、`构成`、`是一种`、`具有属性`、`具有特征`、`定义`、`并列`、`是前提`、`支持`
- 连接关系必须优先组织成主知识树，再在树外做少量外围挂接
- 避免网状结构、分支互连和多分支交叉
- 案例节点、策略节点、练习节点默认只作为叶子外挂节点，不要反向连回主知识节点
- 若某条关系会把图拉成织网结构，优先调整层级或改为外围挂接，不要直接补边

关系：
- 关系文本必须真实表达语义
- 必须且只能使用当前技能约定的 10 个标准关系名
- 若出现跨分支语义，优先通过调整层级、重新归类或外围挂接表达，不要直接把多个分支重新连成网

关系生成顺序：
1. 先确定主知识树，只保留最主要、最稳定的父子关系
2. 再补步骤链、枚举组、组成关系等树内展开
3. 最后再补案例、策略、练习等外围挂接
4. 只有在不破坏主知识树阅读的前提下，才允许保留极少量跨层语义连接

结构优先级：
- 优先保持主知识树清楚，再追求语义补充完整
- 宁可少一条容易引起交叉的补充关系，也不要把图做成网状结构
- 当一个节点一级子节点过多时，先拆成二级分组节点，再继续展开

## graph.md 固定规则

- 一旦生成出 `graph.md`，后续所有问题都只能通过修改这个文件来尝试生成 `result.json`
- 不允许重新生成整张 `graph.md`
- 只允许在现有表上做定点 edit
- 用户确认知识点和语义关系后，`graph.md` 表内容视为固定基线
- `graph.md` 成功生成过一次 `result.json` 后，建模图内容即固定下来，后续调整都视为布局调整

用户确认后，默认只允许修改这些布局字段：
- `NodeX`
- `NodeY`
- `NodeWidth`
- `NodeHeight`

用户确认后，默认冻结这些字段：
- `NodeID`
- `NodeText`
- `NodeType`
- `ParentID`
- `RelationText`
- `NodeColor`

例外：
- 只有节点 `id`、关系 `id`、引用合法性这类基础标识问题会导致结果无法生成时，才允许做必要纠错
- 这类纠错不能改变知识点内容、语义关系或整体结构

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
9. 若 `graph.md` 已成功生成过一次 `result.json`，后续只修改布局字段

## 输出要求

默认交付：
- 先生成 `/output/graph.md`
- 再基于该文件生成 `/output/result.json`

回复用户时：
- 以结果完成情况为主
- 不要用长篇解释替代最终文件
- 如果用户额外要求说明，可以附一段极简说明
