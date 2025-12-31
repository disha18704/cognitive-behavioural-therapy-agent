# Clarity CBT

**An intelligent multi-agent system that autonomously designs, critiques, and refines CBT (Cognitive Behavioral Therapy) exercises.**

Clarity CBT is a team of AI experts working together:
- **Drafter** - Creates and revises CBT exercises
- **Safety Guardian** - Reviews for medical safety
- **Clinical Critic** - Validates empathy and clinical quality  
- **Supervisor** - Orchestrates the collaboration
- **Intent Router** - Handles both casual chat and therapy requests

## Key Features

- **Smart Chat Routing** - Casual greetings → friendly chat, therapy requests → CBT workflow
- **Multi-Agent Collaboration** - Agents debate, revise, and re-review
- **Rich State Management** - Scratchpad notes, version history, quality scores
- **SQLite Persistence** - Crash recovery with checkpointing
- **Clean Gemini-Style UI** - Minimal, modern React interface
- **Real-time Streaming** - Watch agents collaborate live

## Quick Start

### Prerequisites
- Python 3.14
- Node.js 20+
- OpenAI API Key

### 1. Install Dependencies

```bash
# Backend
pip install -r requirements.txt

# Frontend
cd frontend && npm install
```

### 2. Setup Environment

Create `.env` in project root:
```bash
OPENAI_API_KEY=your-openai-api-key-here
```

### 3. Run the Application

**Terminal 1 - Backend:**
```bash
python3 -m uvicorn backend.server:app --reload
```

**Terminal 2 - Frontend:**
```bash
cd frontend && npm run dev
```

**Browser:** http://localhost:5173

## Try It Out

**Casual Chat:**
- "hey"
- "how are you?"
- "what can you do?"

**CBT Exercises:**
- "I'm feeling anxious"
- "Create a CBT exercise for insomnia"
- "Help with negative thoughts"

## Project Structure

```
cognitive-behavioural-therapy-agent/
├── backend/
│   ├── agents.py      # Intent router & agent implementations
│   ├── graph.py       # LangGraph workflow with routing
│   ├── state.py       # Shared state structure
│   ├── models.py      # Pydantic data models
│   ├── prompts.py     # Expert system prompts
│   └── server.py      # FastAPI server with streaming
│
├── frontend/
│   └── src/
│       └── App.tsx    # React UI (Clean design)
│
├── mcp/
│   └── mcp_server.py  # MCP server for Claude Desktop
│
└── docs/
    ├── ARCHITECTURE.md    # System architecture
    └── README_MCP.md      # MCP setup guide
```

## How It Works

### 1. Intent Classification
```
User message → Intent Router
  ├─ "hey" → Chat Response
  └─ "I'm anxious" → CBT Workflow
```

### 2. CBT Agent Collaboration
```
Supervisor → Drafter (creates v1)
    ↓
Supervisor → Safety Guardian (reviews)
    ↓ [Rejects - needs disclaimer]
Supervisor → Drafter (creates v2)
    ↓
Supervisor → Safety Guardian (re-reviews)
    ↓ [Approves]
Supervisor → Clinical Critic (reviews)
    ↓ [Approves]
Result → User
```

## MCP Integration

Expose the workflow as a tool for Claude Desktop. See **[docs/README_MCP.md](docs/README_MCP.md)** for setup instructions.

**Quick setup:**
1. Install: `pip install mcp`
2. Configure Claude Desktop config
3. Use in Claude: "Use Clarity CBT to create a CBT exercise for social anxiety"

## API Endpoints

**FastAPI Docs:** http://127.0.0.1:8000/docs

- `POST /stream` - Stream agent collaboration
- `GET /state/{thread_id}` - Get conversation state
- `POST /approve` - Approve draft (Human-in-the-Loop)

## Documentation

- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Detailed system architecture
- **[docs/README_MCP.md](docs/README_MCP.md)** - MCP server setup for Claude Desktop

## Technical Highlights

- **Smart Intent Routing** - LLM-powered classification (chat vs therapy)  
- **Multi-Agent Collaboration** - Self-correcting review cycles  
- **Persistent State** - SQLite checkpointing for crash recovery  
- **Clean UI** - Minimalist design
- **Streaming SSE** - Real-time agent activity
- **MCP Integration** - Works with Claude Desktop

## Troubleshooting

### Backend won't start
```bash
# Kill existing process
lsof -ti:8000 | xargs kill -9

# Restart
python3 -m uvicorn backend.server:app --reload
```

### Frontend blank screen
```bash
# Kill and restart
cd frontend
npm run dev
```

### Missing API key
Check `.env` file has `OPENAI_API_KEY=...`

## Built With

- **LangGraph & LangChain** - Agent orchestration
- **OpenAI GPT-4o** - LLM inference
- **FastAPI** - REST API with streaming
- **React + TypeScript** - Clean UI
- **MCP** - Claude Desktop integration
- **SQLite** - State persistence

---

**Ready to see AI agents collaborate?** Start with the Quick Start guide above!
