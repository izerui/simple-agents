---
name: flowchart-generator
description: 使用 Mermaid 语法生成流程图、序列图、思维导图等多种图表
---

# Flowchart Generator - 流程图生成技能

## 技能概述

这个技能使用 Mermaid 语法来生成各种类型的图表，包括：
- 流程图 (Flowchart)
- 序列图 (Sequence Diagram)
- 类图 (Class Diagram)
- 状态图 (State Diagram)
- 实体关系图 (ER Diagram)
- 用户旅程图 (User Journey)
- 甘特图 (Gantt Chart)
- 思维导图 (Mindmap)
- 饼图 (Pie Chart)

## 何时使用此技能

当用户需要：
- 创建流程图或流程图
- 绘制序列图或时序图
- 生成思维导图
- 创建类图或架构图
- 绘制甘特图或项目计划
- 生成任何类型的可视化图表

## Mermaid 语法快速参考

### 1. 流程图 (Flowchart)

```mermaid
graph TD
    A[开始] --> B{判断条件}
    B -->|是| C[执行操作A]
    B -->|否| D[执行操作B]
    C --> E[结束]
    D --> E
```

**方向说明：**
- `TD` - 从上到下 (Top to Down)
- `DT` - 从下到上 (Down to Top)
- `LR` - 从左到右 (Left to Right)
- `RL` - 从右到左 (Right to Left)

**形状说明：**
- `[文本]` - 矩形
- `(文本)` - 圆角矩形
- `{文本}` - 菱形（判断）
- `[(文本)]` - 圆柱形
- `[[文本]]` - 子程序

### 2. 序列图 (Sequence Diagram)

```mermaid
sequenceDiagram
    participant 用户
    participant 系统
    participant 数据库

    用户->>系统: 发送请求
    系统->>数据库: 查询数据
    数据库-->>系统: 返回结果
    系统-->>用户: 响应数据
```

### 3. 类图 (Class Diagram)

```mermaid
classDiagram
    class Animal {
        +String name
        +int age
        +eat()
        +sleep()
    }
    class Dog {
        +bark()
        +fetch()
    }
    Animal <|-- Dog
```

### 4. 思维导图 (Mindmap)

```mermaid
mindmap
  root((主题))
    分支1
      子分支1.1
      子分支1.2
    分支2
      子分支2.1
      子分支2.2
```

### 5. 甘特图 (Gantt Chart)

```mermaid
gantt
    title 项目计划
    dateFormat  YYYY-MM-DD
    section 设计
    需求分析   :a1, 2024-01-01, 7d
    系统设计   :a2, after a1, 7d
    section 开发
    前端开发   :b1, after a2, 14d
    后端开发   :b2, after a2, 14d
```

### 6. 状态图 (State Diagram)

```mermaid
stateDiagram-v2
    [*] --> 待处理
    待处理 --> 处理中: 开始处理
    处理中 --> 已完成: 处理成功
    处理中 --> 失败: 处理失败
    失败 --> 待处理: 重试
    已完成 --> [*]
```

### 7. 实体关系图 (ER Diagram)

```mermaid
erDiagram
    CUSTOMER ||--o{ ORDER : places
    ORDER ||--|{ LINE-ITEM : contains
    CUSTOMER }|..|{ DELIVERY-ADDRESS : uses
```

## 使用方法

### 在线渲染（推荐）

1. **Mermaid Live Editor** - https://mermaid.live
   - 实时预览
   - 导出为 SVG/PNG
   - 分享链接

2. **Markdown 编辑器**
   - Typora
   - Obsidian
   - VS Code (with Mermaid 插件)

### 命令行使用

```bash
# 安装 Mermaid CLI
npm install -g @mermaid-js/mermaid-cli

# 将 mmd 文件转换为 PNG
mmdc -i input.mmd -o output.png

# 转换为 SVG
mmdc -i input.mmd -o output.svg

# 指定主题
mmdc -i input.mmd -o output.png -t dark
```

## 实用技巧

### 1. 样式定制

```mermaid
graph TD
    A[开始] --> B[结束]

    style A fill:#f9f,stroke:#333,stroke-width:4px
    style B fill:#bbf,stroke:#333,stroke-width:2px
```

### 2. 子图

```mermaid
graph TD
    subgraph 子图1
        A1[节点1]
        A2[节点2]
        A1 --> A2
    end

    subgraph 子图2
        B1[节点3]
        B2[节点4]
        B1 --> B2
    end

    A2 --> B1
```

### 3. 链接标签

```mermaid
graph LR
    A[开始] -->|条件1| B[结果1]
    A -->|条件2| C[结果2]
    A -->|条件3| D[结果3]
```

## 常见问题

**Q: 如何调整图表大小？**
A: Mermaid 会自动调整大小。如果需要固定尺寸，可以在导出时指定。

**Q: 支持中文吗？**
A: 完全支持中文，但建议使用 UTF-8 编码。

**Q: 如何在 Markdown 中使用？**
A: 直接使用 ```mermaid 代码块包裹语法即可。

**Q: 图表太复杂怎么办？**
A: 考虑拆分成多个子图，或使用更简洁的表示方式。

## 示例模板

### 业务流程图模板

```mermaid
graph TD
    Start([开始]) --> Input[输入数据]
    Input --> Validate{数据验证}
    Validate -->|通过| Process[处理数据]
    Validate -->|失败| Error[记录错误]
    Error --> End([结束])
    Process --> Save[保存结果]
    Save --> End
```

### 系统架构图模板

```mermaid
graph TB
    Client[客户端] --> LoadBalancer[负载均衡器]
    LoadBalancer --> Server1[服务器1]
    LoadBalancer --> Server2[服务器2]
    Server1 --> Cache[(缓存)]
    Server2 --> Cache
    Server1 --> Database[(数据库)]
    Server2 --> Database
```

### API 序列图模板

```mermaid
sequenceDiagram
    actor User as 用户
    participant API as API网关
    participant Service as 业务服务
    participant DB as 数据库

    User->>API: 发起请求
    API->>Service: 转发请求
    Service->>DB: 查询数据
    DB-->>Service: 返回数据
    Service-->>API: 处理结果
    API-->>User: 响应结果
```

## 资源链接

- 官方文档: https://mermaid.js.org/
- 在线编辑器: https://mermaid.live
- GitHub: https://github.com/mermaid-js/mermaid
- 语法文档: https://mermaid.js.org/syntax/reference.html

## 更新日志

- v1.0.0 - 初始版本，支持基本的图表生成
