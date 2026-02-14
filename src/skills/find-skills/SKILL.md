---
name: find-skills
description: 帮助用户发现和安装技能。当用户问"怎么做X"、"找一个X的技能"、"有没有能做X的技能"，或表达扩展能力的意愿时使用此技能。
---

# 技能查找

帮助用户从开放技能生态系统中发现和安装技能，可以查找技能并自动下载到 `/skills/` 目录。

## 使用场景

当用户：

- 问"怎么做X"，X 可能是常见任务
- 说"找一个X的技能"或"有没有X的技能"
- 问"你能做X吗"，X 是专门的能力
- 表达扩展 Agent 能力的意愿
- 想要搜索工具、模板或工作流
- 提到希望在特定领域获得帮助（设计、测试、部署等）
- 需要下载并安装技能到 `/skills/` 目录
- **探索技能类型**：问"有哪些技能"、"技能分类"
- **模糊查询**：问"操作 word 文档的技能有哪些"

## 探索技能（AI 语义搜索）

当用户没有指明具体的关键字，而是进行模糊查询时，使用 AI 语义搜索：

**使用场景：**
- "有哪些技能"
- "技能分类"
- "操作 word 文档的技能有哪些"
- "数据分析相关的技能"

**命令：**
```bash
# 使用 AI 语义搜索探索技能
python /skills/find-skills/scripts/install_skill.py -e "操作 word 文档的技能"
python /skills/find-skills/scripts/install_skill.py -e "有哪些数据分析的技能"
```

**AI 搜索 vs 关键词搜索：**

| 搜索方式 | 命令参数 | 适用场景 |
|---------|---------|---------|
| AI 语义搜索 | `-e` | 模糊查询、自然语言问题、探索技能类型 |
| 关键词搜索 | `-s` | 明确的关键词、精确搜索 |

## 安装方法

### Python 脚本安装

使用提供的 Python 脚本通过 HTTP 直接下载安装：

**核心特性：**
- ✅ **零依赖** - 仅需 Python 3.5+
- ✅ **安全** - 永不覆盖已有安装
- ✅ **直接** - 直接下载到 `/skills/` 目录
- ✅ **灵活** - 支持 npm、GitHub 和直接 URL
- ✅ **完整** - 搜索 + 安装 + 列表功能
- ✅ **智能过滤** - 按 SKILL.md name 字段过滤

### 快速开始

```bash
# 搜索技能
python /skills/find-skills/scripts/install_skill.py -s "react performance"

# 安装特定技能（按 SKILL.md name 过滤）
python /skills/find-skills/scripts/install_skill.py vercel-labs/agent-skills/vercel-react-best-practices

# 列出已安装技能
python /skills/find-skills/scripts/install_skill.py -l
```

### 安装示例

**从 GitHub 安装（推荐）：**
```bash
# 按技能名安装（匹配 SKILL.md 中的 name 字段）
python /skills/find-skills/scripts/install_skill.py vercel-labs/agent-skills/vercel-react-best-practices

# 按路径安装技能
python /skills/find-skills/scripts/install_skill.py owner/repo/skills/my-skill

# 安装仓库中的所有技能（不过滤）
python /skills/find-skills/scripts/install_skill.py vercel-labs/agent-skills
```

**从 npm registry 安装：**
```bash
# 安装最新版本
python /skills/find-skills/scripts/install_skill.py create-react-app

# 安装特定版本
python /skills/find-skills/scripts/install_skill.py create-react-app@5.0.1
```

**从直接 URL 安装：**
```bash
# tarball URL
python /skills/find-skills/scripts/install_skill.py https://example.com/skill-package.tar.gz

# GitHub tree URL（从 SkillsMP 搜索结果复制）
python /skills/find-skills/scripts/install_skill.py https://github.com/owner/repo/tree/main/path/to/skill
```

**从本地 tarball 文件安装：**
```bash
python /skills/find-skills/scripts/install_skill.py /path/to/skill-package.tar.gz
python /skills/find-skills/scripts/install_skill.py ./my-skill.tgz
```

### 可用命令

```bash
# 搜索技能（关键词搜索）
python /skills/find-skills/scripts/install_skill.py -s "查询关键词"

# 探索技能（AI 语义搜索，用于模糊查询）
python /skills/find-skills/scripts/install_skill.py -e "操作 word 文档的技能"
python /skills/find-skills/scripts/install_skill.py -e "有哪些数据分析的技能"

# 安装到自定义目录
python /skills/find-skills/scripts/install_skill.py -d /path/to/skills <package>

# 列出已安装技能
python /skills/find-skills/scripts/install_skill.py -l

# 显示帮助
python /skills/find-skills/scripts/install_skill.py --help
```

## 帮助用户查找技能

### 步骤 1：理解用户需求

当用户请求帮助时，识别：

1. 领域（如 React、测试、设计、部署）
2. 具体任务（如编写测试、创建动画、审查 PR）
3. 是否是常见任务，可能有现成技能

### 步骤 2：搜索技能

**搜索优先级顺序：**

| 优先级 | 来源 | 说明 |
|--------|------|------|
| 1 | **skills.sh** | 专门的技能目录（优先搜索） |
| 2 | **SkillsMP** | 技能市场，支持关键词搜索和 AI 语义搜索 |
| 3 | **npm registry** | npm 包搜索 |
| 4 | **GitHub** | 搜索流行仓库并提供手动搜索链接 |

**使用脚本搜索：**
```bash
python /skills/find-skills/scripts/install_skill.py -s "react performance"
```

**手动浏览：**
访问 https://skills.sh/ 探索可用技能

**常见技能来源：**
- `vercel-labs/agent-skills` - Vercel 的 Agent 技能集合
- `expo/skills` - Expo 官方技能
- `ComposioHQ/awesome-claude-skills` - 社区维护列表

### 步骤 3：向用户展示选项

找到相关技能后，清晰展示：

```
我找到一个可能有帮助的技能！"vercel-react-best-practices" 技能提供了
来自 Vercel Engineering 的 React 和 Next.js 性能优化指南。

安装命令：
python /skills/find-skills/scripts/install_skill.py vercel-labs/agent-skills/vercel-react-best-practices

了解更多：https://skills.sh/vercel-labs/agent-skills/vercel-react-best-practices
```

### 步骤 4：安装技能

如果用户确认，直接安装：

```bash
python /skills/find-skills/scripts/install_skill.py <package_spec>
```

脚本会：
- ✅ 通过 HTTP 下载（无需 npx）
- ✅ 解压到 `/skills/` 目录
- ✅ 按 SKILL.md name 字段过滤（如果指定了技能名）
- ✅ 跳过已安装的技能（永不覆盖）
- ✅ 自动清理临时文件

## 常见技能类别

搜索时，考虑以下常见类别：

| 类别 | 示例查询 |
|------|----------|
| Web 开发 | react, nextjs, typescript, css, tailwind |
| 测试 | testing, jest, playwright, e2e |
| DevOps | deploy, docker, kubernetes, ci-cd |
| 文档 | docs, readme, changelog, api-docs |
| 代码质量 | review, lint, refactor, best-practices |
| 设计 | ui, ux, design-system, accessibility |
| 效率 | workflow, automation, git |

## 技术细节

### 技能过滤机制

指定技能名时，脚本按 SKILL.md 中的 `name` 字段过滤：

```
owner/repo/skill-name
  ↑        ↑
仓库     技能名（匹配 SKILL.md 中的 name 字段）
```

**示例：**
```bash
# 只安装 SKILL.md 中 name: expo-deployment 的技能
python /skills/find-skills/scripts/install_skill.py expo/skills/expo-deployment
```

匹配不区分大小写，支持 `-`、`_` 和空格互通。

### 工作原理（直接 HTTP 下载）

脚本通过直接 HTTP 请求下载和安装技能：

```
仓库 → 下载到 /tmp/ → 解压 → 查找 SKILL.md → 过滤 → 安装到 /skills/
```

**工作流程：**

1. **查询包仓库：**
   - 从 npm registry 或 GitHub 获取包信息

2. **下载 Tarball 到 /tmp/：**
   - 下载 .tgz 文件到临时目录

3. **在 /tmp/ 中解压：**
   - 解压 tarball 到临时目录

4. **查找 SKILL.md 文件：**
   - 递归查找包含 SKILL.md 的文件夹
   - 如果指定了技能名，按 name 字段过滤

5. **安装到 /skills/：**
   - 将技能文件夹复制到 `/skills/` 目录

6. **防覆盖保护：**
   - 如果 `/skills/<package>/` 已存在，跳过安装

所有操作仅使用 **Python 标准库** - 无需外部命令。

### 支持的包格式

**1. GitHub 仓库：**
```
owner/repo                    # 安装所有技能
owner/repo/skill-name         # 安装特定技能（按 SKILL.md name 过滤）
owner/repo/path/skill-name    # 从子目录安装
```

**2. npm 包：**
```
package-name
package-name@version
package@1.2.3
```

**3. 直接 URL：**
```
https://registry.npmjs.org/package/-/package-1.0.0.tgz
https://github.com/owner/repo/archive/refs/tags/v1.0.0.tar.gz
https://example.com/skill-package.tar.gz
```

**4. 本地 tarball 文件：**
```
/path/to/skill-package.tar.gz
./my-skill.tgz
~/Downloads/skill.tar.bz2
```

## 搜索技巧

1. **使用具体关键词**："react testing" 比 "testing" 更好
2. **尝试替代词**：如果 "deploy" 没找到，试试 "deployment" 或 "ci-cd"
3. **检查热门来源**：许多技能来自 `vercel-labs/agent-skills`、`expo/skills`
4. **手动浏览**：访问 https://skills.sh/ 探索

## 未找到技能时

如果没有找到相关技能：

1. 告知用户没有找到现有技能
2. 主动提出使用通用能力帮助完成任务
3. 建议用户可以创建自己的技能

示例：

```
我搜索了与 "xyz" 相关的技能但没有找到匹配项。
我仍然可以直接帮你完成这个任务！要继续吗？

如果你经常需要这个功能，可以使用 /skills/find-skills/ 中的模板
创建自己的技能。
```

## 故障排除

**问题：找不到命令或 Python 2 错误**
```bash
# 解决方案：使用 python3
python3 /skills/find-skills/scripts/install_skill.py <package>
```

**问题：权限被拒绝**
```bash
# 解决方案：确保 /skills/ 目录可写
python -c "import os; os.chmod('/skills/', 0o755)"
```

**问题：技能已存在**
```bash
# 这是预期行为！脚本永不覆盖。
# 要重新安装，先删除现有技能：
python -c "import shutil; shutil.rmtree('/skills/<skill-name>')"

# 然后再次安装
python /skills/find-skills/scripts/install_skill.py <package>
```

**问题：找不到技能（过滤未匹配）**
```bash
# 技能名必须匹配 SKILL.md 中的 "name:" 字段
# 查看仓库中的 SKILL.md 文件确认正确的名称
# 示例：如果 SKILL.md 中有 "name: vercel-react-best-practices"
python /skills/find-skills/scripts/install_skill.py vercel-labs/agent-skills/vercel-react-best-practices
```

**注意：** 此脚本仅使用 Python 标准库 - 无需外部命令。
