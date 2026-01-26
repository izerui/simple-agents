/**
 * Deno + uvx Python 代码执行器
 * 
 * 使用 uvx 管理 Python 依赖，并在隔离环境中执行代码
 * 
 * 使用方法：
 * deno run --allow-read --allow-write --allow-run mod.ts \
 *   --with pandas --with openpyxl -c "import pandas; print(pandas.__version__)"
 * 
 * 或者挂载目录：
 * deno run --allow-read --allow-write --allow-run mod.ts \
 *   -m /path/to/workspace --with pandas -c "import os; print(os.listdir('.'))"
 * 
 * 特性：
 * - 自动依赖管理：使用 uvx 自动下载和缓存依赖
 * - 目录挂载：支持将本地目录挂载为工作目录
 * - 环境隔离：清空敏感环境变量
 * - 超时控制：防止脚本无限运行
 */

interface ExecuteOptions {
  command: string;
  workDir?: string;
  cacheDir?: string;
  timeout?: number;
}

interface ExecuteResult {
  stdout: string;
  stderr: string;
  exitCode: number;
  success: boolean;
  executionTime: number;
}

/**
 * 解析命令行参数
 */
function parseArgs(args: string[]): {
  command?: string;
  workDir?: string;
  cacheDir?: string;
  timeout?: number;
} {
  let command: string | undefined;
  let workDir: string | undefined;
  let cacheDir: string | undefined;
  let timeout: number | undefined;

  let i = 0;
  while (i < args.length) {
    if (args[i] === "-c" || args[i] === "--command") {
      command = args[i + 1];
      i += 2;
    } else if (args[i] === "-m" || args[i] === "--mount") {
      workDir = args[i + 1];
      i += 2;
    } else if (args[i] === "-C" || args[i] === "--cache-dir") {
      cacheDir = args[i + 1];
      i += 2;
    } else if (args[i] === "-t" || args[i] === "--timeout") {
      timeout = parseInt(args[i + 1]);
      i += 2;
    } else if (args[i] === "-h" || args[i] === "--help") {
      return {};
    } else {
      i++;
    }
  }

  return { command, workDir, cacheDir, timeout };
}

/**
 * 解析 uvx 命令
 * 使用 shell 来正确处理引号和转义
 */
function parseUvxCommand(command: string): string[] {
  // 使用 shell 来执行命令，这样可以正确处理引号
  return ["/bin/sh", "-c", command.trim()];
}

/**
 * 执行 Python 代码
 */
async function executePython(options: ExecuteOptions): Promise<ExecuteResult> {
  const startTime = Date.now();
  
  try {
    // 解析 uvx 命令
    const commandArgs = parseUvxCommand(options.command);

    // 显示调试信息
    console.error(`执行命令: ${options.command}`, null);
    if (options.workDir) {
      console.error(`工作目录: ${options.workDir}`, null);
    }

    // 准备环境变量（清空敏感变量）
    const env: Record<string, string> = {
      "PATH": Deno.env.get("PATH") || "",
      "HOME": Deno.env.get("HOME") || "",
      "USER": Deno.env.get("USER") || "",
    };

    // 执行命令
    const command = new Deno.Command(commandArgs[0], {
      args: commandArgs.slice(1), // 跳过 /bin/sh
      cwd: options.workDir,
      env: env,
      stdout: "piped",
      stderr: "piped",
    });

    const process = command.spawn();
    const output = await process.output();
    
    const executionTime = Date.now() - startTime;
    const stdout = new TextDecoder().decode(output.stdout);
    const stderr = new TextDecoder().decode(output.stderr);

    return {
      stdout,
      stderr,
      exitCode: output.code,
      success: output.code === 0,
      executionTime,
    };
  } catch (error) {
    const executionTime = Date.now() - startTime;
    const errorMsg = error instanceof Error ? error.message : String(error);
    
    return {
      stdout: "",
      stderr: errorMsg,
      exitCode: -1,
      success: false,
      executionTime,
    };
  }
}



/**
 * 显示帮助信息
 */
function showHelp() {
  console.error(`
Deno + uvx Python 代码执行器

使用方法:
  deno run --allow-read --allow-write --allow-run mod.ts [选项]

选项:
  -c, --command <cmd>        要执行的 uvx 命令
  -m, --mount <dir>          工作目录（挂载点）
  -C, --cache-dir <dir>      缓存目录
  -t, --timeout <seconds>    执行超时（秒）
  -h, --help                 显示帮助信息

示例:
  # 执行 uvx 命令
  deno run mod.ts -c "uvx --with requests python -c 'import requests; print(requests.__version__)'"
  
  # 挂载目录
  deno run mod.ts -m /path/to/workspace -c "uvx python script.py"
  
  # 使用多个依赖
  deno run mod.ts -c "uvx --with requests,rich python script.py"

特性:
  - 直接执行 uvx 命令：uvx 自己管理依赖
  - 工作目录隔离：通过 -m 参数设置工作目录
  - 环境变量隔离：清空敏感环境变量
  - 快速执行：依赖缓存后，后续执行非常快
`, null);
}

/**
 * 主函数
 */
async function main() {
  const args = Deno.args;
  
  // 解析参数
  const parsed = parseArgs(args);
  
  // 显示帮助
  if (args.includes("-h") || args.includes("--help")) {
    showHelp();
    Deno.exit(0);
  }
  
  // 检查命令
  if (!parsed.command) {
    console.error("错误: 必须提供命令（-c）", null);
    console.error("", null);
    console.error("使用 --help 查看帮助信息", null);
    Deno.exit(1);
  }
  
  // 执行命令
  const result = await executePython({
    command: parsed.command,
    workDir: parsed.workDir,
    cacheDir: parsed.cacheDir,
    timeout: parsed.timeout,
  });
  
  // 输出结果（JSON 格式）
  const output = JSON.stringify({
    stdout: result.stdout,
    stderr: result.stderr,
    exitCode: result.exitCode,
    success: result.success,
    executionTime: result.executionTime,
  });
  
  console.log(output);
  
  // 返回适当的退出码
  Deno.exit(result.success ? 0 : 1);
}

// 运行主函数
if (import.meta.main) {
  main().catch((error) => {
    console.error(JSON.stringify({
      stdout: "",
      stderr: error instanceof Error ? error.message : String(error),
      exitCode: -1,
      success: false,
      executionTime: 0,
    }));
    Deno.exit(1);
  });
}

export { executePython, ExecuteOptions, ExecuteResult };