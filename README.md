# Simple Agents

debug:
```
uv pip install -U "langgraph-cli[inmem]"
```

A sophisticated AI research agent framework built with LangGraph and DeepAgents, designed to conduct comprehensive web research with strategic thinking and context management.

## Features

- **Multi-Agent Research System**: Orchestrates research tasks with specialized sub-agents
- **Sandbox File System**: Per-conversation sandbox isolation with automatic cleanup via FileUploadMiddleware
- **File Upload**: Automatic file upload handling with files copied to sandbox_sessions/{thread_id}/
- **Strategic Thinking**: Built-in reflection tool (think_tool) for systematic research decision-making
- **Streaming Output**: Real-time token-level streaming with node execution monitoring
- **Tool Call Limits**: Configurable middleware to prevent excessive tool usage
- **Markdown Processing**: Converts web content to markdown for easy consumption
- **Rich Display**: Utilities for formatting messages and prompts in Jupyter notebooks

## Architecture

The system consists of several key components:

- **`agent.py`**: Main agent orchestration with sub-agent delegation
- **`main.py`**: Entry point for running the agent with streaming events
- **`tools.py`**: Research tools including file operations and reflection
- **`prompts.py`**: Research workflow instructions and agent prompts
- **`file_upload_middleware.py`**: File upload middleware with sandbox management
- **`utils.py`**: Utilities for displaying messages and prompts with rich formatting

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd simple-agents
```

2. Install dependencies using uv:
```bash
uv sync
```

3. Create a `.env` file in the project root:
```env
MODEL_BASE_URL=your_model_base_url
MODEL_API_KEY=your_api_key
MODEL_MODEL_ID=your_model_id
```

## Usage

Run the research agent:

```bash
python main.py
```

The agent will execute with streaming output, showing:
- Node completion status
- Real-time token streaming
- Research progress and findings
- Sandbox directory creation and file uploads

## Configuration

### Research Limits

Configure in `agent.py`:
- `max_concurrent_research_units`: Maximum parallel sub-agents (default: 3)
- `max_researcher_iterations`: Maximum delegation rounds (default: 3)
- Tool call limits per run (default: 50)
- Recursion limit (default: 50)

### Sandbox Configuration

The `FileUploadMiddleware` provides per-conversation file system isolation:
- Each conversation gets a unique sandbox directory under `sandbox_sessions/{thread_id}/`
- Files uploaded via agent-chat-ui are automatically copied to the sandbox directory
- Automatic cleanup of sandbox directories after conversations
- Uses ContextVar to track thread_id across the conversation lifecycle

### Model Settings

The agent supports configurable LLM models through environment variables. It defaults to using Claude 4.5.

## Project Structure

```
simple-agents/
├── agent.py              # Agent orchestration and sub-agent setup
├── main.py               # Entry point with streaming execution
├── tools.py              # Research tools (file ops, reflection)
├── prompts.py            # Research workflow instructions
├── file_upload_middleware.py  # File upload middleware with sandbox management
├── utils.py              # Utilities for rich message display
├── pyproject.toml        # Project dependencies
├── langgraph.json        # LangGraph configuration
├── .env                  # Environment variables (create this)
├── uploads/              # Temporary upload directory
└── sandbox_sessions/     # Per-conversation sandbox directories (created automatically)
```

## Research Workflow

The agent follows a systematic research process:

1. **Plan**: Break down research into focused tasks using todos
2. **Save Request**: Store research questions to `/deepagent_request.md`
3. **Upload Files**: Files uploaded via UI are automatically copied to sandbox directory
4. **Research**: Delegate to specialized sub-agents with file reading
5. **Reflect**: Use think_tool after each operation for strategic thinking
6. **Synthesize**: Consolidate findings and citations
7. **Write**: Generate comprehensive reports to `/final_report.md`
8. **Verify**: Ensure all aspects are addressed with proper citations

## Key Components

### FileUploadMiddleware

Provides automatic file upload handling and sandbox management:
- `set_thread_id(thread_id)`: Sets the current conversation thread_id
- `get_sandbox_dir(thread_id)`: Creates and returns the sandbox directory path
- `handle_message(message, thread_id)`: Processes file attachments in messages
- `pre_tool_call(tool_name, tool_args, thread_id)`: Handles file uploads in tool calls
- Uses ContextVar (`_current_thread_id`) to track thread_id across operations
- Automatically handles file naming conflicts by appending timestamps

### Research Tools

- **think_tool**: Strategic reflection tool for decision-making during research
- **list_files**: Lists files in specified directories
- File system operations through virtual backend (read, write, ls)

## Dependencies

- `deepagents>=0.3.1` - Agent framework with sub-agent orchestration
- `langchain-deepseek>=1.0.1` - LangChain DeepSeek integration
- `langchain-openai>=1.1.6` - LangChain OpenAI integration
- `langgraph-cli>=0.4.11` - LangGraph command-line tools
- `markdownify>=1.2.2` - HTML to markdown conversion
- `sse-starlette>=3.1.1` - Server-sent events support
- `rich>=14.2.0` - Rich terminal and Jupyter notebook formatting
- `load-dotenv>=0.1.0` - Environment variable loading

## License

This project is provided as-is for educational and research purposes.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.