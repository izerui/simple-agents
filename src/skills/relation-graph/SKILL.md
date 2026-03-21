---
name: relation-graph
description: 生成可直接导入、可显示、可继续迭代修改的知识建模图最终 JSON。帮助高校教师将课程知识点、关系与层级结构转换为符合建模图规范的结构化结果。
---

# 知识建模图生成

帮助高校教师为课程创建完整的知识建模图。

## 生成约束

生成前必须满足：

1. 严格符合 `references/schema.json`
2. 所有 `id` 必须非空且唯一
   - 根对象：推荐 `root-随机字符串`
   - 节点：推荐 `node-随机字符串`
   - 连线：推荐 `line-随机字符串`
3. 使用当前布局脚本与布局参考

## 关键文件

### `references/schema.json`
- 最终输出的唯一结构基准
- 若与其他说明冲突，以它为准

### `references/layout-semantic.md`
- 布局规则、分区规则、增量追加规则
- 规划主干区、步骤区、枚举区、案例区、策略区时必须先读

### 布局脚本
- `scripts/layout_graph.py`：执行布局的脚本
- 新建图、增量图都通过布局脚本完成布局处理
- 技能目录 `/skills/relation-graph/` 只用于读取脚本、参考资料、schema，不用于写入请求文件或结果文件
- 请求 JSON、布局结果 JSON、最终结果 JSON 都必须写入当前工作区的 `output/` 目录
- 只要是本技能生成的 JSON 文件，无论中间文件还是最终文件，都必须放在 `output/`
- 不要写入 `/skills/relation-graph/output/...`
- 用法：`python /skills/relation-graph/scripts/layout_graph.py /path/to/request.json --output output/layout-result.json --pretty`
- 调用时必须显式传入请求 JSON 路径和 `--output` 路径，不能依赖脚本默认值

### `scripts/validate_json.py`
- 最终结果校验脚本
- 最终 JSON 生成后必须运行，只有返回 `VALID` 才算完成
- 用法：`python /skills/relation-graph/scripts/validate_json.py output/result.json --schema /skills/relation-graph/references/schema.json`

## 术语约定

- 节点（node）：`nodes[]` 内对象
- 连线（line）：`lines[]` 内对象
- 根对象：最外层 JSON 对象
- 关系文本：连线的 `text` 字段

## 任务目标

直接产出可导入、可显示、可继续迭代的知识建模图 JSON，不要用解释替代结果。

默认要求：
- 严格符合 schema
- 所有字段都可直接落入前端
- 新建与增量都遵循当前布局参考
- 写入 JSON 文件时必须一次性写入完整对象，不能省略固定字段，不能只写差量字段，不能依赖后续脚本补齐
- 默认应直接生成 JSON 内容并写入文件，不要为了生成请求 JSON 或最终 JSON 再额外编写 Python 脚本
- 只有用户明确要求时，才允许用 Python 脚本程序化生成 JSON

## 增量修改

如果用户提供当前建模图 JSON，应理解为在原图基础上修改，而不是重建。

规则：
- 优先以用户上传的当前 JSON 为基准
- 只有新增或明确要求修改的节点、连线才调整
- 新增节点和连线在原 JSON 基础上追加
- 避免破坏用户已手工优化的位置关系
- 未改旧节点应加入 `preserveNodeIds`
- `preserveNodeIds` 中的节点坐标保持不变，不参与重排
- `targetNodeIds` 只包含本轮新增节点或允许局部调整的节点
- 未明确修改的旧节点样式沿用原 JSON；脚本只做必要规范化补齐，例如 `data.startPostion` 对齐、schema 允许色值归一化
- 新节点按语义区域局部追加，不做整图重排

## 数据要求

### 根对象
最外层 JSON 结构：

```json
{
  "rootId": "root-A1B2C3",
  "datetime": 1770620051255,
  "nodes": [],
  "lines": []
}
```

要求：
- `rootId`：根对象标识，非空字符串，推荐使用 `root-随机字符串` 格式，且不能与节点 id 重复
- `nodes`：至少 1 个节点
- `lines`：连线数组，数组名固定为 `lines`
- `datetime`：时间戳，可选，类型为 `number`

### 节点
节点至少应正确提供：
- `id`
- `text`
- `x`
- `y`
- `data.type`

关键约束：
- `x/y` 必须由 AI 按布局规则直接给出
- `data.startPostion.x/y` 必须与节点 `x/y` 完全一致
- `borderColor` 与 `fontColor` 必须一致
- `width/height` 可缺省，由脚本估算补齐

增量/布局场景下：
- 仅调整 `x/y`
- 如有必要可补齐 `width/height`
- 必须同步更新 `data.startPostion`
- 未明确要求修改的节点样式字段应沿用原 JSON，不要借布局名义重写

布局阶段允许改动的节点字段：
- `x`
- `y`
- `width`
- `height`
- `data.startPostion`

逐字段说明：
- `id`：节点标识，类型为 `string`，必须非空且唯一，推荐使用 `node-随机字符串`
- `text`：节点显示文本
- `text` 不允许换行
- `x`：节点水平坐标，画布中心点为原点 `(0,0)`，左侧为负，右侧为正
- `y`：节点垂直坐标，画布中心点为原点 `(0,0)`，上方为负，下方为正
- `width`：节点宽度，应根据节点文字内容自适应生成
- `height`：节点高度，应根据节点文字内容自适应生成
- `borderColor`：节点边框颜色，由节点语义决定
- `fontColor`：节点文本颜色，必须与 `borderColor` 一致

常用固定字段：
- `type`: `node`
- `isShow`: `true`
- `isHide`: `false`
- `expanded`: `true`
- `selected`: `false`
- `dragging`: `false`
- `styleClass`: `""`
- `className`: `""`
- `nodeShape`: `1`（底层固定值，不代表真实形状）
- `borderWidth`: `1`
- `fontSize`: `14`
- `fontFamily`: `"宋体"`
- `fontBold`: `false`
- `fontItalic`: `false`
- `fontUnderline`: `false`
- `textHorizontalAlign`: `"center"`
- `textVerticalAlign`: `"middle"`
- `color`: `"#ffffff"`（节点背景色，不用于语义表达）
- `opacity`: `1`
- `fixed`: `true`
- `Fx`: `0`
- `Fy`: `0`
- `offset_x`: `0`
- `offset_y`: `0`
- `disableDrag`: `false`
- `singleNode`: `false`
- `invisiable`: `false`
- `zIndex`: `300`

颜色语义：
- `#FF0000`：核心知识点
- `#00B0F0`：核心结构化知识框架
- `#00B050`：先决知识点
- `#000000`：普通知识点

节点 `data` 结构示例：

```json
{
  "type": 2,
  "backgroundImage": "",
  "imageFit": "cover",
  "startPostion": {
    "x": 0,
    "y": 0
  }
}
```

`data` 下固定字段：
- `backgroundImage`: `""`
- `imageFit`: `"cover"`

### `data.type`

| data.type | 含义 | 真实形状 |
| --- | --- | --- |
| 2 | 陈述性知识 | 矩形 |
| 3 | 程序性知识 | 胶囊 |
| 5 | 认知策略 | 圆柱 |
| 6 | 事实范例 | 波浪矩形 |

要求：
- 只能使用以上 4 种取值
- 必须由节点内容语义决定
- 根节点也按 `data.type` 决定其知识类型
- 课程思政点如出现，也必须归入以上 4 类之一，不能扩展新的 `data.type`
- 若下级知识点是步骤或流程，优先标记为程序性知识 `3`
- 若下级知识点不是步骤或流程，优先标记为陈述性知识 `2`

说明：
- 颜色表达语义层次
- 真实形状表达知识类型
- 这两套维度不能混用，不要因为是核心节点就擅自修改知识类型，也不要因为是程序性/策略/范例就误改颜色语义

### 连线
连线至少应正确提供：
- `id`
- `from`
- `to`
- `text`

关键约束：
- `from/to` 必须引用有效节点 id
- `fromJunctionPoint/toJunctionPoint` 由脚本更新
- `lineShape` 默认使用 `1`

增量/布局场景下：
- 只应更新 `fromJunctionPoint`
- 只应更新 `toJunctionPoint`
- 未明确要求修改时，连线样式字段应沿用原 JSON

布局阶段允许改动的连线字段：
- `fromJunctionPoint`
- `toJunctionPoint`

逐字段说明：
- `id`：连线标识，类型为 `string`，必须非空且唯一，推荐使用 `line-随机字符串`
- `from`：起始节点 id，必须引用有效节点
- `to`：结束节点 id，必须引用有效节点
- `text`：关系文本，必须反映真实语义关系
- `text` 不允许换行
- `fromJunctionPoint`：起始节点上的连接位置，可用 `border`、`left`、`right`、`top`、`bottom`
- `toJunctionPoint`：结束节点上的连接位置，可用 `border`、`left`、`right`、`top`、`bottom`
- `lineShape`：连线形状，`1`=直线，`44`=折线，`6`=曲线，默认使用 `1`

常用固定字段：
- `showStartArrow`: `false`
- `showEndArrow`: `true`
- `lineWidth`: `1`
- `color`: `"#000000"`
- `isHide`: `false`
- `fontBold`: `false`
- `fontItalic`: `false`
- `fontUnderline`: `false`
- `opacity`: `1`
- `arrow`: `"RGIns-12-arrow-000000-w5"`
- `animation`: `0`
- `dashType`: `0`
- `disableDefaultClickEffect`: `false`
- `startMarkerId`: `""`
- `endMarkerId`: `""`
- `forDisplayOnly`: `false`
- `fromJuctionPointOffsetX`: `0`
- `fromJuctionPointOffsetY`: `0`
- `toJuctionPointOffsetX`: `0`
- `toJuctionPointOffsetY`: `0`
- `polyLineRadius`: `0`
- `hidden`: `false`

关系文本常用值：
- `支持`
- `具有特征`
- `包含`
- `步骤包含`
- `是前提`
- `关键点包含`
- `并列`
- `定义`
- `具有属性`
- `是一种`
- `组成`
- `构成`

要求：
- 若常用值不足以准确表达语义，允许使用更贴切的关系描述

## 版式原则

relation-graph 按教材式布局规则生成知识建模图。

要求：
- 节点位置由知识角色、分区和阅读路径决定
- 详细分区与样例规则以 `references/layout-semantic.md` 为准

最重要的空间规则：
- 根节点与一级主干节点放中心或中心偏左
- `data.type=3` 优先形成左侧纵向步骤列
- 同父枚举项优先成组排列并尾插
- `data.type=6` 优先放外围区域
- `data.type=5` 放边缘辅助区域
- 增量时优先沿用原图既有方向与分组关系

基础原则：
- 优先 JSON 结构正确，再考虑坐标布局
- 严格按照技能中描述的字段名
- 节点位置由 `x`、`y`、`width`、`height` 共同决定
- 节点中心点 = `(x + width/2, y + height/2)`
- 任意两个节点至少保持 `20px` 安全间距
- 判断重叠或间距不足时，不能只看中心点，必须结合 `x/y/width/height`
- 节点不能重叠

### 画布坐标系

- 原点：`(0, 0)` 为画布中心点
- X 方向：向左为负，向右为正
- Y 方向：向上为负，向下为正
- 节点位置由 `x`、`y`、`width`、`height` 共同决定
- 节点中心点 = `(x + width/2, y + height/2)`

### 节点尺寸

- 节点尺寸由 `width` 和 `height` 决定
- `width`、`height` 可根据节点文字内容自适应生成
- 若请求中未提供 `width/height`，可由脚本按文本估算补齐
- 判断节点重叠、间距和排布时，必须同时考虑 `x`、`y`、`width`、`height`

### 节点间距要求

- 任意两个节点之间至少保持 `20px` 安全间距
- 推荐使用更宽松的间距：垂直方向 `50-80px`，水平方向 `80-120px`
- 计算节点间距时，必须结合节点的 `x`、`y`、`width`、`height`
- 节点不能重叠

### 连线文本对间距的影响

- 有连线文本的节点对，需要根据连线文本长度适当增加间距
- 文本长度较短时，可使用基础间距
- 文本长度较长时，应增加节点之间的水平或垂直距离，避免文字拥挤
- 垂直布局时，连线文本主要影响垂直间距
- 水平布局时，连线文本主要影响水平间距

### 子节点位置计算

- 子节点坐标不是从父节点 `x/y` 开始计算，而是从父节点边界开始计算
- 右侧：`B.x = xA + wA + 间距`
- 左侧：`B.x = xA - wB - 间距`
- 下方：`B.y = yA + hA + 间距`
- 上方：`B.y = yA - hB - 间距`

### 多个子节点布局

- 单个子节点：
- 上下连接时，可以放在父节点上方或下方
- 左右连接时，可以放在父节点左侧或右侧
- 同一父节点的多个子节点应均匀分布
- 右侧或左侧排布时，优先保持相近 `x` 轴，在 `y` 方向均匀展开
- 上方或下方排布时，优先保持相近 `y` 轴，在 `x` 方向均匀展开
- 在此基础上，再叠加步骤列、枚举组、案例区、策略区等语义分区规则

**排列公式：**

- 父节点中心：`centerX = x + width/2`
- 父节点中心：`centerY = y + height/2`
- 子节点数量：`n`
- 横向排布时：`totalWidth = sum(子节点 width) + (n - 1) * spacing`
- 纵向排布时：`totalHeight = sum(子节点 height) + (n - 1) * spacing`
- 横向起始位置：`startX = centerX - totalWidth/2`
- 纵向起始位置：`startY = centerY - totalHeight/2`

### 连接点选择

- 目标在右侧：`right -> left`
- 目标在左侧：`left -> right`
- 目标在下方：`bottom -> top`
- 目标在上方：`top -> bottom`
- 垂直步骤链优先 `bottom -> top`
- 水平同层关系优先左右连接
- 在无法简单判断的情况下，可退回使用 `border`

## 生成步骤

### 1. 判断任务类型
- 有当前建模图 JSON：按增量修改处理
- 没有当前建模图 JSON：按新建处理

增量判断与处理要求：
- 文件内容若已符合本技能规范，且包含 `rootId`、`nodes`、`lines`，应视为当前建模图 JSON
- 增量时尽量保持现有节点、连线、坐标、颜色、形状、文本、`data` 等属性不变
- 先理解原图结构，再做局部修改

### 2. 识别语义结构
识别：
- 根节点
- 核心知识点
- 程序性步骤
- 枚举组
- 案例
- 策略
- 关系语义与阅读路径

### 3. 生成节点与连线内容
根据语义确定：
- 节点文本
- 连线文本
- `data.type`
- 颜色
- 分区

内容质量要求：
- 对理论性强、抽象度高、理解门槛高的陈述性知识点，后面应尽量补充对应范例知识点
- 范例知识点优先使用 `data.type=6`
- 范例知识点应尽量具体，不要只写空泛的“案例分析”

### 4. 直接给出语义坐标
- 必须先阅读 `references/layout-semantic.md`
- 给 `x/y` 时优先参考 `graph-data-1774064516149.json` 的版式风格
- 新建图：先主干，再步骤列，再枚举组，最后外挂案例与策略
- 增量图：优先冻结旧节点，新增节点沿已有步骤列、枚举组、外围区域方向追加
- 步骤链连接方向优先 `top -> bottom`
- 外围挂接优先朝向主干

### 5. 调用布局脚本
必须执行：

```bash
python /skills/relation-graph/scripts/layout_graph.py /path/to/request.json --output output/layout-result.json --pretty
```

路径要求：
- `python /skills/relation-graph/scripts/layout_graph.py` 中的 `/skills/...` 仅指脚本位置
- `/path/to/request.json` 应替换为当前工作区 `output/` 中的文件，例如 `output/python_functions_request.json`
- `--output` 也必须写到当前工作区的 `output/` 目录，例如 `output/layout-result.json`
- 不要把请求文件或结果文件写到 `/skills/relation-graph/output/...`
- 布局脚本调用时必须显式传入这两个路径：请求 JSON 路径、`--output` 路径

写文件要求：
- 调用写文件工具生成 JSON 时，必须写入完整 JSON 内容，不能只写节点/连线的局部字段
- 不能因为字段是固定值就省略
- 不能写“先最小化生成，后面让脚本补齐”的 JSON
- 请求 JSON、布局结果 JSON、最终结果 JSON 都必须是完整对象

请求 JSON 至少包含：
- `mode`: `create` / `incremental`
- `nodes`: 全量节点，且每个节点都直接带 `x/y`
- `lines`: 全量连线
- `preserveNodeIds`: 增量时冻结的旧节点 id 列表
- `targetNodeIds`: 本轮新增或允许局部调整的节点 id 列表
- `rootId`: 可选

要求：
- `layoutOptions` 不使用
- 必须通过 `layout_graph.py` 进入布局流程
- `layout_graph.py` 不负责补齐固定字段；若节点、连线缺少技能要求的固定字段，脚本会直接报错
- `layout_graph.py` 只允许修改布局相关字段，不允许借布局流程重建或简化最终 JSON 结构

### 6. 组装最终 schema JSON
- 读取 `layout_graph.py` 输出
- 合并 schema 固定字段、节点语义属性、颜色、关系文本
- 确保 `data.startPostion` 与 `x/y` 完全一致
- 最终 JSON 必须输出到 `output/` 目录
- 不允许把最终 JSON 写到技能目录、根目录或其他非 `output/` 位置

### 7. 执行最终校验
必须执行：

```bash
python /skills/relation-graph/scripts/validate_json.py output/result.json --schema /skills/relation-graph/references/schema.json
```

要求：
- 只有返回 `VALID` 才算完成
- 若失败，必须继续修正直到通过
- 校验时必须显式传入 `--schema /skills/relation-graph/references/schema.json`

修正策略：
- 先修正结构问题，再修正坐标与布局问题
- 若失败原因是节点过密、局部重叠、间距不足，应扩大空间、增大层间距或重排局部区域后重新执行布局
- 不要为了局部美观牺牲 JSON 结构正确性

## 输出前检查

1. 是否严格符合 `references/schema.json`？
2. `rootId` / 节点 id / 连线 id 是否都非空且唯一？
3. 是否按当前布局参考执行？
4. 节点是否都包含 `id/text/x/y/data.type`？
5. `data.startPostion` 是否与节点坐标完全一致？
6. 连线的 `from/to` 是否都能在节点中找到？
7. 是否严格按照技能中描述的字段名，且未误用 `edges`、`source`、`target`、`label`？
8. 每条连线是否都包含 `fromJunctionPoint`、`toJunctionPoint`？
9. 节点颜色、真实形状、`data.type` 是否由语义决定，而不是为了美观随意指定？
10. 关系文本是否真实表达语义关系？
11. 程序性节点是否形成步骤列？
12. 枚举节点是否成组排列？
13. 案例节点是否优先位于外围区域？
14. 若为增量修改，未改旧节点是否已尽量保持不变？
15. 是否存在孤立节点、重叠或明显拥挤？

若失败原因是节点间距不足或局部重叠，应回到坐标生成或布局执行阶段继续修正。

## 输出要求

最终输出应是知识建模图 JSON。

若用户要求附带说明，可在 JSON 后补充极简说明，但不能省略最终 JSON。
- 输出文件应放在 `output` 目录下。

## 快速参考

### 节点类型
- `2`：陈述性知识，矩形
- `3`：程序性知识，胶囊
- `5`：认知策略，圆柱
- `6`：事实范例，波浪矩形

### 颜色语义
- `#FF0000`：核心知识点
- `#00B0F0`：核心结构化知识框架
- `#00B050`：先决知识点
- `#000000`：普通知识点

### 布局阶段允许改动字段
- 节点：`x`、`y`、`width`、`height`、`data.startPostion`
- 连线：`fromJunctionPoint`、`toJunctionPoint`

### 结构优先级
- 优先 JSON 结构正确，再考虑坐标布局
- 严格按照技能中描述的字段名
- 若与其他说明冲突，以 `references/schema.json` 为准
