import uvicorn
import json
import os
import aiosqlite
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from backend.graph import get_graph
from backend.models import ReviewMetadata
from backend.vector_store import initialize_vector_store, index_draft
from langchain_core.messages import HumanMessage
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncSqliteSaver.from_conn_string("backend/checkpoints.db") as checkpointer:
        app.state.graph = get_graph().compile(checkpointer=checkpointer)
        # Initialize vector store
        await initialize_vector_store()
        yield


app = FastAPI(title="Clarity CBT API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RequestData(BaseModel):
    message: str
    thread_id: str

class ApprovalData(BaseModel):
    thread_id: str
    edited_content: Optional[str] = None

class SaveDraftData(BaseModel):
    thread_id: str
    draft: dict  # ExerciseDraft as dict
    original_message: Optional[str] = None  # Original user message for retrieval



@app.post("/stream")
async def stream_workflow(data: RequestData):
    """Stream the workflow execution with real-time updates"""
    graph = app.state.graph
    config = {"configurable": {"thread_id": data.thread_id}}
    
    # Check if this is a new conversation
    current_state = await graph.aget_state(config)
    
    # Memory agent will handle intent classification and retrieval
    # Just pass the message to the workflow
    if not current_state.values:
        # Initialize new state
        inputs = {
            "messages": [HumanMessage(content=data.message)],
            "current_draft": None,
            "draft_history": [],
            "critiques": [],
            "scratchpad": [],
            "metadata": ReviewMetadata(),
            "last_reviewer": None,
            "memory_result": None
        }
    else:
        # Continue with existing state - memory agent will handle routing
        inputs = {"messages": [HumanMessage(content=data.message)]}
    
    def serialize_message(msg):
        """Serialize a LangChain message to a dict"""
        try:
            if hasattr(msg, 'model_dump'):
                return msg.model_dump()
            elif hasattr(msg, 'dict'):
                return msg.dict()
            else:
                return {
                    "type": getattr(msg, 'type', 'unknown'),
                    "content": getattr(msg, 'content', str(msg))
                }
        except Exception:
            return {"type": "unknown", "content": str(msg)}
    
    def serialize_state_value(value):
        """Recursively serialize state values"""
        if isinstance(value, list):
            return [serialize_state_value(item) for item in value]
        elif hasattr(value, 'model_dump'):
            return value.model_dump()
        elif hasattr(value, 'dict'):
            return value.dict()
        elif isinstance(value, dict):
            return {k: serialize_state_value(v) for k, v in value.items()}
        else:
            return value
    
    async def generate():
        """Generator for streaming events"""
        try:
            async for event in graph.astream(inputs, config=config):
                # Serialize the event properly
                serialized_event = {}
                for node_name, node_data in event.items():
                    if isinstance(node_data, dict):
                        serialized_event[node_name] = {}
                        for key, value in node_data.items():
                            if key == 'messages' and isinstance(value, list):
                                # Special handling for messages
                                serialized_event[node_name][key] = [serialize_message(msg) for msg in value]
                            else:
                                serialized_event[node_name][key] = serialize_state_value(value)
                    else:
                        serialized_event[node_name] = serialize_state_value(node_data)
                
                # Send each event as JSON
                yield f"data: {json.dumps(serialized_event)}\n\n"
            
            # Send completion signal
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/state/{thread_id}")
async def get_state(thread_id: str):
    """Get current state for a thread"""
    graph = app.state.graph
    config = {"configurable": {"thread_id": thread_id}}
    state = await graph.aget_state(config)
    
    if not state.values:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    # Convert messages to JSON-serializable format and extract original user message
    messages = state.values.get("messages", [])
    serialized_messages = []
    original_user_message = None
    
    # Better extraction of original user message
    for msg in messages:
        # Check if it's a HumanMessage object
        if hasattr(msg, 'type') and msg.type == 'human':
            original_user_message = msg.content if hasattr(msg, 'content') else str(msg)
        # Check if it's a HumanMessage by class name
        elif hasattr(msg, '__class__') and 'HumanMessage' in str(type(msg)):
            original_user_message = msg.content if hasattr(msg, 'content') else str(msg)
        # Check if it's already a dict
        elif isinstance(msg, dict) and msg.get('type') in ['human', 'HumanMessage', 'user']:
            original_user_message = msg.get('content', '')
        
        if original_user_message:
            break  # Found the first user message
    
    # Auto-index completed drafts
    current_draft = state.values.get("current_draft")
    if current_draft and original_user_message:
        # Check if draft is completed (routed to human_review or has been through all reviews)
        last_reviewer = state.values.get("last_reviewer")
        next_worker = state.values.get("next_worker")
        
        # Save if draft has been reviewed (either approved or reached human review)
        if last_reviewer in ['safety_guardian', 'clinical_critic'] or next_worker == 'human_review':
            try:
                metadata = state.values.get("metadata")
                await index_draft(current_draft, original_user_message, metadata)
            except Exception as e:
                # Log error but don't fail the request
                print(f"Error auto-indexing draft: {e}")
    
    # Continue serializing messages
    for msg in messages:
        try:
            if hasattr(msg, 'model_dump'):
                msg_dict = msg.model_dump()
            elif hasattr(msg, 'dict'):
                msg_dict = msg.dict()
            else:
                # Fallback: extract content and type
                msg_dict = {
                    "type": getattr(msg, 'type', 'unknown'),
                    "content": getattr(msg, 'content', str(msg))
                }
            # Ensure content is a string
            if isinstance(msg_dict.get('content'), list):
                # Handle case where content might be a list
                msg_dict['content'] = ' '.join(str(c) for c in msg_dict['content'])
            elif not isinstance(msg_dict.get('content'), str):
                msg_dict['content'] = str(msg_dict.get('content', ''))
            
            serialized_messages.append(msg_dict)
        except Exception as e:
            # If serialization fails, create a simple dict
            serialized_messages.append({
                "type": "unknown",
                "content": str(msg) if hasattr(msg, '__str__') else "Unable to serialize message"
            })
    
    # Convert state to JSON-serializable format
    return {
        "current_draft": state.values.get("current_draft"),
        "draft_history": state.values.get("draft_history", []),
        "critiques": state.values.get("critiques", []),
        "scratchpad": state.values.get("scratchpad", []),
        "metadata": state.values.get("metadata"),
        "last_reviewer": state.values.get("last_reviewer"),
        "next_worker": state.values.get("next_worker"),
        "memory_result": state.values.get("memory_result"),
        "messages": serialized_messages
    }


@app.post("/approve")
async def approve_draft(data: ApprovalData):
    """Approve and finalize a draft, optionally with edits"""
    graph = app.state.graph
    config = {"configurable": {"thread_id": data.thread_id}}
    
    # Get current state
    current_state = await graph.aget_state(config)
    if not current_state.values:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    # If edited content provided, update the draft
    if data.edited_content:
        # Update the draft with edited content
        draft = current_state.values.get("current_draft")
        if draft:
            draft.content = data.edited_content
            # Resume with updated draft
            result = await graph.ainvoke(
                {"current_draft": draft},
                config=config
            )
        else:
            raise HTTPException(status_code=400, detail="No draft to edit")
    else:
        # Just approve - return final state
        result = current_state.values
    
    return {
        "status": "approved",
        "draft": result.get("current_draft"),
        "metadata": result.get("metadata")
    }


def normalize_message(message: str) -> str:
    """Normalize user message for consistent key matching"""
    import re
    normalized = message.lower().strip()
    normalized = re.sub(r'\s+', ' ', normalized)  # Replace multiple spaces with single space
    normalized = re.sub(r'[^\w\s]', '', normalized)  # Remove punctuation
    return normalized[:200]

@app.post("/save-draft")
async def save_draft(data: SaveDraftData):
    """Save an edited draft to the database"""
    graph = app.state.graph
    config = {"configurable": {"thread_id": data.thread_id}}
    
    # Get current state
    current_state = await graph.aget_state(config)
    if not current_state.values:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    # Update the draft with edited content
    from backend.models import ExerciseDraft
    edited_draft = ExerciseDraft(**data.draft)
    
    # Use aupdate_state (async version) to update just the draft without running workflow
    # This creates a new checkpoint with the edited draft
    await graph.aupdate_state(
        config,
        {"current_draft": edited_draft}
    )
    
    # Re-index draft in vector store when edited
    if data.original_message:
        try:
            metadata = current_state.values.get("metadata")
            await index_draft(edited_draft, data.original_message, metadata)
        except Exception as e:
            print(f"Error re-indexing edited draft: {e}")
    
    return {
        "status": "saved",
        "draft": edited_draft.model_dump()
    }


@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "message": "Clarity CBT API",
        "endpoints": {
            "POST /stream": "Stream workflow execution",
            "GET /state/{thread_id}": "Get current state",
            "POST /approve": "Approve draft with optional edits",
            "POST /save-draft": "Save edited draft"
        }
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
