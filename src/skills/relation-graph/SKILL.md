---
name: relation-graph
description: 生成或增量修改可直接导入前端的知识建模图 JSON。适用于把课程知识点、层级、关系、步骤链、案例、策略等内容转成符合 schema 的最终图数据，并在需要时保持旧图稳定地追加修改。
---

# Relation Graph

生成最终可用的知识建模图 JSON，不输出“草稿结构”或“待补字段”。

默认交付物：
- 结构化产物：`output/structured.json`
- 最终产物：`output/result.json`
- 若同名文件已存在，则按序递增命名，如 `output/result2.json`、`output/result3.json`

默认工作方式：
- 先生成结构化产物
- 再编译为最终完整 JSON
- 坐标直接写在结构化产物中
- 最终必须通过校验脚本

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

3. `scripts/compose_json.py`
什么时候用：
- 生成完结构化产物后，必须用它编译出最终完整 JSON
- 这个脚本负责补全固定字段、固定值、`fontColor`、`data.startPostion` 等内容

用法：

```bash
python /skills/relation-graph/scripts/compose_json.py output/structured.json --output output/result.json --pretty
```

4. `references/structured-reference.json`
什么时候读：
- 需要参考现有图谱的结构化组织方式、分区方式、节点密度、案例外挂方式时
- 只把它当结构化参考，不要拿它覆盖 schema 或用户当前要求

5. `scripts/validate_json.py`
什么时候用：
- 编译出最终 JSON 后必须运行

用法：

```bash
python /skills/relation-graph/scripts/validate_json.py output/result.json --schema /skills/relation-graph/references/schema.json
```

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

### 4. 先生成结构化产物

结构化产物只保留真正需要模型决定的字段。

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
- 把中间产物拆成多段文件补写
- 使用 `edges`、`source`、`target`、`label` 之类的错误字段名

### 5. 编译最终 JSON

先写出结构化产物，例如：

```text
output/structured.json
```

再执行：

```bash
python /skills/relation-graph/scripts/compose_json.py output/structured.json --output output/result.json --pretty
```

要求：
- 编译脚本只负责补全固定字段和固定值
- 不要手动在最终 JSON 上分段补字段
- 如果怀疑输出被截断，不要在原文件上续补，应重新生成新的完整文件

### 6. 写到固定输出位置

结果文件必须写到：

```text
output/result.json
```

若该文件已存在，则按序递增到下一个可用文件名，例如：

```text
output/result2.json
```

不要写到技能目录或其他路径。

### 7. 校验并修正

最终 JSON 写出后，必须运行：

```bash
python /skills/relation-graph/scripts/validate_json.py output/result.json --schema /skills/relation-graph/references/schema.json
```

只有返回 `VALID` 才算完成。

如果失败：
- 继续修正
- 重新校验
- 不要把未通过校验的结果当最终交付

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
- `fromJunctionPoint/toJunctionPoint` 必须按节点相对位置与关系方向正确填写
- 关系文本必须真实表达语义

关系：
- 关系文本必须真实表达语义
- 优先使用清晰、稳定、可读的关系词
- 优先使用 `references/schema.json` 中约定的常用连线关系文本
- 如果常见关系不足以表达语义，允许使用更贴切的描述

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
3. 已生成结构化产物，而不是直接拼超长最终 JSON
4. 已用 `scripts/compose_json.py` 编译出最终完整 JSON
5. 结果文件写在 `output/result.json` 或按序递增后的 `output/resultN.json`
6. 最终 JSON 不是差量字段，而是完整对象
7. `rootId`、节点 id、连线 id 均非空且唯一
8. `data.startPostion` 与节点坐标完全一致
9. 连线 `from/to` 都能在节点中找到
10. `fromJunctionPoint/toJunctionPoint` 已正确填写
11. 图中没有明显重叠、拥挤或跨区穿插
12. 若为增量修改，未改动部分已尽量保持稳定
13. 已运行校验脚本且返回 `VALID`

## 输出要求

默认交付：
- 生成 `output/structured.json`
- 再生成 `output/result.json`；若已存在则生成下一个可用的 `output/resultN.json`

回复用户时：
- 以结果完成情况为主
- 不要用长篇解释替代最终文件
- 如果用户额外要求说明，可以附一段极简说明
