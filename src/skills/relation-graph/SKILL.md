---
name: relation-graph
description: 知识建模图生成技能。帮助高校教师为课程创建知识建模图。将知识点转换为建模图JSON。
---

# 知识建模图生成

帮助高校教师为课程创建完整的知识建模图。

---

## 生成JSON建模图

将知识点和关系转换为符合规范的知识建模图JSON。

> **提示**：如果是生成新的 JSON，最好先读取 JSON 格式示例文件 [demo.json](references/demo.json) 作为参考。

> **⚠️ 关键结构警告**（常见导入失败原因）：
> - 边数组名必须是 `lines`，**不能**用 `edges`
> - 边属性名：`from`/`to`（**不能**用 `source`/`target`），`text`（**不能**用 `label`）
> - 每条边必须包含：`fromJunctionPoint`、`toJunctionPoint`、`showStartArrow`、`showEndArrow`
> - 节点 `data.startPostion` 必须与 `x`、`y` 坐标一致

### 前置说明

**已有JSON文件处理**：
如果用户已经提供了 JSON 文件（尤其是文件名或语义上表示为“当前建模图.json”这类当前图谱文件），应默认理解为：**用户希望在现有建模图基础上继续修改、补充和微调，而不是整图重建。**

处理原则：
- 优先以用户上传的当前 JSON 作为基准数据
- 尽量保持现有节点、连线、坐标、颜色、形状、文本、data 等属性不变
- 只有**新增**或**明确要求修改**的节点、连线，才依据本技能规则重新计算或调整
- 对未被用户要求修改的内容，不要重排、不重算、不覆盖
- 新增节点和新增连线，应在原 JSON 基础上追加
- 如果只是局部调整，应尽量只影响局部区域，避免破坏用户已经手工优化过的位置关系
- 目标是让用户可以基于同一个建模图 JSON 持续迭代、多轮优化，而不是每次生成一份全新的布局

**画布坐标系说明**：

整个画布是以**中心点(0,0)**为原点，向四周无限延伸的无边区域。

**坐标方向：**
- 原点(0,0)为中心点
- 向左移动：x 减小（如 x - 100）
- 向右移动：x 增大（如 x + 100）
- 向上移动：y 减小（如 y - 100）
- 向下移动：y 增大（如 y + 100）

**节点定位：**
- 节点位置由 **x、y** + **宽高(width、height)** 决定
- 节点中心点 = (x + width/2, y + height/2)

**布局原则：**
- 核心知识点放置在画布中心(0,0)附近
- 子知识点按层级向外延伸分布
- **【核心要求】节点绝对不能重叠，连接线绝对不能交叉**

**核心约束条件：**

1. **节点间距**：
   - 任意两个节点之间**至少保持18px间距**
   - 考虑节点的x、y、width、height，确保不重叠

2. **节点重叠计算规则（重点：必须考虑源节点的宽高）**：

   **【关键原则】计算子节点坐标时，必须从源节点的边界开始计算，而不是从源节点的x/y坐标开始！**

   假设父节点 A(xA, yA, width: wA, height: hA)，子节点 B(width: wB, height: hB)：
   - **右侧子节点**：
     - A的右边界 = xA + wA
     - B.x >= A的右边界 + 间距 = (xA + wA) + 间距
     - 示例：A(x=0, w=200)，B.x >= 0 + 200 + 150 = 350
   - **左侧子节点**：
     - A的左边界 = xA
     - B的右边界 = B.x + wB
     - B的右边界 <= A的左边界 - 间距 = xA - 间距
     - 示例：A(x=0)，B.x + wB <= 0 - 150，即 B.x <= -150 - wB
   - **下方子节点**：
     - A的底部边界 = yA + hA
     - B.y >= A的底部边界 + 间距 = (yA + hA) + 间距
     - 示例：A(y=0, h=60)，B.y >= 0 + 60 + 100 = 160
   - **上方子节点**：
     - A的顶部边界 = yA
     - B的底部边界 = B.y + hB
     - B的底部边界 <= A的顶部边界 - 间距 = yA - 间距
     - 示例：A(y=0)，B.y + hB <= 0 - 100，即 B.y <= -100 - hB

3. **连接线交叉预防**：
   - 相邻层级的节点尽量采用不同的y值或x值偏移
   - 同一父节点的多个子节点，按顺序错开排列
   - 必要时增大层间距或节点间距

4. **跨父节点子节点防交叉（重点）**：
   - 当多个父节点的子节点位于同一层级（左右布局）时，需要整体考虑所有子节点的布局
   - 不同父节点的子节点要在y方向上错开，避免交叉
   - 计算公式：
     ```
     父节点A的子节点范围: yA_min ~ yA_max
     父节点B的子节点范围: yB_min ~ yB_max
     需要满足: yA_max + 间距 < yB_min  或  yB_max + 间距 < yA_min

     示例：
     - 父节点A的4个子节点y范围: -451 ~ -61
     - 父节点B的4个子节点y范围: 25 ~ 398
     - 两者y方向错开，避免交叉
     ```

5. **同父节点多级子节点防重叠**：
   - 当同一个父节点的多个子节点又连接到下一级子节点时，这些孙节点应该在x方向上错开分布
   - 不能所有孙节点都在同一个x位置，应该依次向右偏移
   - 计算公式：
     ```
     父节点A有3个子节点B1,B2,B3，每个Bi又有子节点Ci
     - B1的子节点: x = B1.x + 偏移量1
     - B2的子节点: x = B2.x + 偏移量2 (偏移量2 > 偏移量1)
     - B3的子节点: x = B3.x + 偏移量3 (偏移量3 > 偏移量2)

     示例：
     - node-15(x=687) → node-19(x=1121)
     - node-16(x=687) → node-20(x=1085)
     - 子节点x位置不同，避免垂直排列重叠
     ```

6. **空间预留**：
   - 生成前先计算所有节点所需的总空间
   - 根据子节点数量和层级深度，预留足够的画布区域
   - 避免出现后续节点没有足够空间摆放的情况

5. **对称布局计算（重点）**：

   **上下连接的对称计算**：
   ```
   源节点A: x=0, y=0, width=200, height=60, 右边界=200
   子节点在A右侧，需要计算从右边界开始：
   - 第一个子节点x: 200 + 间距
   - 多个子节点时，从右边界开始均匀分布
   ```

   **左右连接的对称计算**：
   ```
   源节点A: x=0, y=0, width=200, height=60, 底部边界=60
   子节点在A下方，需要计算从底部边界开始：
   - 第一个子节点y: 60 + 间距
   - 多个子节点时，从底部边界开始均匀分布
   ```

   **错误示例（未考虑宽高）**：
   ```
   源节点A: x=0, width=200
   错误: 子节点x = 0 + 150 = 150  ← 从x坐标开始计算，错误！
   正确: 子节点x = 0 + 200 + 150 = 350  ← 从右边界(x+width)开始计算，正确！
   ```

   **正确示例**：
   ```
   父节点A: x=0, y=0, width=200, height=60
   2个子节点在右侧，水平对称分布：
   - 子节点总宽度: 140 * 2 + 30 = 310
   - 起始x = (0 + 200) + 50 = 250  ← 从右边界开始
   - 第一个子节点: x = 250
   - 第二个子节点: x = 250 + 140 + 30 = 420

   父节点A下方有2个子节点，垂直对称分布：
   - 子节点总高度: 45 * 2 + 30 = 120
   - 起始y = (0 + 60) + 50 = 110  ← 从底部边界开始
   - 第一个子节点: y = 110
   - 第二个子节点: y = 110 + 45 + 30 = 185
   ```

**子节点布局规则：**

1. **单个子节点**：
   - 上下连接：可以放在上下位置（x相同，y有一定距离），连接线垂直
   - 左右连接：可以放在左右位置（y相同，x有一定距离），连接线水平

2. **多个子节点 - 上下连接（目标节点在源节点上方/下方）**：
   - 需要在x方向均匀分布，同时y方向也有一定距离
   - 尽量保持与源节点图形中心点对称
   - 计算公式：
     ```
     父节点中心: centerX = x + width/2, centerY = y + height/2
     子节点数量: n
     子节点总宽度: totalWidth = sum(子节点width) + (n-1) * spacing
     起始x: startX = centerX - totalWidth/2
     第i个子节点x: x_i = startX + sum(前i个节点width+spacing)
     y偏移: 根据层级和布局方向计算
     ```

3. **多个子节点 - 左右连接（目标节点在源节点左侧/右侧）**：
   - 需要在y方向均匀分布，同时x方向也有一定距离
   - 尽量保持与源节点图形中心点对称
   - 计算公式：
     ```
     父节点中心: centerX = x + width/2, centerY = y + height/2
     子节点数量: n
     子节点总高度: totalHeight = sum(子节点height) + (n-1) * spacing
     起始y: startY = centerY - totalHeight/2
     第i个子节点y: y_i = startY + sum(前i个节点height+spacing)
     x偏移: 根据层级和布局方向计算
     ```

4. **对称布局示例**：
   ```
   父节点A: x=0, y=0, width=200, height=60, centerX=100, centerY=30
   有3个子节点B,C,D: width=140, height=45, spacing=30

   方案1（上下连接，水平对称分布）:
   - B: x=-195, y=-150
   - C: x=30, y=-150
   - D: x=255, y=-150
   - 保持y一致，x均匀分布

   方案2（左右连接，垂直对称分布）:
   - B: x=300, y=-45
   - C: x=300, y=0
   - D: x=300, y=45
   - 保持x一致，y均匀分布
   ```

**多层布局计算：**
- 第二层节点：以第一层节点为基准计算坐标
- 第三层节点：以第二层节点为基准计算坐标
- 以此类推，确保每一层都不与相邻层重叠

### 步骤0：生成前后的结构约束（最高优先级）

**首要目标：生成出来的 JSON 必须可导入、可显示、可解析。**

在满足结构可用之前，不要优先追求“更美观”的连接线或布局。任何坐标优化、连接点优化，都不能破坏 JSON 的结构合法性。

**硬性要求：**

1. **严格使用本技能定义的 JSON schema**
   - 根对象只能使用：`rootId`、`datetime`、`nodes`、`lines`
   - 边数组名必须是 `lines`，**不能**写成 `edges`
   - 边属性必须使用 `from`、`to`、`text`，**不能**写成 `source`、`target`、`label`

2. **禁止杜撰属性、禁止混入其他图库格式**
   - 不要参考其他流程图、关系图库、思维导图库的字段命名习惯
   - 不要输出本规范未定义、且无法确定被支持的字段
   - 如果不确定某个字段是否支持，宁可不加，也不要臆造

3. **关键字段必须完整**
   - 节点必须有：`id`、`text`、`x`、`y`、`data.type`
   - 边必须有：`id`、`from`、`to`、`text`
   - 为保证导入后可正常显示，边还必须明确：`fromJunctionPoint`、`toJunctionPoint`、`showStartArrow`、`showEndArrow`

4. **引用必须有效**
   - `rootId` 必须存在于 `nodes[].id` 中
   - 每条边的 `from`、`to` 必须都能在 `nodes[].id` 中找到
   - 所有 `id` 不能重复

5. **节点坐标字段必须自洽**
   - `data.startPostion.x` 必须与节点 `x` 一致
   - `data.startPostion.y` 必须与节点 `y` 一致
   - 不允许出现节点显示坐标与 data 中记录坐标不一致的情况

6. **生成后必须先做结构验证，再做布局验证**
   - 先检查 JSON 结构、字段名、字段完整性、引用关系是否正确
   - 确认结构可用后，再检查节点重叠、连线交叉、连接点协调性

### 结构禁止输出字段对照表

| 禁止输出 | 必须改为 | 原因 |
|:---------|:---------|:-----|
| `edges` | `lines` | 本技能边数组固定使用 `lines` |
| `source` | `from` | 本技能边起点字段固定使用 `from` |
| `target` | `to` | 本技能边终点字段固定使用 `to` |
| `label` | `text` | 本技能关系文本字段固定使用 `text` |
| 其他外部图库专用字段 | 本规范已定义字段 | 禁止混入其他图库 schema，避免导入失败 |

### 语义驱动的渲染约束

**节点颜色、形状、知识类型、关系文本都必须由节点内容与实际语义决定，不能为了美观或对称随意指定。**

1. **节点颜色必须匹配节点语义**
   - 核心知识点 → 红色 `#FF0000`
   - 结构化知识框架 → 蓝色 `#00B0F0`
   - 先决知识点 → 绿色 `#00B050`
   - 普通知识点 → 黑色 `#000000`
   - `fontColor` 与 `borderColor` 必须完全一致，禁止一个节点出现文字颜色与边框颜色不一致的情况
   - 节点只能使用以上 4 种颜色，禁止使用任何其他节点颜色
   - 不允许把普通节点随意标成核心节点颜色

2. **节点形状固定规则**
   - `nodeShape` 固定为 `1`
   - 不再通过 `nodeShape` 区分知识类型
   - 节点语义类型通过 `data.type` 定义，并严格遵循内容语义匹配
   - 不能为了视觉变化或类别区分，随意把 `nodeShape` 改成其他值

3. **`data.type` 必须匹配知识内容本身**
   - 概念、定义、原理 → `2`（陈述性知识）
   - 步骤、流程、操作方法 → `3`（程序性知识）
   - 学习方法、选择策略、分析策略 → `5`（认知策略）
   - 案例、示例、范例 → `6`（事实范例）
   - 思政支撑内容 → `9`（思政点）
   - 不能为了凑类型覆盖而强行改写节点语义

4. **关系文本必须反映真实语义关系**
   - 上位包含下位：`包含` / `内容包含`
   - 组成部分：`组成`
   - 步骤流程：`步骤包含`
   - 前置依赖：`是前提`
   - 示例支撑：`是范例`
   - 支撑说明：`支持`
   - 不允许为了让图更“好看”随意替换关系词

5. **线条样式约束**
   - `lineShape` 只在以下三种中选择：`1`（直线）、`44`（折线）、`6`（曲线）
   - 线条样式必须结合整体布局进行匹配：在能保证结构可用、方向正确、且不增加交叉的前提下，优先使用 `1`（直线）；当直线不利于避让或可读性不足时，再使用 `44`（折线）；仅当直线和折线都不能较好表达布局关系时，才使用 `6`（曲线）
   - 线条样式的选择应服务于连线避让、层级表达和整体可读性，不能为了视觉变化随意切换线条样式

6. **线条颜色约束**
   - 线条 `color` 保持默认值 `#000000`
   - 不要为了区分关系或增强视觉效果，给线条额外着色
   - 除非有非常明确的特殊要求，否则所有线条统一使用默认颜色

7. **渲染属性服从语义，不服从随意排版**
   - 先判断节点/关系语义，再决定颜色、形状、关系名
   - 在语义确定后，再做坐标布局和连接点调优
   - 不能反过来先决定样式，再倒推语义

### 生成前自检 Prompt

在开始生成 JSON 前，先逐条自检，全部满足后再输出：

```text
1. 我输出的根对象是否只包含 rootId、datetime、nodes、lines？
2. 我是否严格使用 lines，而没有写成 edges？
3. 我是否严格使用 from / to / text，而没有写成 source / target / label？
4. 我是否杜撰了任何本规范未定义、或无法确认支持的属性？如果有，必须删除。
5. 我的 rootId 是否对应某个真实存在的 nodes[].id？
6. 每个节点是否都包含 id、text、x、y、data.type？
7. 每个节点的 data.startPostion.x / y 是否与节点 x / y 完全一致？
8. 每条边是否都包含 id、from、to、text、fromJunctionPoint、toJunctionPoint、showStartArrow、showEndArrow？
9. 每条边的 from / to 是否都能在 nodes[].id 中找到？
10. 节点颜色、nodeShape、data.type 是否由节点语义决定，而不是为了美观随意指定？
11. 关系 text 是否真实表达语义关系（包含、组成、步骤包含、是前提、是范例、支持等）？
12. 我是否先保证 JSON 结构可用，再考虑连接点协调、布局美观和线条优化？
```

如果以上任一项不能确定，则不要急于输出，先回到结构和语义层面修正，再继续生成。

### 步骤1：确定节点属性

根据知识点类型设置节点属性（文字颜色和边框颜色必须同时改变且保持一致，只允许使用这 4 种颜色）：

| 节点类型 | fontColor | borderColor | nodeShape |
|:---------|:----------|:------------|:----------|
| 核心知识点 | #FF0000 | #FF0000 | 1 |
| 结构化知识框架 | #00B0F0 | #00B0F0 | 1 |
| 先决知识点 | #00B050 | #00B050 | 0 |
| 普通知识点 | #000000 | #000000 | 1 |

### 步骤2：生成节点JSON

节点(nodes)包含以下属性：

| 参数 | 说明 | 类型 | 必选 | 默认值 |
|:-----|:-----|:-----|:-----|:-------|
| id | 节点id，不能重复 | string | 是 | - |
| text | 节点文本 | string | 是 | - |
| type | 节点类型 | string | 否 | "node" |
| isShow | 是否显示 | boolean | 否 | true |
| isHide | 是否隐藏 | boolean | 否 | false |
| expanded | 展开状态 | boolean | 否 | true |
| styleClass | 节点样式class | string | 否 | "" |
| className | 节点类名 | string | 否 | "" |
| nodeShape | 节点形状（0:圆形；1:矩形） | int | 否 | 1 |
| borderWidth | 边框粗细 | int | 否 | 0 |
| borderColor | 边框颜色 | string | 否 | "#000000" |
| fontColor | 节点文本颜色 | string | 否 | "#000000" |
| fontFamily | 字体 | string | 否 | - |
| fontSize | 字体大小 | int | 否 | 14 |
| fontBold | 字体加粗 | boolean | 否 | false |
| fontItalic | 字体斜体 | boolean | 否 | false |
| fontUnderline | 字体下划线 | boolean | 否 | false |
| textHorizontalAlign | 水平位置（left/center/right） | string | 否 | "center" |
| textVerticalAlign | 垂直位置（top/middle/bottom） | string | 否 | "middle" |
| color | 背景颜色（默认白色） | string | 否 | "#ffffff" |
| opacity | 透明度（0-1） | number | 否 | 1 |
| fixed | 是否固定位置 | boolean | 否 | true |
| width | 节点宽度 | number | 否 | 自动 |
| height | 节点高度 | number | 否 | 自动 |
| x | x坐标 | number | 否 | - |
| y | y坐标 | number | 否 | - |
| offset_x | 横向偏移量 | int | 否 | 0 |
| offset_y | 纵向偏移量 | int | 否 | 0 |
| disableDrag | 是否禁止拖拽 | boolean | 否 | false |
| singleNode | 是否为独立节点 | boolean | 否 | false |
| invisiable | 是否不可见 | boolean | 否 | false |
| zIndex | 层级 | int | 否 | 300 |
| data | 自定义属性，包含type等 | object | 否 | - |

### 步骤3：生成边/关系JSON（lines）

节点之间的连线(lines)包含：

| 参数 | 说明 | 类型 | 必选 | 默认值 |
|:-----|:-----|:-----|:-----|:-------|
| id | 边id | string | 是 | - |
| from | 源节点id | string | 是 | - |
| to | 目标节点id | string | 是 | - |
| text | 关系名称 | string | 否 | - |
| styleClass | 线条样式class | string | 否 | "" |
| lineWidth | 线条粗细（像素） | int | 否 | 1 |
| color | 线条颜色 | string | 否 | "#000000" |
| isHide | 是否隐藏 | boolean | 否 | false |
| lineShape | 线条样式（1:直线/44:折线/6:曲线） | int | 否 | 1 |
| fontColor | 线条文字颜色 | string | 否 | "#000000" |
| opacity | 透明度（0-1或0-100，设置为0可隐藏） | number | 否 | 1 |
| arrow | 箭头样式标识 | string | 否 | - |
| animation | 动画效果 | int | 否 | 0 |
| dashType | 虚线类型（0:实线/1:虚线） | int | 否 | 0 |
| disableDefaultClickEffect | 禁用默认点击效果 | boolean | 否 | false |
| showStartArrow | 显示起点箭头（设为true显示双箭头） | boolean | 否 | false |
| showEndArrow | 显示终点箭头（设为true显示双箭头） | boolean | 否 | true |
| startMarkerId | 起点标记id | string | 否 | "" |
| endMarkerId | 终点标记id | string | 否 | "" |
| forDisplayOnly | 仅用于显示 | boolean | 否 | false |
| fromJunctionPoint | 起点连接位置（border:动态最近边框/left:左/right:右/top:上/bottom:下），不设置时默认border | string | 否 | "border" |
| toJunctionPoint | 终点连接位置（border:动态最近边框/left:左/right:右/top:上/bottom:下），不设置时默认border | string | 否 | "border" |

**连接点规则重构原则：先保证结构可用，再优化视觉协调。**

连接点计算不能只做“方向判断”，还要结合二维坐标系、多条关系分布、整体局部避让来调优。

### 3.1 连接点优化目标

连接点选择时，按以下优先级综合考虑：

1. **结构合法**：必须输出规范字段：`fromJunctionPoint`、`toJunctionPoint`
2. **方向正确**：连线出发方向与目标节点相对方位一致
3. **局部顺畅**：尽量减少折返、贴边滑行、过长绕行
4. **多关系均匀分布**：同一节点同一侧的多条关系不能全部挤在中点
5. **整体更协调**：尽量减少交叉，保持主干结构清晰

### 3.2 二维坐标系下的相对方位判断

设起始节点 A(xA, yA, widthA, heightA)，目标节点 B(xB, yB, widthB, heightB)

先计算两个节点中心点：

```text
centerA = (xA + widthA/2, yA + heightA/2)
centerB = (xB + widthB/2, yB + heightB/2)

dx = centerB.x - centerA.x
dy = centerB.y - centerA.y
```

再判断 B 相对 A 的主要方向：

- `|dx| >> |dy|`：以左右关系为主
- `|dy| >> |dx|`：以上下关系为主
- `|dx|` 与 `|dy|` 接近：视为斜向关系（左上 / 左下 / 右上 / 右下）

### 3.3 连接点选择不再是“唯一固定映射”，而是“候选组合 + 择优”

#### （1）正向关系的基础候选

| B相对A的位置 | 优先候选 |
|:-------------|:---------|
| 正右 | `from=right`, `to=left` |
| 正左 | `from=left`, `to=right` |
| 正上 | `from=top`, `to=bottom` |
| 正下 | `from=bottom`, `to=top` |

#### （2）斜向关系的候选组合

| B相对A的位置 | 候选方案1 | 候选方案2 |
|:-------------|:-----------|:-----------|
| 右上 | `right → bottom` | `top → left` |
| 右下 | `right → top` | `bottom → left` |
| 左上 | `left → bottom` | `top → right` |
| 左下 | `left → top` | `bottom → right` |

#### （3）择优规则

当斜向关系存在多个可选组合时，不要机械固定使用某一个，而要比较：

- 哪个方案更符合当前主方向
- 哪个方案与现有连线交叉更少
- 哪个方案让同一侧多条关系分布更均匀
- 哪个方案更少穿越密集节点区域

如果两个方案差异不明显，优先选择更符合主方向的那个。

### 3.4 同一节点多条关系的连接点分布规则

**关键原则：同一节点同一侧的多条边，不能都连接到该侧的中点。**

应该按以下方式处理：

1. 先按边的方向把关系分组：
   - left 侧一组
   - right 侧一组
   - top 侧一组
   - bottom 侧一组

2. 对每一组内部，再按目标节点中心点排序：
   - 左右侧分组：按目标节点 `centerY` 排序
   - 上下侧分组：按目标节点 `centerX` 排序

3. 在该边上按顺序均匀分配锚点，而不是共用一个点

#### 示例A：A右侧有4个子节点

```text
A.right 侧需要连接 B、C、D、E
先按 B/C/D/E 的 centerY 从上到下排序
再把 A.right 边分成 4 个落点区域
让 4 条线分别从不同高度连出
```

#### 示例B：多个节点同时连向同一个目标节点左侧

```text
B、C、D 都连向 A.left
不能都连到 A.left 的中心点
应按 B/C/D 的 centerY 排序后，
在 A.left 边上从上到下分配多个落点
```

### 3.5 单条边方向正确，但整体不协调时的调优规则

如果某条边单独看方向没问题，但放到整体图中不协调，则优先按以下顺序调优：

1. **先调整连接点组合**
   - 例如右上关系从 `right → bottom` 改为 `top → left`

2. **再调整同侧锚点顺序**
   - 让多条线的出线顺序与目标节点排序一致

3. **必要时才调整节点布局**
   - 给高密度边区域留出更大的走线空间

### 3.6 典型案例（案例优先）

#### 案例1：B 在 A 左边

```text
A 在右，B 在左
优先：A.left → B.right
```

#### 案例2：B 在 A 左下

```text
候选1：A.left → B.top
候选2：A.bottom → B.right
如果 A 左侧已有很多连线，而底部较空，则优先候选2
```

#### 案例3：B 在 A 右上

```text
候选1：A.right → B.bottom
候选2：A.top → B.left
如果 A.right 已经有多条边密集分布，则改用 A.top → B.left 更协调
```

#### 案例4：A 同时连接多个右侧子节点

```text
A.right 不能所有边都从中点发出
应按子节点从上到下排序后，
在 A.right 边上分配多个锚点
让连线像“扇形展开”而不是“挤成一束”
```

#### 案例5：两个方案方向都对，但一个更协调

```text
若 B 在 A 右上方：
- A.right → B.bottom 方向正确
- A.top → B.left 方向也正确
此时应选择与其他线交叉更少、边上更均匀的方案
而不是机械套用固定表
```
| fromJuctionPointOffsetX | 起点连接点X偏移 | int | 否 | 0 |
| fromJuctionPointOffsetY | 起点连接点Y偏移 | int | 否 | 0 |
| toJuctionPointOffsetX | 终点连接点X偏移 | int | 否 | 0 |
| toJuctionPointOffsetY | 终点连接点Y偏移 | int | 否 | 0 |
| polyLineRadius | 折线半径 | int | 否 | 0 |
| hidden | 是否隐藏 | boolean | 否 | false |
| useTextPath | 连线文字沿着连线路径走 | boolean | 否 | false |
| data | 自定义属性，如 {type: 9} | object | 否 | {} |

### 步骤4：data字段与知识类型

data字段用于存储节点和边的自定义属性：

**节点 data 字段：**
```
"data": {
  "type": 数字,
  "ownerContainerId": "",
  "backgroundImage": "",
  "imageFit": "cover",
  "startPostion": {"x": 数值, "y": 数值}  // 与节点 x, y 保持一致
}
```

**边 data 字段：**
```
"data": {
  "type": 数字  // 如 9 表示思政点
}
```

**知识类型映射到 data.type：**

| data.type | 类型 | 说明 |
|:----------|:-----|:------|
| 2 | 陈述性知识 | 是什么？为什么？概念、原理 |
| 3 | 程序性知识 | 怎么做？操作步骤 |
| 5 | 认知策略 | 如何学得好？学习方法 |
| 6 | 事实范例 | 案例、例子 |
| 9 | 思政点 | 课程思政点 |

### 步骤5：JSON根对象结构

完整的JSON还需要包含根对象：

| 参数 | 说明 | 类型 | 必选 |
|:-----|:-----|:-----|:-----|
| rootId | 根节点id，随机字符串（如 kp001） | string | 是 |
| datetime | 时间戳 | number | 否 |
| nodes | 节点数组 | array | 是 |
| lines | 边数组 | array | 是 |

### 步骤6：质量检查

生成后检查：
1. 知识点涵盖 data.type (2, 3, 5, 6) 四种类型
2. 核心知识点标红、结构化框架标蓝、先决知识点标绿
3. 包含类关系至少2个子内容
4. 无孤立节点

### 步骤7：JSON结构验证（生成后必须执行）

生成 JSON 后，必须验证结构是否符合要求。**注意：这一步不是可选项，而是生成流程中的必做步骤。**

在任何情况下，都不能因为“布局看起来更美观”而牺牲 JSON 结构合法性。

**先做结构验证，再做布局验证。**

**1. 根对象结构**：
```json
{
  "rootId": "kp001",  // 字符串，必填
  "datetime": 1234567890,  // 数字，可选
  "nodes": [...],  // 数组，必填
  "lines": [...]  // 数组，必填，注意是 "lines" 不是 "edges"
}
```

**⚠️ 常见错误警告**：

| 错误用法 | 正确用法 | 说明 |
|---------|---------|------|
| `"edges": [...]` | `"lines": [...]` | 边数组必须命名为 `lines` |
| `"source": "node-1"` | `"from": "node-1"` | 源节点属性必须是 `from` |
| `"target": "node-2"` | `"to": "node-2"` | 目标节点属性必须是 `to` |
| `"label": "包含"` | `"text": "包含"` | 关系名称属性必须是 `text` |
| 缺少 `fromJunctionPoint` | 添加 `"fromJunctionPoint": "right"` | 必须指定连接点位置 |
| 缺少 `toJunctionPoint` | 添加 `"toJunctionPoint": "left"` | 必须指定连接点位置 |
| 缺少 `showStartArrow`/`showEndArrow` | 添加箭头属性 | 必须指定箭头显示 |
| `data.startPostion` 与 `x,y` 不一致 | 保持一致 | `startPostion` 必须与节点坐标同步 |

**2. 节点对象属性**（每个节点必须包含）：
| 属性 | 类型 | 必填 | 说明 |
|:-----|:-----|:-----|:-----|
| id | string | 是 | 节点id，不能重复 |
| text | string | 是 | 节点文本 |
| x | number | 是 | x坐标 |
| y | number | 是 | y坐标 |
| data.type | number | 是 | 知识点类型：2, 3, 5, 6, 9 |
| data.startPostion | object | 是 | 必须与 x, y 坐标一致：`{"x": 节点x, "y": 节点y}` |
| fontColor | string | 否 | 文字颜色 |
| borderColor | string | 否 | 边框颜色 |
| nodeShape | number | 否 | 形状：0=圆形，1=矩形 |

**3. 连接线对象属性**（每条边必须包含）：
| 属性 | 类型 | 必填 | 说明 |
|:-----|:-----|:-----|:-----|
| id | string | 是 | 边id，不能重复 |
| from | string | 是 | 源节点id（注意：不是 `source`） |
| to | string | 是 | 目标节点id（注意：不是 `target`） |
| text | string | 是 | 关系名称（注意：不是 `label`） |
| fromJunctionPoint | string | 是 | 起点连接位置（border/left/right/top/bottom） |
| toJunctionPoint | string | 是 | 终点连接位置（border/left/right/top/bottom） |
| showStartArrow | boolean | 是 | 是否显示起点箭头 |
| showEndArrow | boolean | 是 | 是否显示终点箭头 |
| lineWidth | number | 否 | 线条粗细，默认1 |
| lineShape | number | 否 | 线条样式，仅允许 1（直线）、44（折线）、6（曲线）；应结合布局匹配，优先直线，其次折线，最后曲线，默认1 |
| color | string | 否 | 线条颜色，默认#000000 |
| opacity | number | 否 | 透明度，默认1 |

**4. 结构可用性强制检查清单**：

生成后必须逐条核对：

- 根对象是否只使用 `rootId`、`datetime`、`nodes`、`lines`
- 是否错误使用了 `edges`
- 每个节点是否都包含 `id`、`text`、`x`、`y`、`data.type`
- 每个节点的 `data.startPostion.x` 是否等于 `x`
- 每个节点的 `data.startPostion.y` 是否等于 `y`
- 每条边是否都包含 `id`、`from`、`to`、`text`
- 每条边是否都包含 `fromJunctionPoint`、`toJunctionPoint`、`showStartArrow`、`showEndArrow`
- 是否错误使用了 `source`、`target`、`label`
- `rootId` 是否存在于 `nodes[].id`
- 每条边的 `from`、`to` 是否都能在 `nodes[].id` 中找到
- 所有节点 id、边 id 是否都唯一
- 是否出现了本规范未定义、无法确认支持的杜撰属性

**5. 布局验证**：
- 节点不能重叠
- 连接线不能交叉
- 节点间距至少 18px
- 同一节点同一侧多条关系不能共用一个中点
- 连线方向应与节点相对位置基本一致

---

## 最小可用 JSON 模板

> **用途**：当生成新的知识建模图 JSON 时，优先以这个模板为骨架补全内容。
>
> **原则**：先保证字段名、结构、引用关系完全合法，再补充节点内容、坐标和连接点优化。

```json
{
  "rootId": "node-1",
  "datetime": 1770620051255,
  "nodes": [
    {
      "id": "node-1",
      "text": "核心主题",
      "type": "node",
      "isShow": true,
      "isHide": false,
      "expanded": true,
      "styleClass": "",
      "className": "",
      "nodeShape": 1,
      "borderWidth": 1,
      "borderColor": "#FF0000",
      "fontColor": "#FF0000",
      "textHorizontalAlign": "center",
      "textVerticalAlign": "middle",
      "color": "#ffffff",
      "opacity": 1,
      "fixed": true,
      "width": 200,
      "height": 60,
      "x": 0,
      "y": 0,
      "offset_x": 0,
      "offset_y": 0,
      "disableDrag": false,
      "singleNode": false,
      "invisiable": false,
      "zIndex": 301,
      "data": {
        "type": 2,
        "ownerContainerId": "",
        "backgroundImage": "",
        "imageFit": "cover",
        "startPostion": {
          "x": 0,
          "y": 0
        }
      }
    },
    {
      "id": "node-2",
      "text": "子知识点",
      "type": "node",
      "isShow": true,
      "isHide": false,
      "expanded": true,
      "styleClass": "",
      "className": "",
      "nodeShape": 1,
      "borderWidth": 0,
      "borderColor": "#000000",
      "fontColor": "#000000",
      "textHorizontalAlign": "center",
      "textVerticalAlign": "middle",
      "color": "#ffffff",
      "opacity": 1,
      "fixed": true,
      "width": 140,
      "height": 45,
      "x": 300,
      "y": 0,
      "offset_x": 0,
      "offset_y": 0,
      "disableDrag": false,
      "singleNode": false,
      "invisiable": false,
      "zIndex": 301,
      "data": {
        "type": 2,
        "ownerContainerId": "",
        "backgroundImage": "",
        "imageFit": "cover",
        "startPostion": {
          "x": 300,
          "y": 0
        }
      }
    }
  ],
  "lines": [
    {
      "id": "line-1",
      "from": "node-1",
      "to": "node-2",
      "text": "包含",
      "color": "#000000",
      "opacity": 1,
      "fontBold": false,
      "fontItalic": false,
      "fontUnderline": false,
      "lineWidth": 1,
      "lineShape": 1,
      "isHide": false,
      "animation": 0,
      "dashType": 0,
      "disableDefaultClickEffect": false,
      "showStartArrow": false,
      "showEndArrow": true,
      "startMarkerId": "",
      "endMarkerId": "",
      "forDisplayOnly": false,
      "fromJunctionPoint": "right",
      "toJunctionPoint": "left",
      "fromJuctionPointOffsetX": 0,
      "fromJuctionPointOffsetY": 0,
      "toJuctionPointOffsetX": 0,
      "toJuctionPointOffsetY": 0,
      "polyLineRadius": 0,
      "hidden": false,
      "data": {
        "type": 2
      }
    }
  ]
}
```

### 使用这个模板时必须检查

- 根对象必须是 `rootId`、`datetime`、`nodes`、`lines`
- `rootId` 必须等于某个真实节点的 `id`
- 每个节点的 `data.startPostion` 必须与 `x`、`y` 完全一致
- 每条边必须使用 `from` / `to` / `text`，不能写成 `source` / `target` / `label`
- 每条边必须引用真实存在的节点 id
- 每条边都应明确 `fromJunctionPoint`、`toJunctionPoint`、`showStartArrow`、`showEndArrow`
- 先保证模板结构合法，再扩展节点数量、关系数量和布局细节

## 快速参考

### 知识点类型（data.type）

| data.type | 类型 | 说明 |
|:----------|:-----|:------|
| 2 | 陈述性知识 | 是什么？为什么？概念、原理 |
| 3 | 程序性知识 | 怎么做？操作步骤 |
| 5 | 认知策略 | 如何学得好？学习方法 |
| 6 | 事实范例 | 案例、例子 |
| 9 | 思政点 | 课程思政点 |

### 颜色标注

文字颜色(fontColor)和边框颜色(borderColor)必须同时改变且严格一致，只允许使用以下 4 种颜色：

- 红色(#FF0000)：核心知识点
- 蓝色(#00B0F0)：结构化知识框架
- 绿色(#00B050)：先决知识点
- 黑色(#000000)：普通知识点

除上述 4 种颜色外，节点不得使用任何其他文字颜色或边框颜色。

### nodeShape 形状

- 0：圆形
- 1：矩形

### lineShape 线条形状

- 1：直线
- 44：折线
- 6：曲线

### dashType 虚线类型

- 0：实线
- 1：虚线

### 程序性知识标注规则

- 下级知识点为步骤或流程 → 标识为程序性知识(PK)
- 下级知识点不是步骤或流程 → 标识为陈述性知识(DK)

### JSON格式参考

JSON格式示例：读取 [demo.json](references/demo.json)
