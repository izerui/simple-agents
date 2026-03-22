---
name: relation-graph
description: 生成或增量修改可直接导入前端的知识建模图 JSON。适用于把课程知识点、层级、关系、步骤链、案例、策略等内容转成符合 schema 的最终图数据，并在需要时保持旧图稳定地追加修改。
---

# Relation Graph

生成最终可用的知识建模图 JSON，不输出“草稿结构”或“待补字段”。

默认交付物：
- 递增结构化产物：`/relation-graph/structured.jsonl`
- 物化后的结构化产物：`/relation-graph/structured.json`
- 最终产物：`/relation-graph/result.json`
- 优先在已有文件基础上修改；只有无法稳定修改时，才递增命名，如 `/relation-graph/result2.json`、`/relation-graph/result3.json`

默认工作方式：
- 先递增追加 `structured.jsonl`
- 再物化为 `structured.json`
- 结构化产物通过校验后，再编译为最终完整 JSON
- 坐标直接写在结构化产物中
- 结构化产物必须先通过校验

## 什么时候用

当用户要你：
- 从知识点文本、课程内容、结构提纲生成知识建模图
- 修改已有知识建模图 JSON
- 追加节点、关系、步骤链、案例、策略节点
- 调整图结构但仍需输出符合既有 schema 的最终 JSON

## 先读什么

按这个顺序加载资源：

1. `references/schema.json`
作用：
- 最终结构与固定字段/固定值的唯一基准
- 如果和其他说明冲突，以它为准

2. `references/layout.md`
什么时候读：
- 任何需要生成或调整 `x/y/width/height`、阅读路径、分区布局、连线拓扑时

3. `scripts/materialize_structured.py`
什么时候用：
- 先把递增写入的 `/relation-graph/structured.jsonl` 物化成 `/relation-graph/structured.json`
- 物化脚本按行读取 JSONL，`meta`/`node`/`line` 记录都允许重复追加；同 id 后出现的记录覆盖前面的记录
- 只有物化成功后，才进入结构化校验

用法：

```bash
python /skills/relation-graph/scripts/materialize_structured.py /relation-graph/structured.jsonl --output /relation-graph/structured.json --pretty
```

4. `scripts/validate_structured.py`
什么时候用：
- 生成完结构化产物后，必须先校验结构化产物
- 只有结构化产物通过校验后，才继续补全生成最终 JSON

用法：

```bash
python /skills/relation-graph/scripts/validate_structured.py /relation-graph/structured.json
```

5. `scripts/compose_json.py`
什么时候用：
- 结构化产物校验通过后，必须用它编译出最终完整 JSON
- 这个脚本负责补全固定字段、固定值、`fontColor`、`data.startPostion` 等内容

用法：

```bash
python /skills/relation-graph/scripts/compose_json.py /relation-graph/structured.json --output /relation-graph/result.json --pretty
```

6. `references/structured-reference.json`
什么时候读：
- 需要参考现有图谱的结构化组织方式、分区方式、节点密度、案例外挂方式时
- 只把它当结构化参考，不要拿它覆盖 schema 或用户当前要求

## 工作流

### 1. 判断是新建还是增量

新建：
- 用户没有提供现有图 JSON
- 从头生成完整图

增量：
- 用户提供了现有图 JSON
- 以现有图为基准修改
- 未明确要求改动的旧节点、旧连线尽量保持不变
- 不要为了新增少量内容重排整张图

### 2. 先识别语义骨架

先判断这些结构，再落图：
- 根节点
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
- 优先形成“中心主干 + 左侧步骤 + 右侧展开 + 外围挂接”的稳定阅读结构

这句话要严格按这个意思理解：
- `x/y` 必须出现在最终 JSON 中
- `x/y` 的值必须依据 `references/layout.md` 生成

### 4. 先递增生成 `structured.jsonl`

先生成 append-only 的 `structured.jsonl`，每行一个 JSON 对象，不要反复重写整份结构化 JSON。

记录类型只用三种：
- `{"kind":"meta","rootId":"...","datetime":...}`
- `{"kind":"node", ...节点字段...}`
- `{"kind":"line", ...连线字段...}`

规则：
- 首次创建 `structured.jsonl` 时写入一条 `meta`
- 后续新增或修正节点、连线时，只追加新的 `node`/`line` 记录，不重写整个文件
- 如果要修正已有节点或连线，追加同 id 的新记录；物化脚本会以后出现的记录为准
- 只有 `structured.jsonl` 已损坏、被截断或无法稳定追加时，才改写到新的 `structured2.jsonl`

结构化记录只保留真正需要模型决定的字段。

节点至少保留：
- `id`
- `text`
- `x`
- `y`
- `width`
- `height`
- `borderColor`
- `data.type`

连线至少保留：
- `id`
- `from`
- `to`
- `text`

按需保留：
- `fromJunctionPoint`
- `toJunctionPoint`
- `lineShape`

不要：
- 先输出超长最终 JSON 再赌模型一次写完
- 把固定字段和固定值也交给模型重复生成几十上百次
- 重写整个 `structured.jsonl` 或手动拼超长 `structured.json`
- 使用 `edges`、`source`、`target`、`label` 之类的错误字段名

### 5. 物化、校验并编译最终 JSON

先递增写出结构化记录，例如：

```text
/relation-graph/structured.jsonl
```

再物化为结构化 JSON：

```bash
python /skills/relation-graph/scripts/materialize_structured.py /relation-graph/structured.jsonl --output /relation-graph/structured.json --pretty
```

物化成功后会得到：

```text
/relation-graph/structured.json
```

先执行结构化产物校验：

```bash
python /skills/relation-graph/scripts/validate_structured.py /relation-graph/structured.json
```

只有结构化产物通过后，再执行：

```bash
python /skills/relation-graph/scripts/compose_json.py /relation-graph/structured.json --output /relation-graph/result.json --pretty
```

要求：
- `structured.jsonl` 必须采用递增追加，不要整文件重写
- 结构化校验前，必须先从 `structured.jsonl` 物化出 `structured.json`
- 结构化产物不通过时，不要继续补全生成最终 JSON
- 结构化产物校验不通过时，优先继续向 `/relation-graph/structured.jsonl` 追加修正记录，然后重新物化并重新校验
- 即使需要重新布局，也应优先通过追加修正后的节点 `x/y`、`width/height`、连接点和分区来完成，而不是重写整份中间产物
- 只有当前 `structured.jsonl` 无法稳定追加、已损坏、被截断，或用户明确要求保留历史版本时，才重新写入新的结构化文件
- 编译脚本只负责补全固定字段和固定值
- 不要手动在最终 JSON 上分段补字段
- 如果怀疑输出被截断，优先检查并修复 `structured.jsonl`；必要时新建下一个可用的 `structuredN.jsonl`

### 6. 写到固定输出位置

结果文件必须写到：

```text
/relation-graph/result.json
```

若该文件已存在，则按序递增到下一个可用文件名，例如：

```text
/relation-graph/result2.json
```

这里的 `/relation-graph/` 指当前任务工作目录下的输出目录，不是技能目录下的路径。

不要写到技能目录或其他路径。

### 7. 生成最终文件

结构化产物校验通过后，由编译脚本生成最终 JSON 文件。

## 关键约束

这些约束要始终满足：

- 最外层字段名必须是 `rootId`、`nodes`、`lines`
- `rootId` 非空且唯一
- 节点 `id` 非空且唯一
- 连线 `id` 非空且唯一
- `from/to` 必须引用有效节点
- `data.startPostion.x/y` 必须与节点 `x/y` 完全一致
- `x/y` 必须按 `references/layout.md` 生成后直接写入最终 JSON
- `width/height` 必须直接写入最终 JSON，不能省略
- `fromJunctionPoint/toJunctionPoint` 必须按节点相对位置与关系方向正确填写
- 节点文本和关系文本都不允许换行
- `borderColor` 与 `fontColor` 必须一致
- 固定字段及其固定值必须以 `references/schema.json` 为准，由编译脚本统一补全，不要凭记忆补写

## 节点与关系的语义要求

节点关键要求：
- `text` 不允许换行
- `data.startPostion.x/y` 必须与节点 `x/y` 完全一致
- `x/y` 必须按 `references/layout.md` 生成后直接写入最终 JSON
- `width/height` 必须直接写入最终 JSON，不能省略

节点：
- 颜色表达语义层次
- 形状表达知识类型
- 不要把颜色和形状的语义混用
- 节点边框颜色 `borderColor` 和节点文字颜色 `fontColor` 必须按 `references/schema.json` 要求填写并保持一致
- 颜色只能从 schema 允许的四种颜色中选择，并根据 schema 中定义的颜色语义选择合适值

连线关键要求：
- `text` 不允许换行
- `from/to` 必须引用有效节点
- `from` 表示父节点，`to` 表示子节点
- `fromJunctionPoint/toJunctionPoint` 必须按节点相对位置与关系方向正确填写
- 关系文本必须真实表达语义
- 连接关系必须优先组织成主知识树，再在树外做少量外围挂接
- 避免网状结构、分支互连和多分支交叉
- 案例节点、策略节点、练习节点默认只作为叶子外挂节点，不要反向连回主知识节点
- 若某条关系会把图拉成织网结构，优先调整层级或改为外围挂接，不要直接补边

关系：
- 关系文本必须真实表达语义
- 优先使用清晰、稳定、可读的关系词
- 优先使用 `references/schema.json` 中约定的常用连线关系文本
- 如果常见关系不足以表达语义，允许使用更贴切的描述
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

## 增量修改要求

如果是增量修改：
- 优先保留已有节点位置
- 优先保留已有连线与 id
- 新增内容应在原图基础上自然追加
- 不要因为局部新增导致全图阅读路径被打散

## 交付前检查

交付前至少确认：

1. 已读取 `references/schema.json`
2. 坐标生成前已读取 `references/layout.md`
3. 已递增生成 `/relation-graph/structured.jsonl`，而不是直接拼超长最终 JSON
4. 已用 `scripts/materialize_structured.py` 物化出 `/relation-graph/structured.json`
5. 已用 `scripts/validate_structured.py` 校验结构化产物并通过
6. 已用 `scripts/compose_json.py` 编译出最终完整 JSON
7. 结果文件写在 `/relation-graph/result.json` 或按序递增后的 `/relation-graph/resultN.json`
8. 若为增量修改，未改动部分已尽量保持稳定

## 输出要求

默认交付：
- 先生成 `/relation-graph/structured.jsonl`
- 生成 `/relation-graph/structured.json`
- 再生成 `/relation-graph/result.json`
- 若已有同名文件，优先在原文件基础上追加或修改；只有无法稳定修改时，才生成下一个可用的 `/relation-graph/structuredN.jsonl` 或 `/relation-graph/resultN.json`

回复用户时：
- 以结果完成情况为主
- 不要用长篇解释替代最终文件
- 如果用户额外要求说明，可以附一段极简说明
