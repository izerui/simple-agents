# 教学设计导入 `data` 对象结构说明

本文档只分析 Python 文档解析服务返回结果中的 `data` 对象，也就是 Java 后端真正消费的文档内容。

对应入口代码：

- [CollectCourseDesignServiceImpl.java](/Users/liuyuhua/IdeaProjects/mcd_admin_server/src/main/java/com/hnyr/mcd/bis/service/impl/CollectCourseDesignServiceImpl.java#L549)
- [CollectCourseDesignServiceImpl.java](/Users/liuyuhua/IdeaProjects/mcd_admin_server/src/main/java/com/hnyr/mcd/bis/service/impl/CollectCourseDesignServiceImpl.java#L996)
- [CollectCourseDesignServiceImpl.java](/Users/liuyuhua/IdeaProjects/mcd_admin_server/src/main/java/com/hnyr/mcd/bis/service/impl/CollectCourseDesignServiceImpl.java#L1622)

## 1. 总体处理流程

后端拿到 `docResponse.data` 后，会先转成 `JSONObject`，然后分两步处理：

1. `processDesignData(...)`
   处理教学设计基础信息。
2. `processActivityData(...)`
   处理教学活动及活动任务明细。

流程顺序如下：

1. 读取 `课程设计名称`
2. 读取 `课程设计` 数组
3. 从 `课程设计` 中提取学习目标、先决知识、时间、资源、活动摘要
4. 保存教学设计主表
5. 保存知识点、资源明细
6. 再读取顶层 `活动序列`
7. 按活动顺序创建活动
8. 再按任务数组顺序创建活动任务

## 2. `data` 对象总体结构

最接近当前代码真实消费方式的结构如下：

```json
{
  "课程设计名称": "2025-2026学年第一学期第3周（第2次）XXX",
  "课程设计": [
    {
      "key": "学习目标",
      "value": {
        "知识点（学习水平）": "（1）xxx（理解）\n（2）yyy（运用）",
        "能力目标": "（1）aaa\n（2）bbb",
        "素质目标（课程思政点）": "（1）ccc"
      }
    },
    {
      "key": "学习先决知识",
      "value": {
        "知识点（学习水平）": "（1）前置1\n（2）前置2"
      }
    },
    {
      "key": "课上时间",
      "value": "45分钟"
    },
    {
      "key": "课下时间",
      "value": "30分钟"
    },
    {
      "key": "课上资源",
      "value": "资源类别1\n资源说明1\n资源类别2\n资源说明2"
    },
    {
      "key": "课下资源",
      "value": "资源类别A\n资源说明A"
    },
    {
      "key": "活动序列",
      "sorted_names": [
        "活动1：导入",
        "活动2：任务实施"
      ],
      "value": {
        "活动1：导入": [
          {
            "活动目标": "（1）xxx",
            "地点": "课上",
            "时间": "10分钟",
            "学习资源": "PPT\n案例"
          }
        ],
        "活动2：任务实施": [
          {
            "活动目标": "（1）yyy",
            "地点": "课上",
            "时间": "35分钟",
            "学习资源": "任务书\n样例"
          }
        ]
      }
    }
  ],
  "活动序列": {
    "活动1：导入": {
      "活动任务序列（导入任务描述）": "导入说明",
      "师生交互过程": "活动级文字描述",
      "活动目标": "（1）xxx",
      "活动任务序列（任务）": [
        {
          "任务名称": "任务1：观察",
          "任务描述": "观察案例",
          "任务时长": "10分钟",
          "学习地点": "课上",
          "教学方式（或学习方式）": {
            "checkbox": [
              ["讲授法", "讨论法", "其他"],
              [0, 1]
            ],
            "checkbox_other": "补充方式"
          },
          "学习资源": "PPT\n案例材料",
          "师生交互过程": {
            "value": ["教师提问", "img1.png", "学生回答"],
            "images": ["img1.png"]
          },
          "学习成果及评价标准": {
            "value": ["学习成果：xxx", "评价标准：yyy"],
            "images": []
          },
          "备注": "可选"
        }
      ]
    }
  }
}
```

## 3. 顶层字段说明

### 3.1 `课程设计名称`

来源代码：

- [CollectCourseDesignServiceImpl.java](/Users/liuyuhua/IdeaProjects/mcd_admin_server/src/main/java/com/hnyr/mcd/bis/service/impl/CollectCourseDesignServiceImpl.java#L998)
- [CollectCourseDesignServiceImpl.java](/Users/liuyuhua/IdeaProjects/mcd_admin_server/src/main/java/com/hnyr/mcd/bis/service/impl/CollectCourseDesignServiceImpl.java#L854)

处理规则：

- 为空时，不中断导入，但会记录提示：`未获取到教学设计课次名称`
- 必须同时包含 `学年`、`学期`、`周`、`次`，否则记录提示：`教学设计课次名称不规范`
- 原文保存为教学设计名称 `designDto.name`
- 同时解析出：
  - `year`：`学年` 前面的文本
  - `semester`：`学年` 与 `学期` 之间的文本，去掉前缀“第”
  - `week`：`学期` 与 `周` 之间的文本，去掉前缀“第”
  - `teachNumber`：`（第` 与 `次）` 之间的文本，去掉前缀“第”

注意：

- 这里只做字符串切割，不做严格格式校验
- 中文数字不会统一转换成阿拉伯数字

### 3.2 `课程设计`

来源代码：

- [CollectCourseDesignServiceImpl.java](/Users/liuyuhua/IdeaProjects/mcd_admin_server/src/main/java/com/hnyr/mcd/bis/service/impl/CollectCourseDesignServiceImpl.java#L1020)

这是一个数组，后台按每个元素的 `key` 识别不同模块。

当前代码依赖的 `key` 有：

- `学习目标`
- `学习先决知识`
- `课上时间`
- `课下时间`
- `课上资源`
- `课下资源`
- `活动序列`

如果整个 `课程设计` 数组为空：

- 不抛异常
- 只记录提示：`未获取到教学设计基础设计数据`

### 3.3 顶层 `活动序列`

来源代码：

- [CollectCourseDesignServiceImpl.java](/Users/liuyuhua/IdeaProjects/mcd_admin_server/src/main/java/com/hnyr/mcd/bis/service/impl/CollectCourseDesignServiceImpl.java#L1632)

这是活动详情对象，key 为活动原始名称，例如：

```json
{
  "活动1：导入": {
    "活动任务序列（导入任务描述）": "导入说明",
    "师生交互过程": "活动级文字描述",
    "活动目标": "（1）xxx",
    "活动任务序列（任务）": []
  }
}
```

注意：

- 这里的活动名必须和 `课程设计[].key = 活动序列.value` 中的活动名完全一致
- 后台不会直接遍历顶层 `活动序列`，而是按 `课程设计` 中的活动摘要顺序来反查详情

## 4. `课程设计` 数组详细处理方式

### 4.1 `key = 学习目标`

来源代码：

- [CollectCourseDesignServiceImpl.java](/Users/liuyuhua/IdeaProjects/mcd_admin_server/src/main/java/com/hnyr/mcd/bis/service/impl/CollectCourseDesignServiceImpl.java#L696)

`value` 应为对象，当前后台读取：

- `知识点（学习水平）`
- `能力目标`
- `素质目标（课程思政点）`

#### 4.1.1 知识点拆分规则

来源代码：

- [CollectCourseDesignServiceImpl.java](/Users/liuyuhua/IdeaProjects/mcd_admin_server/src/main/java/com/hnyr/mcd/bis/service/impl/CollectCourseDesignServiceImpl.java#L584)

拆分顺序：

1. 先按换行 `\n` 拆
2. 如果只得到 1 项，再按 `（数字）` 拆
3. 如果还只有 1 项，再按中文分号 `；` 拆

每项会去掉的前缀序号：

- `（1）`
- `1.`
- `1、`

排序方式：

- 按拆分后的出现顺序，从 1 开始设置 `sortNum`

标签提取：

- 取每项最后一个 `（...）` 作为标签区
- 支持映射：
  - `理解` -> `0`
  - `记忆` -> `1`
  - `运用` -> `2`

标签会从最终知识点名称中去掉。

示例：

```json
"知识点（学习水平）": "（1）变量定义（记忆）\n（2）条件判断（理解,运用）"
```

会被拆成近似结果：

```json
[
  { "name": "变量定义", "sortNum": 1, "tags": "1" },
  { "name": "条件判断", "sortNum": 2, "tags": "0,2" }
]
```

#### 4.1.2 `能力目标`

只有在请求参数 `kcType` 包含“项目化”时才会处理，来源代码：

- [CollectCourseDesignServiceImpl.java](/Users/liuyuhua/IdeaProjects/mcd_admin_server/src/main/java/com/hnyr/mcd/bis/service/impl/CollectCourseDesignServiceImpl.java#L1031)

否则即使有值，也不会写入能力目标列表。

#### 4.1.3 `素质目标（课程思政点）`

处理方式与知识点一致，直接拆分并保存。

### 4.2 `key = 学习先决知识`

来源代码：

- [CollectCourseDesignServiceImpl.java](/Users/liuyuhua/IdeaProjects/mcd_admin_server/src/main/java/com/hnyr/mcd/bis/service/impl/CollectCourseDesignServiceImpl.java#L717)

`value` 应为对象，当前后台只读取：

- `知识点（学习水平）`

拆分规则与知识点完全一致，最终保存为学习先决知识点列表。

### 4.3 `key = 课上时间 / 课下时间`

来源代码：

- [CollectCourseDesignServiceImpl.java](/Users/liuyuhua/IdeaProjects/mcd_admin_server/src/main/java/com/hnyr/mcd/bis/service/impl/CollectCourseDesignServiceImpl.java#L807)

处理规则：

- `课上时间` 对应 `ksTime`
- `课下时间` 对应 `kxTime`
- 从字符串中提取第一个数字作为分钟数
- 没提取到数字时返回 `0`

示例：

- `"45分钟"` -> `45`
- `"课上 2 学时"` -> `2`
- `"约 10-15 分钟"` -> `10`

注意：

- 这里只取第一个数字，不会累加多个数字

### 4.4 `key = 课上资源 / 课下资源`

来源代码：

- [CollectCourseDesignServiceImpl.java](/Users/liuyuhua/IdeaProjects/mcd_admin_server/src/main/java/com/hnyr/mcd/bis/service/impl/CollectCourseDesignServiceImpl.java#L794)
- [CollectCourseDesignServiceImpl.java](/Users/liuyuhua/IdeaProjects/mcd_admin_server/src/main/java/com/hnyr/mcd/bis/service/impl/CollectCourseDesignServiceImpl.java#L1151)

`value` 必须是字符串，按“资源名称 / 资源描述”交替行解析。

示例：

```json
"课上资源": "教材\nPython基础教材\nPPT\n第3章课件"
```

解析结果近似为：

```json
[
  { "name": "教材", "resourceDetail": "Python基础教材" },
  { "name": "PPT", "resourceDetail": "第3章课件" }
]
```

处理规则：

1. 按换行拆分
2. 奇数行作为资源名称
3. 偶数行作为资源描述
4. 如果最后一个资源名称没有对应描述，描述为空字符串

### 4.5 `key = 活动序列`

来源代码：

- [CollectCourseDesignServiceImpl.java](/Users/liuyuhua/IdeaProjects/mcd_admin_server/src/main/java/com/hnyr/mcd/bis/service/impl/CollectCourseDesignServiceImpl.java#L735)
- [CollectCourseDesignServiceImpl.java](/Users/liuyuhua/IdeaProjects/mcd_admin_server/src/main/java/com/hnyr/mcd/bis/service/impl/CollectCourseDesignServiceImpl.java#L1211)

这一块不是活动详情，而是活动摘要表。

结构要求：

```json
{
  "key": "活动序列",
  "sorted_names": ["活动1：导入", "活动2：任务实施"],
  "value": {
    "活动1：导入": [
      {
        "活动目标": "（1）xxx",
        "地点": "课上",
        "时间": "10分钟",
        "学习资源": "PPT\n案例"
      }
    ]
  }
}
```

#### 4.5.1 `sorted_names` 的作用

排序规则：

- 如果 `sorted_names` 存在，则活动顺序严格按它执行
- 如果 `sorted_names` 缺失，则退化为 `value.keySet()` 顺序

风险：

- `keySet()` 顺序不适合依赖为稳定业务顺序
- 建议 `sorted_names` 始终提供

#### 4.5.2 活动摘要行支持字段

每个活动数组中的每一项，当前后台可能读取：

- `活动目标`
- `地点`
- `学习地点`
- `时间`
- `学习资源`

其中：

- `地点` 优先；缺失时才读取 `学习地点`
- 地点去空白后只允许 `课上` / `课下`
- 时间字段会提取所有数字并累加
- `学习资源` 按资源名/描述交替行解析

#### 4.5.3 活动摘要的两个用途

这一块最终会生成两类中间数据：

1. `activityTimeVoList`
   用于控制活动创建顺序以及活动地点/时间/资源摘要。
2. `designPointMap`
   用于给活动补充“活动目标 + 地点时间资源摘要”。

## 5. 顶层 `活动序列` 详细处理方式

来源代码：

- [CollectCourseDesignServiceImpl.java](/Users/liuyuhua/IdeaProjects/mcd_admin_server/src/main/java/com/hnyr/mcd/bis/service/impl/CollectCourseDesignServiceImpl.java#L1622)

后台不是直接遍历顶层 `活动序列`，而是：

1. 先从 `课程设计[].活动序列` 生成活动顺序
2. 再按活动原始名称去顶层 `活动序列` 里取对应详情

这意味着：

- 顶层 `活动序列` 多出来的活动，不会被处理
- `课程设计[].活动序列` 中存在但顶层缺失的活动，可能导致空指针异常

### 5.1 活动对象支持字段

每个活动对象当前读取：

- `活动任务序列（导入任务描述）`
- `师生交互过程`
- `活动目标`
- `活动任务序列（任务）`

### 5.2 活动名称处理规则

来源代码：

- [CollectCourseDesignServiceImpl.java](/Users/liuyuhua/IdeaProjects/mcd_admin_server/src/main/java/com/hnyr/mcd/bis/service/impl/CollectCourseDesignServiceImpl.java#L1576)

处理方式：

1. 去掉前缀 `活动1`、`活动2`、`活动一`、`活动二` 等
2. 去掉前导标点 `:：、，,`
3. 最终得到库里保存的活动名称

示例：

- `活动1：导入` -> `导入`
- `活动三、任务实施` -> `任务实施`

活动排序：

- 从 1 开始，按 `activityTimeVoList` 顺序递增

## 6. `活动任务序列（任务）` 详细处理方式

来源代码：

- [CollectCourseDesignServiceImpl.java](/Users/liuyuhua/IdeaProjects/mcd_admin_server/src/main/java/com/hnyr/mcd/bis/service/impl/CollectCourseDesignServiceImpl.java#L1444)

每个任务对象当前支持：

- `任务名称`
- `任务描述`
- `任务时长`
- `学习地点`
- `教学方式（或学习方式）`
- `学习资源`
- `师生交互过程`
- `学习成果及评价标准`
- `备注`

### 6.1 `任务名称`

处理规则：

1. 删除字符串中的 `活动任务序列`
2. 去掉首尾全角括号 `（` `）`
3. 长度必须不超过 50
4. 再去掉前缀 `任务1`、`任务2`、`任务一`、`任务二`
5. 去掉前导标点 `:：、，,`

示例：

- `任务1：观察` -> `观察`
- `（任务二）归纳总结` -> `归纳总结`

任务排序：

- 从 1 开始，按数组顺序递增

### 6.2 `任务描述`

处理规则：

- 原样读取
- 长度必须不超过 500

### 6.3 `任务时长`

处理规则：

- 提取字符串中所有数字并累加

示例：

- `"10分钟"` -> `10`
- `"1课时20分钟"` -> `21`

### 6.4 `学习地点`

处理规则：

- 去掉所有空白
- 只允许 `课上` / `课下`
- 否则直接抛异常，终止导入

### 6.5 `教学方式（或学习方式）`

推荐结构：

```json
{
  "checkbox": [
    ["讲授法", "讨论法", "其他"],
    [0, 1]
  ],
  "checkbox_other": "补充说明"
}
```

来源代码：

- [CollectCourseDesignServiceImpl.java](/Users/liuyuhua/IdeaProjects/mcd_admin_server/src/main/java/com/hnyr/mcd/bis/service/impl/CollectCourseDesignServiceImpl.java#L1489)

处理规则：

- `checkbox` 必须是长度为 2 的数组
- 第 1 项是 label 数组
- 第 2 项是被选中的下标数组
- 每个选中下标先做 `+1`
- 如果 `+1` 后恰好等于 label 总数，则映射成 `99`
- `checkbox_other` 长度不得超过 50

示例：

```json
"checkbox": [
  ["讲授法", "讨论法", "其他"],
  [0, 2]
]
```

会映射为：

```json
["1", "99"]
```

### 6.6 `学习资源`

处理方式与 `课上资源` / `课下资源` 一致：

- 字符串格式
- 按资源名称 / 资源描述交替行拆分

### 6.7 `师生交互过程`

这是任务级富文本对象，不是普通字符串。

推荐结构：

```json
{
  "value": ["教师提问", "img1.png", "学生回答"],
  "images": ["img1.png"]
}
```

来源代码：

- [CollectCourseDesignServiceImpl.java](/Users/liuyuhua/IdeaProjects/mcd_admin_server/src/main/java/com/hnyr/mcd/bis/service/impl/CollectCourseDesignServiceImpl.java#L1276)

处理规则：

- `images` 中列出的字符串会被识别为图片占位符
- `value` 按顺序遍历
- 如果某项属于图片，则输出成 `<p><img src='前缀+文件名' /></p>`
- 非图片项连续拼接后再包成 `<p>文本</p>`

最终入库的是 HTML 字符串。

### 6.8 `学习成果及评价标准`

这也是富文本对象。

推荐结构：

```json
{
  "value": ["学习成果：xxx", "评价标准：yyy"],
  "images": []
}
```

来源代码：

- [CollectCourseDesignServiceImpl.java](/Users/liuyuhua/IdeaProjects/mcd_admin_server/src/main/java/com/hnyr/mcd/bis/service/impl/CollectCourseDesignServiceImpl.java#L1326)

处理规则：

1. 在 `value` 中找到第一个以 `评价标准` 开头的元素，作为分割点
2. 分割点之前归入“学习成果”
3. 分割点及其之后归入“评价标准”
4. 两部分都按富文本规则转成 HTML
5. 第一段会去掉标题前缀：
   - `学习成果`
   - `评价标准`
   - 紧接着的 `:：、，,`

最终写入：

- `resultContent`
- `evaluateContent`

注意：

- 如果根本没有出现 `评价标准`，则全部内容都会被归到“学习成果”

### 6.9 `备注`

处理规则：

- 原样读取
- 不做长度校验

## 7. 排序规则汇总

### 7.1 教学设计排序

来源代码：

- [CollectCourseDesignServiceImpl.java](/Users/liuyuhua/IdeaProjects/mcd_admin_server/src/main/java/com/hnyr/mcd/bis/service/impl/CollectCourseDesignServiceImpl.java#L1107)

规则：

- 新建导入时，`sortNum = 当前课程下最大 sortNum + 1`
- 覆盖导入时沿用已有设计记录

### 7.2 知识点排序

来源代码：

- [CollectCourseDesignServiceImpl.java](/Users/liuyuhua/IdeaProjects/mcd_admin_server/src/main/java/com/hnyr/mcd/bis/service/impl/CollectCourseDesignServiceImpl.java#L603)

规则：

- 按拆分后的自然顺序，从 1 开始

### 7.3 活动排序

来源代码：

- [CollectCourseDesignServiceImpl.java](/Users/liuyuhua/IdeaProjects/mcd_admin_server/src/main/java/com/hnyr/mcd/bis/service/impl/CollectCourseDesignServiceImpl.java#L1211)
- [CollectCourseDesignServiceImpl.java](/Users/liuyuhua/IdeaProjects/mcd_admin_server/src/main/java/com/hnyr/mcd/bis/service/impl/CollectCourseDesignServiceImpl.java#L1636)

规则：

- 优先按 `课程设计[].活动序列.sorted_names`
- 缺失时退化成 `value.keySet()` 顺序
- 活动 `sortNum` 从 1 开始递增

### 7.4 任务排序

来源代码：

- [CollectCourseDesignServiceImpl.java](/Users/liuyuhua/IdeaProjects/mcd_admin_server/src/main/java/com/hnyr/mcd/bis/service/impl/CollectCourseDesignServiceImpl.java#L1445)

规则：

- 按 `活动任务序列（任务）` 数组顺序，从 1 开始递增

## 8. 校验与风险点

### 8.1 只记录提示，不中断导入

以下问题当前只会写入结果提示，不一定中断：

- `课程设计名称` 缺失
- `课程设计名称` 格式不规范
- `课程设计` 为空
- 学习目标/先决知识/活动摘要缺失

### 8.2 会直接抛异常并中断导入

以下问题可能直接导致导入失败：

- `地点` / `学习地点` 不是 `课上` 或 `课下`
- 活动名称为空
- 活动名称长度超过 50
- 任务名称长度超过 50
- 任务描述长度超过 500
- `checkbox_other` 长度超过 50

### 8.3 结构一致性风险

这些是当前代码强依赖但没有完全防守式处理的约束：

- `课程设计[].活动序列.value` 的活动名必须和顶层 `活动序列` 完全一致
- `sorted_names` 最好始终提供，否则活动顺序不稳定
- 顶层 `活动序列` 中缺失某个活动详情时，存在空指针风险
- `活动任务序列（任务）` 理论上应该始终为数组

## 9. JSON Schema

下面 schema 尽量贴近当前后端实现，但有两类跨字段一致性无法仅靠 schema 完整表达：

- `课程设计[].活动序列.value` 的 key 必须与顶层 `活动序列` key 一致
- `sorted_names` 必须与上述 key 一致

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.com/course-design-data.schema.json",
  "title": "Course Design Parse Data",
  "type": "object",
  "required": ["课程设计名称", "课程设计", "活动序列"],
  "properties": {
    "课程设计名称": {
      "type": "string",
      "description": "教学设计名称，建议包含学年/学期/周/次"
    },
    "课程设计": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/courseDesignItem"
      }
    },
    "活动序列": {
      "type": "object",
      "description": "活动详细信息，key 为活动原始名称，如 活动1：导入",
      "minProperties": 1,
      "additionalProperties": {
        "$ref": "#/$defs/activityDetail"
      }
    }
  },
  "$defs": {
    "courseDesignItem": {
      "oneOf": [
        { "$ref": "#/$defs/learningTargetItem" },
        { "$ref": "#/$defs/prerequisiteItem" },
        { "$ref": "#/$defs/timeItem" },
        { "$ref": "#/$defs/resourceItem" },
        { "$ref": "#/$defs/activitySummaryItem" }
      ]
    },
    "learningTargetItem": {
      "type": "object",
      "required": ["key", "value"],
      "properties": {
        "key": {
          "const": "学习目标"
        },
        "value": {
          "type": "object",
          "properties": {
            "知识点（学习水平）": { "type": "string" },
            "能力目标": { "type": "string" },
            "素质目标（课程思政点）": { "type": "string" }
          },
          "additionalProperties": true
        }
      },
      "additionalProperties": true
    },
    "prerequisiteItem": {
      "type": "object",
      "required": ["key", "value"],
      "properties": {
        "key": {
          "const": "学习先决知识"
        },
        "value": {
          "type": "object",
          "properties": {
            "知识点（学习水平）": { "type": "string" }
          },
          "additionalProperties": true
        }
      },
      "additionalProperties": true
    },
    "timeItem": {
      "type": "object",
      "required": ["key", "value"],
      "properties": {
        "key": {
          "enum": ["课上时间", "课下时间"]
        },
        "value": {
          "type": "string",
          "description": "如 45分钟"
        }
      },
      "additionalProperties": true
    },
    "resourceItem": {
      "type": "object",
      "required": ["key", "value"],
      "properties": {
        "key": {
          "enum": ["课上资源", "课下资源"]
        },
        "value": {
          "type": "string",
          "description": "按换行交替排列：资源类别、资源描述、资源类别、资源描述"
        }
      },
      "additionalProperties": true
    },
    "activitySummaryItem": {
      "type": "object",
      "required": ["key", "value"],
      "properties": {
        "key": {
          "const": "活动序列"
        },
        "sorted_names": {
          "type": "array",
          "description": "建议始终提供，决定活动顺序",
          "items": {
            "type": "string"
          }
        },
        "value": {
          "type": "object",
          "minProperties": 1,
          "additionalProperties": {
            "type": "array",
            "items": {
              "$ref": "#/$defs/activitySummaryRow"
            }
          }
        }
      },
      "additionalProperties": true
    },
    "activitySummaryRow": {
      "type": "object",
      "properties": {
        "活动目标": { "type": "string" },
        "地点": {
          "type": "string",
          "enum": ["课上", "课下"]
        },
        "学习地点": {
          "type": "string",
          "enum": ["课上", "课下"]
        },
        "时间": {
          "type": "string"
        },
        "学习资源": {
          "type": "string"
        }
      },
      "additionalProperties": true
    },
    "activityDetail": {
      "type": "object",
      "required": ["活动任务序列（任务）"],
      "properties": {
        "活动任务序列（导入任务描述）": {
          "type": "string"
        },
        "师生交互过程": {
          "type": "string",
          "description": "活动层面的简单文本描述"
        },
        "活动目标": {
          "type": "string"
        },
        "活动任务序列（任务）": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/taskItem"
          }
        }
      },
      "additionalProperties": true
    },
    "taskItem": {
      "type": "object",
      "required": [
        "任务名称",
        "任务描述",
        "任务时长",
        "学习地点",
        "教学方式（或学习方式）",
        "学习资源",
        "师生交互过程",
        "学习成果及评价标准"
      ],
      "properties": {
        "任务名称": {
          "type": "string",
          "maxLength": 50
        },
        "任务描述": {
          "type": "string",
          "maxLength": 500
        },
        "任务时长": {
          "type": "string"
        },
        "学习地点": {
          "type": "string",
          "enum": ["课上", "课下"]
        },
        "教学方式（或学习方式）": {
          "$ref": "#/$defs/teachingMethod"
        },
        "学习资源": {
          "type": "string"
        },
        "师生交互过程": {
          "$ref": "#/$defs/richTextWithImages"
        },
        "学习成果及评价标准": {
          "$ref": "#/$defs/richTextWithImages"
        },
        "备注": {
          "type": "string"
        }
      },
      "additionalProperties": true
    },
    "teachingMethod": {
      "type": "object",
      "properties": {
        "checkbox": {
          "type": "array",
          "minItems": 2,
          "maxItems": 2,
          "prefixItems": [
            {
              "type": "array",
              "items": {
                "type": "string"
              }
            },
            {
              "type": "array",
              "items": {
                "type": "integer",
                "minimum": 0
              }
            }
          ]
        },
        "checkbox_other": {
          "type": "string",
          "maxLength": 50
        }
      },
      "additionalProperties": true
    },
    "richTextWithImages": {
      "type": "object",
      "required": ["value", "images"],
      "properties": {
        "value": {
          "type": "array",
          "items": {
            "type": "string"
          }
        },
        "images": {
          "type": "array",
          "items": {
            "type": "string"
          }
        }
      },
      "additionalProperties": true
    }
  }
}
```
