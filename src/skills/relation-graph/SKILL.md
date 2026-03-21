---
name: relation-graph
description: 生成可直接导入、可显示、可继续迭代修改的知识建模图最终 JSON。帮助高校教师将课程知识点、关系与层级结构转换为符合建模图规范的结构化结果。
---

# 知识建模图生成

## 任务目标

直接生成最终建模图 JSON。

要求：
- 可直接导入前端
- 严格符合 `references/schema.json`
- 坐标、尺寸、关系拓扑直接可用
- 可继续增量修改

不要用解释替代 JSON。

## 必读文件

### `references/schema.json`

- 最终结构和固定值的唯一基准
- 若与其他说明冲突，以它为准

### `references/layout.md`

- 画布、坐标、分区、布局、关系拓扑的一体化参考
- 生成 `x/y/width/height` 前必须先读

### `scripts/validate_json.py`

- 最终校验脚本
- 最终 JSON 生成后必须运行
- 只有返回 `VALID` 才算完成

用法：

```bash
python /skills/relation-graph/scripts/validate_json.py output/result.json --schema /skills/relation-graph/references/schema.json
```

## 工作方式

### 直接生成 JSON

默认应直接生成完整 JSON 内容并写入文件。

不要：
- 先写 Python 脚本再生成请求 JSON
- 先写不完整 JSON，后面再补字段
- 依赖其他脚本替你补固定字段或修结构

只有用户明确要求时，才允许用 Python 脚本程序化生成 JSON。

### 输出位置

本技能生成的 JSON 文件都必须放在 `output/` 目录下。

例如：
- `output/result.json`

不要写到：
- `/skills/...`
- 项目根目录
- 其他非 `output/` 路径

### 一次写完整对象

调用写文件工具时，必须一次性写入完整对象。

不要：
- 只写节点局部字段
- 只写连线局部字段
- 因为字段是固定值就省略
- 依赖后续步骤补齐缺失字段

## 生成流程

### 1. 判断是新建还是增量

如果用户提供当前建模图 JSON，应按增量修改处理，而不是重建。

增量要求：
- 优先以用户提供的当前 JSON 为基准
- 未明确修改的旧节点、旧连线尽量保持不变
- 新增内容在原图基础上追加
- 不要为了新增少量节点重排整张图

### 2. 识别语义结构

先识别：
- 根节点
- 一级主干
- 步骤链
- 枚举组
- 案例节点
- 策略节点
- 关系语义
- 主阅读路径

### 3. 按布局参考整体规划

必须先读 `references/layout.md`，再生成坐标。

要求：
- 把画布、坐标、节点分区、关系拓扑作为一个整体规划
- 先定骨架，再定分区，再落坐标
- 直接生成美观、稳定、可读的最终坐标

### 4. 生成最终 JSON

直接生成符合 schema 的最终 JSON。

必须保证：
- `rootId` 非空
- 节点 `id` 非空且唯一
- 连线 `id` 非空且唯一
- `nodes` 和 `lines` 字段名正确
- 不误用 `edges`、`source`、`target`、`label`
- `data.startPostion.x/y` 与节点 `x/y` 完全一致
- `x/y` 必须先依据 `references/layout.md` 的布局规则生成，再直接写入最终 JSON
- `width/height` 必须在最终 JSON 中直接给出，不能省略
- `from/to` 都引用有效节点
- `fromJunctionPoint/toJunctionPoint` 按相对位置正确设置

### 5. 写入最终文件

最终文件写到：

```text
output/result.json
```

### 6. 执行最终校验

必须执行：

```bash
python /skills/relation-graph/scripts/validate_json.py output/result.json --schema /skills/relation-graph/references/schema.json
```

要求：
- 只有返回 `VALID` 才算完成
- 若失败，必须继续修正并重新校验
- 不能把未通过校验的 JSON 当最终结果交付

## 数据要求

### 根对象

最外层结构：

```json
{
  "rootId": "root-A1B2C3",
  "datetime": 1770620051255,
  "nodes": [],
  "lines": []
}
```

要求：
- `rootId`：非空字符串，推荐 `root-随机字符串`
- `nodes`：至少 1 个节点
- `lines`：连线数组，字段名固定为 `lines`
- `datetime`：可选，类型为 `number`

### 节点

节点至少应正确提供：
- `id`
- `text`
- `x`
- `y`
- `width`
- `height`
- `data.type`

关键要求：
- `text` 不允许换行
- `x/y` 必须先依据 `references/layout.md` 的布局规则生成，再直接写入最终 JSON
- `width/height` 必须在最终 JSON 中直接给出，不能省略
- `data.startPostion.x/y` 必须与 `x/y` 完全一致
- `borderColor` 与 `fontColor` 必须一致
- 固定字段和固定值必须完整满足 schema

固定字段及其固定值：
- `type`: `node`
- `isShow`: `true`
- `isHide`: `false`
- `expanded`: `true`
- `selected`: `false`
- `dragging`: `false`
- `styleClass`: `""`
- `className`: `""`
- `nodeShape`: `1`
- `borderWidth`: `1`
- `fontSize`: `14`
- `fontFamily`: `"宋体"`
- `fontBold`: `false`
- `fontItalic`: `false`
- `fontUnderline`: `false`
- `textHorizontalAlign`: `"center"`
- `textVerticalAlign`: `"middle"`
- `color`: `"#ffffff"`
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

`data.type`：
- `2`：陈述性知识，矩形
- `3`：程序性知识，胶囊
- `5`：认知策略，圆柱
- `6`：事实范例，波浪矩形

说明：
- 颜色表达语义层次
- 形状表达知识类型
- 两者不能混用

### 连线

连线至少应正确提供：
- `id`
- `from`
- `to`
- `text`
- `fromJunctionPoint`
- `toJunctionPoint`

关键要求：
- `text` 不允许换行
- `from/to` 必须引用有效节点
- 关系文本必须真实表达语义
- 固定字段和固定值必须完整满足 schema

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

若常用值不足以准确表达语义，允许使用更贴切的关系描述。

固定字段及其固定值：
- `showStartArrow`: `false`
- `showEndArrow`: `true`
- `lineWidth`: `1`
- `color`: `"#000000"`
- `isHide`: `false`
- `lineShape`: `1`
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

## 输出前检查

1. 是否严格符合 `references/schema.json`
2. 是否已先参考 `references/layout.md` 规划布局
3. `rootId` / 节点 id / 连线 id 是否都非空且唯一
4. 是否直接生成了完整 JSON，而不是差量字段
5. `data.startPostion` 是否与节点坐标完全一致
6. 连线 `from/to` 是否都能在节点中找到
7. `fromJunctionPoint/toJunctionPoint` 是否已填写
8. 节点是否存在重叠、拥挤或明显跨区穿插
9. 增量修改时，未改旧节点是否已尽量保持不变
10. 是否已经执行校验脚本并返回 `VALID`

## 输出要求

最终输出应是知识建模图 JSON 文件。

若用户要求附带说明，可在结果后补一段极简说明，但不能省略最终 JSON 文件。
