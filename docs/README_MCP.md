# MCP Server Setup Instructions

## What is This?

This MCP (Model Context Protocol) server exposes the Cerina Protocol Foundry multi-agent workflow as a tool that Claude Desktop can use directly.

## Installation

### 1. Install MCP Package

```bash
/usr/local/bin/python3.11 -m pip install --user mcp
```

### 2. Configure Claude Desktop

**Location of config file:**
- **Mac**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

**Create or edit the file:**

```json
{
  "mcpServers": {
    "cerina-foundry": {
      "command": "/usr/local/bin/python3.11",
      "args": [
        "/Users/dishaarora/Desktop/cerina-health-assignment/mcp_server.py"
      ],
      "env": {
        "OPENAI_API_KEY": "your-key-here"
      }
    }
  }
}
```

**⚠️ Important**: 
- Replace the path with your actual path
- Add your OpenAI API key
- Restart Claude Desktop after saving

### 3. Verify Installation

1. Restart Claude Desktop
2. Look for the 🔌 icon in Claude Desktop (shows MCP servers)
3. You should see "cerina-foundry" connected

## Usage

### In Claude Desktop Chat:

```
You: "I'm struggling with social anxiety. Can you use Cerina Foundry to create a CBT exercise?"

Claude: [Uses create_cbt_exercise tool]
        [Multi-agent collaboration happens]
        
        📋 Social Anxiety Exposure Hierarchy
        ✅ Safety Score: 1.0 | Empathy: 1.0
        
        [Full CBT exercise]
```

### Example Prompts:

- "Use Cerina Foundry to create a sleep hygiene protocol"
- "I need help with perfectionism - ask Cerina Foundry"
- "Create a CBT exercise for managing work stress using the Cerina tool"

## Testing Manually

You can also test the MCP server directly:

```bash
cd /Users/dishaarora/Desktop/cerina-health-assignment
/usr/local/bin/python3.11 mcp_server.py
```

Then send MCP protocol messages via stdin/stdout.

## Troubleshooting

### Tool Not Showing in Claude

1. Check Claude Desktop config file is correct
2. Restart Claude Desktop completely
3. Check logs: `~/Library/Logs/Claude/`

### OpenAI API Errors

Make sure `.env` file has `OPENAI_API_KEY` or set it in the MCP config.

### Import Errors

Verify all packages installed:
```bash
/usr/local/bin/python3.11 -m pip list | grep -E "(langchain|langgraph|mcp)"
```

## Architecture

```
Claude Desktop
    ↓ MCP Protocol
MCP Server (mcp_server.py)
    ↓ Function Call
LangGraph Multi-Agent Workflow
    ├─ Supervisor
    ├─ Drafter
    ├─ Safety Guardian
    └─ Clinical Critic
    ↓ Result
Formatted CBT Exercise
    ↓ MCP Response
Claude Desktop
    ↓ Display
User
```

## What Happens Behind the Scenes

1. **User prompts Claude** with request
2. **Claude calls MCP tool** `create_cbt_exercise`
3. **MCP server receives** the request
4. **Initializes LangGraph** workflow with checkpointing
5. **Agents collaborate:**
   - Supervisor routes
   - Drafter creates
   - Safety Guardian reviews
   - Clinical Critic reviews
   - Drafter revises
6. **Returns formatted exercise** via MCP
7. **Claude presents** to user

## Demo Video Tips

Show this flow:
1. Open Claude Desktop
2. Show the tool is connected (🔌 icon)
3. Type: "Use Cerina Foundry to create an exercise for public speaking anxiety"
4. Show Claude calling the tool
5. Show the final exercise appearing
6. Compare with React dashboard version

This demonstrates the same workflow accessible via different interfaces!
