import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from backend.state import AgentState
from backend.models import ExerciseDraft, Critique, SupervisorDecision, AgentNote, DraftVersion, ReviewMetadata
from backend.prompts import DRAFTER_PROMPT, SAFETY_PROMPT, CLINICAL_PROMPT, SUPERVISOR_PROMPT
from pydantic import BaseModel

def get_llm():
    return ChatOpenAI(model="gpt-4o", temperature=0.2)

class IntentClassification(BaseModel):
    intent: str
    reasoning: str

def intent_router_node(state: AgentState):
    messages = state["messages"]
    last_message = messages[-1].content if messages else ""
    
    classification_prompt = """You are an intent classifier. Determine if the user wants:
- "cbt_exercise" - CBT exercise, therapy help, mental health support, or psychological assistance
- "chat" - Normal chat, greetings, general questions, or small talk

Examples:
"hey" → chat
"hello" → chat  
"I need help with anxiety" → cbt_exercise
"create a CBT exercise" → cbt_exercise

User message: "{message}"

Classify the intent."""

    llm = get_llm()
    structured_llm = llm.with_structured_output(IntentClassification)
    
    result = structured_llm.invoke([
        SystemMessage(content=classification_prompt.format(message=last_message))
    ])
    
    return {
        "next_worker": result.intent,
        "metadata": state.get("metadata", ReviewMetadata())
    }

def chat_response_node(state: AgentState):
    messages = state["messages"]
    
    chat_prompt = """You are Cerina Foundry, a friendly AI assistant specializing in CBT exercises.

For normal conversation, respond helpfully and let users know you can create personalized CBT exercises for mental health challenges like anxiety, depression, and procrastination.

Keep responses concise and friendly."""

    llm = get_llm()
    response = llm.invoke([SystemMessage(content=chat_prompt)] + messages)
    
    return {
        "messages": [response],
        "next_worker": "end",
        "metadata": state.get("metadata", ReviewMetadata())
    }

def drafter_node(state: AgentState):
    messages = [SystemMessage(content=DRAFTER_PROMPT)] + state["messages"]
    
    scratchpad = state.get("scratchpad", [])
    safety_notes = [n for n in scratchpad if "Safety" in n.author]
    clinical_notes = [n for n in scratchpad if "Clinical" in n.author]
    
    draft_history = state.get("draft_history", [])
    version_num = len(draft_history) + 1
    
    revision_context = ""
    if state.get("critiques"):
        recent_critiques = state["critiques"][-2:]
        revision_context += "\n\nRecent Critiques to Address:\n"
        for c in recent_critiques:
            revision_context += f"- [{c.author}] {'✓ Approved' if c.approved else '✗ Rejected'}: {c.content}\n"
    
    if safety_notes or clinical_notes:
        revision_context += "\n\nScratchpad Notes from Reviewers:\n"
        for note in (safety_notes + clinical_notes)[-3:]:
            revision_context += f"- [{note.author}] ({note.priority}): {note.content}\n"
    
    if draft_history:
        last_version = draft_history[-1]
        revision_context += f"\n\nPrevious Version (v{last_version.version_number}): {last_version.notes}\n"
    
    if revision_context:
        messages.append(HumanMessage(content=f"Please revise the draft based on this feedback:{revision_context}"))
    
    # Generate draft
    structured_llm = get_llm().with_structured_output(ExerciseDraft)
    response = structured_llm.invoke(messages)
    
    # Create version entry
    changes_made = "Initial draft" if not draft_history else f"Revised based on {len(state.get('critiques', []))} critiques"
    new_version = DraftVersion(
        version_number=version_num,
        draft=response,
        created_by="Drafter",
        notes=changes_made
    )
    
    # Leave scratchpad note
    note = AgentNote(
        author="Drafter",
        content=f"Created v{version_num}: {response.title}. {changes_made}",
        priority="info"
    )
    
    # Update metadata
    metadata = state.get("metadata") or ReviewMetadata()
    updated_metadata = ReviewMetadata(
        safety_score=metadata.safety_score,
        empathy_score=metadata.empathy_score,
        clarity_score=metadata.clarity_score,
        iteration_count=metadata.iteration_count + 1,
        total_revisions=metadata.total_revisions + 1
    )
    
    return {
        "current_draft": response,
        "draft_history": [new_version],
        "scratchpad": [note],
        "metadata": updated_metadata,
        "last_reviewer": "drafter",
        "messages": [AIMessage(content=f"Drafted/Revised: {response.title} (v{version_num})")]
    }

def safety_node(state: AgentState):
    current_draft = state.get("current_draft")
    draft_history = state.get("draft_history", [])
    
    # Build review context
    version_info = f"Reviewing draft v{len(draft_history)}" if draft_history else "Reviewing initial draft"
    messages = [
        SystemMessage(content=SAFETY_PROMPT),
        HumanMessage(content=f"{version_info}\n\nDraft to review:\n{current_draft.model_dump_json()}")
    ]
    
    # Generate critique
    structured_llm = get_llm().with_structured_output(Critique)
    response = structured_llm.invoke(messages)
    response.author = "Safety Guardian"
    
    # Calculate safety score (simple heuristic)
    safety_score = 1.0 if response.approved else 0.5
    
    # Create detailed scratchpad notes
    priority = "info" if response.approved else "critical"
    notes = [
        AgentNote(
            author="Safety Guardian",
            target="Drafter",
            content=f"Safety review {'passed' if response.approved else 'failed'}: {response.content[:200]}",
            priority=priority
        )
    ]
    
    # Update metadata
    metadata = state.get("metadata") or ReviewMetadata()
    updated_metadata = ReviewMetadata(
        safety_score=safety_score,
        empathy_score=metadata.empathy_score,
        clarity_score=metadata.clarity_score,
        iteration_count=metadata.iteration_count,
        total_revisions=metadata.total_revisions
    )
    
    return {
        "critiques": [response],
        "scratchpad": notes,
        "metadata": updated_metadata,
        "last_reviewer": "safety_guardian",
        "messages": [AIMessage(content=f"Safety Review: {'Approved' if response.approved else 'Rejected'} (Score: {safety_score})")]
    }

def clinical_node(state: AgentState):
    current_draft = state.get("current_draft")
    draft_history = state.get("draft_history", [])
    
    # Build review context
    version_info = f"Reviewing draft v{len(draft_history)}" if draft_history else "Reviewing initial draft"
    messages = [
        SystemMessage(content=CLINICAL_PROMPT),
        HumanMessage(content=f"{version_info}\n\nDraft to review:\n{current_draft.model_dump_json()}")
    ]
    
    # Generate critique
    structured_llm = get_llm().with_structured_output(Critique)
    response = structured_llm.invoke(messages)
    response.author = "Clinical Critic"
    
    # Calculate empathy and clarity scores (simple heuristic)
    empathy_score = 1.0 if response.approved else 0.6
    clarity_score = 1.0 if response.approved else 0.6
    
    # Create detailed scratchpad notes
    priority = "info" if response.approved else "warning"
    notes = [
        AgentNote(
            author="Clinical Critic",
            target="Drafter",
            content=f"Clinical review {'passed' if response.approved else 'needs improvement'}: {response.content[:200]}",
            priority=priority
        )
    ]
    
    # Update metadata
    metadata = state.get("metadata") or ReviewMetadata()
    updated_metadata = ReviewMetadata(
        safety_score=metadata.safety_score,
        empathy_score=empathy_score,
        clarity_score=clarity_score,
        iteration_count=metadata.iteration_count,
        total_revisions=metadata.total_revisions
    )
    
    return {
        "critiques": [response],
        "scratchpad": notes,
        "metadata": updated_metadata,
        "last_reviewer": "clinical_critic",
        "messages": [AIMessage(content=f"Clinical Review: {'Approved' if response.approved else 'Rejected'} (Empathy: {empathy_score}, Clarity: {clarity_score})")]
    }

def supervisor_node(state: AgentState):
    messages = [SystemMessage(content=SUPERVISOR_PROMPT)] + state["messages"]
    
    # Build comprehensive state context
    current_draft = state.get("current_draft")
    draft_history = state.get("draft_history", [])
    critiques = state.get("critiques", [])
    metadata = state.get("metadata")
    last_reviewer = state.get("last_reviewer")
    
    # Determine who rejected (if anyone)
    last_rejection_source = None
    if critiques:
        last_critique = critiques[-1]
        if not last_critique.approved:
            last_rejection_source = last_critique.author
    
    context = f"""
Current State:
- Draft Status: {"No draft" if not current_draft else f"Draft v{len(draft_history)} exists"}
- Last Reviewer: {last_reviewer or "None"}
- Total Revisions: {metadata.total_revisions if metadata else 0}
- Last Critique: {critiques[-1].author if critiques else "None"} → {"Approved" if critiques and critiques[-1].approved else "Rejected"}
- Last Rejection Source: {last_rejection_source or "None"}

Recent Scratchpad Notes:
"""
    scratchpad = state.get("scratchpad", [])
    if scratchpad:
        recent_notes = scratchpad[-3:]  # Last 3 notes
        for note in recent_notes:
            context += f"\n- [{note.author}]: {note.content[:100]}"
    
    messages.append(HumanMessage(content=context))
    
    structured_llm = get_llm().with_structured_output(SupervisorDecision)
    response = structured_llm.invoke(messages)
    
    return {"next_worker": response.next_node}
