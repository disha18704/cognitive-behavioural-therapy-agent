"""
MCP Server for Clarity CBT
Exposes the multi-agent CBT workflow as an MCP tool for Claude Desktop
"""
import asyncio
import os
from typing import Any
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from dotenv import load_dotenv
from backend.graph import get_graph
from backend.models import ReviewMetadata
from backend.formatter import format_exercise_for_presentation
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import HumanMessage

load_dotenv()

# Initialize MCP server
server = Server("clarity-cbt")

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """
    List available tools for MCP clients.
    Returns the create_cbt_exercise tool.
    """
    return [
        Tool(
            name="create_cbt_exercise",
            description="""Create a clinically-validated, expert-reviewed CBT (Cognitive Behavioral Therapy) exercise for any mental health challenge.

The exercise goes through multiple AI expert reviews:
- Safety Guardian: Checks for medical safety and harm prevention
- Clinical Critic: Evaluates empathy, tone, and clinical soundness
- Drafter: Creates and refines the content based on feedback

Use this tool when you need:
- Structured CBT worksheets
- Exposure hierarchies
- Thought records
- Behavioral activation plans
- Anxiety management exercises

Examples:
- "Create a CBT exercise for social anxiety"
- "I need help with insomnia - create a sleep hygiene protocol"
- "Build an exposure hierarchy for public speaking fear"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "request": {
                        "type": "string",
                        "description": "Description of the mental health challenge or CBT need (e.g., 'social anxiety', 'insomnia', 'work stress', 'perfectionism')"
                    }
                },
                "required": ["request"]
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent | EmbeddedResource]:
    """
    Execute the requested tool.
    Runs the multi-agent workflow and returns the CBT exercise.
    """
    if name != "create_cbt_exercise":
        raise ValueError(f"Unknown tool: {name}")
    
    if not os.getenv("OPENAI_API_KEY"):
        return [TextContent(
            type="text",
            text="❌ Error: OPENAI_API_KEY not configured. Please set it in your .env file."
        )]
    
    request = arguments.get("request", "")
    if not request:
        return [TextContent(
            type="text",
            text="❌ Error: Please provide a request describing your CBT needs."
        )]
    
    try:
        # Initialize the graph with checkpointer
        graph = get_graph()
        checkpointer = InMemorySaver()
        app = graph.compile(checkpointer=checkpointer)
        
        # Create thread for this request
        thread_id = f"mcp-{hash(request)}"
        config = {"configurable": {"thread_id": thread_id}}
        
        # Initialize state
        initial_input = {
            "messages": [HumanMessage(content=f"Create a CBT exercise for: {request}")],
            "current_draft": None,
            "draft_history": [],
            "critiques": [],
            "scratchpad": [],
            "metadata": ReviewMetadata(),
            "last_reviewer": None
        }
        
        # Run the multi-agent workflow
        result = await app.ainvoke(initial_input, config=config)
        
        # Get the final draft
        draft = result.get("current_draft")
        metadata = result.get("metadata")
        
        if not draft:
            return [TextContent(
                type="text",
                text="❌ Error: Failed to generate CBT exercise. Please try again with a different request."
            )]
        
        # Format the exercise for presentation
        formatted_exercise = format_exercise_for_presentation(draft, metadata)
        
        # Add metadata summary at the top
        summary = f"""
🧠 **Clarity CBT**
Multi-Agent CBT Exercise Generation System

**Your Request:** {request}

**Quality Validation:**
✅ Safety Review: {"Passed" if metadata and metadata.safety_score and metadata.safety_score >= 0.9 else "N/A"}
✅ Clinical Review: {"Passed" if metadata and metadata.empathy_score and metadata.empathy_score >= 0.9 else "N/A"}
✅ Total Revisions: {metadata.total_revisions if metadata else 0}

---

{formatted_exercise}

---

💡 **Note**: This exercise was created by our multi-agent system with Safety Guardian and Clinical Critic reviews. For personalized care, consult a mental health professional.
"""
        
        return [TextContent(
            type="text",
            text=summary
        )]
        
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"❌ Error generating CBT exercise: {str(e)}\n\nPlease try again or check the server logs for details."
        )]


async def main():
    """Run the MCP server"""
    # Run the server using stdin/stdout streams
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="clarity-cbt",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
