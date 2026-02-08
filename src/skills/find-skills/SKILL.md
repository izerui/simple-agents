---
name: find-skills
description: Helps users discover and install agent skills when they ask questions like "how do I do X", "find a skill for X", "is there a skill that can...", or express interest in extending capabilities. This skill should be used when the user is looking for functionality that might exist as an installable skill.
---

# Find Skills

This skill helps you discover and install skills from the open agent skills ecosystem. It can find skills and automatically download them to your `/skills/` directory.

## When to Use This Skill

Use this skill when the user:

- Asks "how do I do X" where X might be a common task with an existing skill
- Says "find a skill for X" or "is there a skill for X"
- Asks "can you do X" where X is a specialized capability
- Expresses interest in extending agent capabilities
- Wants to search for tools, templates, or workflows
- Mentions they wish they had help with a specific domain (design, testing, deployment, etc.)
- Needs to download and install skills to the `/skills/` directory

## Installation Method

### 🚀 Use the Python Script

Install skills using the provided Python script with direct HTTP download:

**Key features:**
- ✅ **Zero dependencies** - Only requires Python 3.5+
- ✅ **Safe** - NEVER overwrites existing installations
- ✅ **Direct** - Downloads straight to `/skills/` directory
- ✅ **Flexible** - Supports npm, GitHub, and direct URLs
- ✅ **Complete** - Search + install + list functionality

### Quick Start

```bash
# Search for skills (no npx required!)
python3 /skills/find-skills/scripts/install_skill.py -s "react performance"

# Install a skill
python3 /skills/find-skills/scripts/install_skill.py vercel-labs/agent-skills@vercel-react-best-practices

# List installed skills
python3 /skills/find-skills/scripts/install_skill.py -l
```

### Installation Examples

**From GitHub (Recommended for agent skills):**
```bash
# Install specific skill from repository
python3 /skills/find-skills/scripts/install_skill.py vercel-labs/agent-skills@vercel-react-best-practices

# Install entire repository
python3 /skills/find-skills/scripts/install_skill.py vercel-labs/agent-skills

# Install from specific tag
python3 /skills/find-skills/scripts/install_skill.py vercel-labs/agent-skills@v1.0.0
```

**From npm registry:**
```bash
# Install latest version
python3 /skills/find-skills/scripts/install_skill.py create-react-app

# Install specific version
python3 /skills/find-skills/scripts/install_skill.py create-react-app@5.0.1
```

**From direct URL:**
```bash
python3 /skills/find-skills/scripts/install_skill.py https://example.com/skill-package.tar.gz
```

**From local tarball file:**
```bash
# Install from local .tgz or .tar.gz file
python3 /skills/find-skills/scripts/install_skill.py /path/to/skill-package.tar.gz
python3 /skills/find-skills/scripts/install_skill.py ./my-skill.tgz
```

### Available Commands

```bash
# Search for skills (no npx required!)
python3 /skills/find-skills/scripts/install_skill.py -s "query"

# Install to custom directory
python3 /skills/find-skills/scripts/install_skill.py -d /path/to/skills <package>

# List installed skills
python3 /skills/find-skills/scripts/install_skill.py -l

# Show help
python3 /skills/find-skills/scripts/install_skill.py --help
```

## How to Help Users Find Skills

### Step 1: Understand What They Need

When a user asks for help with something, identify:

1. The domain (e.g., React, testing, design, deployment)
2. The specific task (e.g., writing tests, creating animations, reviewing PRs)
3. Whether this is a common enough task that a skill likely exists

### Step 2: Search for Skills

**Option A: Use the script's search feature (no npx required!):**
```bash
python3 /skills/find-skills/scripts/install_skill.py -s "react performance"
```

The search will:
- Search GitHub for popular skill repositories
- Suggest relevant npm packages
- Provide manual search links

**Option B: Browse manually:**
Visit https://skills.sh/ to explore available skills

**Option C: Try common skill sources:**
Many skills come from:
- `vercel-labs/agent-skills` - Vercel's collection of agent skills
- `ComposioHQ/awesome-claude-skills` - Community-maintained list

### Step 3: Present Options to the User

When you find relevant skills, present them clearly:

```
I found a skill that might help! The "vercel-react-best-practices" skill provides
React and Next.js performance optimization guidelines from Vercel Engineering.

To install it:
python3 /skills/find-skills/scripts/install_skill.py vercel-labs/agent-skills@vercel-react-best-practices

Learn more: https://skills.sh/vercel-labs/agent-skills/vercel-react-best-practices
```

### Step 4: Install the Skill

If the user wants to proceed, install it directly:

```bash
python3 /skills/find-skills/scripts/install_skill.py <package_spec>
```

The script will:
- ✅ Download via HTTP (no npx needed)
- ✅ Extract to `/skills/` directory
- ✅ Skip if already installed (never overwrites)
- ✅ Clean up temporary files automatically

## Common Skill Categories

When searching, consider these common categories:

| Category        | Example Queries                          |
| --------------- | ---------------------------------------- |
| Web Development | react, nextjs, typescript, css, tailwind |
| Testing         | testing, jest, playwright, e2e           |
| DevOps          | deploy, docker, kubernetes, ci-cd        |
| Documentation   | docs, readme, changelog, api-docs        |
| Code Quality    | review, lint, refactor, best-practices   |
| Design          | ui, ux, design-system, accessibility     |
| Productivity    | workflow, automation, git                |

## Technical Details

### How It Works (Direct HTTP Download)

This script downloads and installs skills using direct HTTP requests:

**1. Query Package Registry:**
```python
GET https://registry.npmjs.org/<package>
→ Returns JSON with versions and tarball URL
```

**2. Download Tarball:**
```python
urllib.request.urlretrieve(tarball_url, temp_path)
→ Downloads .tgz file via HTTP
```

**3. Extract Tarball (Pure Python):**
```python
tarfile.open(tarball_path, 'r:gz').extractall(dest_dir)
→ Extracts .tgz files using Python's tarfile module
→ No external commands (tar, gzip) required
```

**4. Install to Skills Directory:**
```python
shutil.copytree(extracted_dir, skills_dir/package_name)
→ Copies extracted files to /skills/<package-name>/
→ Uses Python's shutil for file operations
```

**5. Anti-Overwrite Protection:**
```python
if target_dir.exists():
    ⚠ Skip installation (NEVER overwrites)
else:
    ✓ Install fresh copy
```

All operations use **only Python standard library** - no external commands required.

### Supported Package Formats

**1. GitHub repositories:**
```
owner/repo
owner/repo@tag
owner/repo@branch
owner/repo@tag/path/to/skill
```

**2. npm packages:**
```
package-name
package-name@version
package@1.2.3
```

**3. Direct URLs:**
```
https://registry.npmjs.org/package/-/package-1.0.0.tgz
https://github.com/owner/repo/archive/refs/tags/v1.0.0.tar.gz
https://example.com/skill-package.tar.gz
```

**4. Local tarball files:**
```
/path/to/skill-package.tar.gz
./my-skill.tgz
~/Downloads/skill.tar.bz2
```

## Tips for Effective Searches

1. **Use specific keywords**: "react testing" is better than just "testing"
2. **Try alternative terms**: If "deploy" doesn't work, try "deployment" or "ci-cd"
3. **Check popular sources**: Many skills come from `vercel-labs/agent-skills`
4. **Browse manually**: Visit https://skills.sh/ to explore

## When No Skills Are Found

If no relevant skills exist:

1. Acknowledge that no existing skill was found
2. Offer to help with the task directly using your general capabilities
3. Suggest the user could create their own skill

Example:

```
I searched for skills related to "xyz" but didn't find any matches.
I can still help you with this task directly! Would you like me to proceed?

If this is something you do often, you could create your own skill
using the template in /skills/find-skills/
```

## Troubleshooting

**Problem:** Command not found or Python 2 error
```bash
# Solution: Use python3 instead of python
python3 /skills/find-skills/scripts/install_skill.py <package>
```

**Problem:** Permission denied
```python
# Solution: Make sure /skills/ directory is writable
python3 -c "import os; os.chmod('/skills/', 0o755)"
```

**Problem:** Skill already exists
```python
# This is expected behavior! The script never overwrites.
# To reinstall, first delete the existing skill:
python3 -c "import shutil; shutil.rmtree('/skills/<skill-name>')"

# Then install again
python3 /skills/find-skills/scripts/install_skill.py <package>
```

**Note:** This script uses only Python standard library - no external commands required.
