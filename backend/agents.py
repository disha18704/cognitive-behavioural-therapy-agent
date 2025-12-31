import os
import asyncio
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from backend.state import AgentState
from backend.models import ExerciseDraft, Critique, SupervisorDecision, AgentNote, DraftVersion, ReviewMetadata
from backend.prompts import DRAFTER_PROMPT, SAFETY_PROMPT, CLINICAL_PROMPT, SUPERVISOR_PROMPT
from backend.vector_store import search_drafts, initialize_vector_store, extract_topics
from pydantic import BaseModel

def get_llm():
    return ChatOpenAI(model="gpt-4o", temperature=0.2)

class IntentClassification(BaseModel):
    intent: str
    reasoning: str

class MemoryIntent(BaseModel):
    """Intent classification for memory agent"""
    intent: str  # "retrieve", "create_new", "modify_existing", "chat"
    reasoning: str
    query: Optional[str] = None  # Extracted query for retrieval searches

async def memory_agent_node(state: AgentState):
    """
    Memory agent that handles intent classification and semantic draft retrieval.
    Determines if user wants to retrieve an existing draft, create a new one, modify existing, or chat.
    """
    messages = state["messages"]
    last_message = messages[-1].content if messages else ""
    
    # Intent classification prompt
    classification_prompt = """You are a memory and retrieval agent. Analyze the user's message to determine their intent.

Classify the intent as one of:
1. "retrieve" - User wants to retrieve/view an existing draft they created earlier
   Examples: "can I have the plan I made for anxiety", "show me my depression exercise", 
   "what was that plan about stress", "give me the anxiety plan"
   
2. "create_new" - User wants to create a brand new draft/exercise
   Examples: "make a plan for anxiety", "create an exercise for depression", 
   "I need help with stress", "make another anxiety plan"
   
3. "modify_existing" - User wants to modify/edit an existing draft
   Examples: "update my anxiety plan", "change the depression exercise", 
   "edit the plan I made earlier"
   
4. "chat" - General conversation, greetings, questions about capabilities
   Examples: "hello", "what can you do", "how are you"

For "retrieve" intent, extract the key query terms (e.g., "anxiety", "depression", "stress plan").
This will be used for semantic search.

User message: "{message}"

Think carefully about the user's intent."""
    
    llm = get_llm()
    structured_llm = llm.with_structured_output(MemoryIntent)
    
    result = structured_llm.invoke([
        SystemMessage(content=classification_prompt.format(message=last_message))
    ])
    
    memory_result = {
        "intent": result.intent,
        "reasoning": result.reasoning,
        "query": result.query or last_message,
        "found": False,
        "draft": None,
        "confidence": 0.0,
        "original_message": None
    }
    
    # If creating new plan, clear old draft from state
    if result.intent == "create_new" and state.get("current_draft"):
        return {
            "memory_result": memory_result,
            "current_draft": None,
            "draft_history": [],
            "critiques": [],
            "scratchpad": [],
            "metadata": ReviewMetadata(),  # Reset metadata
            "last_reviewer": None,
            "next_worker": "intent_router"
        }
    
    # Only perform semantic search if intent is explicitly "retrieve"
    # Never search for "create_new" - always create fresh
    if result.intent == "retrieve":
        try:
            # Use the extracted query or fall back to full message
            search_query = result.query if result.query else last_message
            
            # Extract topics from the full message as well (in case LLM didn't extract properly)
            # This ensures we catch topics even if LLM extraction missed them
            query_topics_from_message = extract_topics(last_message)
            query_topics_from_query = extract_topics(search_query)
            query_topics = query_topics_from_message.union(query_topics_from_query)
            
            # If no topics found, try extracting from the full message more aggressively
            if not query_topics:
                # Fallback: check if message contains common mental health terms
                message_lower = last_message.lower()
                if 'anxiety' in message_lower:
                    query_topics.add('anxiety')
                if 'depression' in message_lower:
                    query_topics.add('depression')
                if 'stress' in message_lower:
                    query_topics.add('stress')
            
            matches = await search_drafts(search_query, limit=5, threshold=0.75)  # Get more matches for better filtering
            
            if matches:
                # Find the best match that has topic overlap - STRICT validation
                best_match = None
                for match in matches:
                    # Use original_message as primary source for topic validation
                    # This ensures we match based on user's original request, not edited content
                    draft_title = match.get('title', '')
                    original_message = match.get('original_message', '')
                    # Prioritize original_message - it's the source of truth for what topic was requested
                    draft_text = f"{original_message} {draft_title}"
                    draft_topics = extract_topics(draft_text)
                    
                    # STRICT: If query has topics, MUST have topic match
                    if query_topics:
                        topic_overlap = query_topics.intersection(draft_topics)
                        if topic_overlap:
                            # Topics match - this is a valid match
                            print(f"Memory agent: Found match with topic overlap {topic_overlap}. Query topics: {query_topics}, Draft topics: {draft_topics}, Draft title: {draft_title}")
                            best_match = match
                            break
                        else:
                            # Topics don't match - skip this match
                            print(f"Memory agent: Skipping match - topic mismatch. Query topics: {query_topics}, Draft topics: {draft_topics}, Draft title: {draft_title}")
                    else:
                        # No topics in query - be very cautious
                        # Only return if similarity is very high (>0.85) and we can't determine topic
                        if match.get('similarity', 0) > 0.85:
                            print(f"Memory agent: No topics in query, using high similarity match (>0.85)")
                            best_match = match
                            break
                        # Otherwise skip - too risky to return wrong draft
                
                if best_match:
                    # Topics match - proceed with returning the draft
                    # Convert draft dict back to ExerciseDraft object
                    from backend.models import ExerciseDraft
                    draft_obj = ExerciseDraft(**best_match["draft"])
                    
                    memory_result.update({
                        "found": True,
                        "draft": best_match["draft"],  # Keep dict for JSON serialization
                        "confidence": best_match["similarity"],
                        "original_message": best_match["original_message"],
                        "metadata": best_match.get("metadata", {})
                    })
                    
                    # Also set current_draft so frontend can access it
                    return {
                        "memory_result": memory_result,
                        "current_draft": draft_obj,
                        "next_worker": "end",
                        "metadata": ReviewMetadata(**best_match.get("metadata", {})) if best_match.get("metadata") else ReviewMetadata()
                    }
                else:
                    # No match with topic overlap
                    memory_result["found"] = False
                    memory_result["reasoning"] += " (No draft found with matching topics)"
        except Exception as e:
            # If search fails, log but continue
            print(f"Error in semantic search: {e}")
            memory_result["reasoning"] += f" (Search error: {str(e)})"
    
    # If intent is "chat", route directly to chat
    if result.intent == "chat":
        return {
            "memory_result": memory_result,
            "next_worker": "chat",
            "metadata": state.get("metadata", ReviewMetadata())
        }
    
    # For other intents, continue to intent_router (which will handle CBT exercise creation)
    return {
        "memory_result": memory_result,
        "next_worker": "intent_router" if result.intent != "chat" else "chat",
        "metadata": state.get("metadata", ReviewMetadata())
    }


def intent_router_node(state: AgentState):
    messages = state["messages"]
    last_message = messages[-1].content if messages else ""
    
    classification_prompt = """You are an intent classifier. Analyze the user's message carefully.

Return "chat" if ONLY IF the user is:
- Greeting (hi, hello, hey, what's up)
- Asking about your capabilities (what can you do, how do you work)
- Making small talk (how are you, thanks, bye)
- Asking general questions NOT related to mental health

Return "cbt_exercise" if the user mentions:
- Mental health issues (anxiety, depression, stress, insomnia, OCD, etc.)
- Wants help with emotions or thoughts
- Requests a CBT exercise, therapy tool, or mental health support
- Describes any psychological challenge or symptom

Examples:
"hey" → chat
"hello" → chat
"what can you do?" → chat
"how are you?" → chat
"I have insomnia" → cbt_exercise
"I'm feeling anxious" → cbt_exercise
"create a CBT exercise" → cbt_exercise
"help with negative thoughts" → cbt_exercise

User message: "{message}"

Think carefully. What is the intent?"""

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
    
    chat_prompt = """You are Clarity CBT, a friendly AI assistant specializing in CBT exercises.

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
    

    version_info = f"Reviewing draft v{len(draft_history)}" if draft_history else "Reviewing initial draft"
    messages = [
        SystemMessage(content=SAFETY_PROMPT),
        HumanMessage(content=f"{version_info}\n\nDraft to review:\n{current_draft.model_dump_json()}")
    ]
    

    structured_llm = get_llm().with_structured_output(Critique)
    response = structured_llm.invoke(messages)
    response.author = "Safety Guardian"
    

    safety_score = 1.0 if response.approved else 0.5
    

    priority = "info" if response.approved else "critical"
    notes = [
        AgentNote(
            author="Safety Guardian",
            target="Drafter",
            content=f"Safety review {'passed' if response.approved else 'failed'}: {response.content[:200]}",
            priority=priority
        )
    ]
    

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
    

    structured_llm = get_llm().with_structured_output(Critique)
    response = structured_llm.invoke(messages)
    response.author = "Clinical Critic"
    

    empathy_score = 1.0 if response.approved else 0.6
    clarity_score = 1.0 if response.approved else 0.6

    priority = "info" if response.approved else "warning"
    notes = [
        AgentNote(
            author="Clinical Critic",
            target="Drafter",
            content=f"Clinical review {'passed' if response.approved else 'needs improvement'}: {response.content[:200]}",
            priority=priority
        )
    ]
    

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
    

    current_draft = state.get("current_draft")
    draft_history = state.get("draft_history", [])
    critiques = state.get("critiques", [])
    metadata = state.get("metadata")
    last_reviewer = state.get("last_reviewer")
    

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
        recent_notes = scratchpad[-3:]  
        for note in recent_notes:
            context += f"\n- [{note.author}]: {note.content[:100]}"
    
    messages.append(HumanMessage(content=context))
    
    structured_llm = get_llm().with_structured_output(SupervisorDecision)
    response = structured_llm.invoke(messages)
    
    return {"next_worker": response.next_node}
