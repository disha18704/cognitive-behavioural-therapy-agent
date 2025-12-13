from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from backend.state import AgentState
from backend.agents import drafter_node, safety_node, clinical_node, supervisor_node, intent_router_node, chat_response_node


workflow = StateGraph(AgentState)


workflow.add_node("intent_router", intent_router_node)
workflow.add_node("chat", chat_response_node)
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("drafter", drafter_node)
workflow.add_node("safety_guardian", safety_node)
workflow.add_node("clinical_critic", clinical_node)

def route_supervisor(state: AgentState):
    next_node = state["next_worker"]
    if next_node == "end":
        return END
    return next_node


workflow.add_edge("drafter", "supervisor")
workflow.add_edge("safety_guardian", "supervisor")
workflow.add_edge("clinical_critic", "supervisor")

workflow.add_conditional_edges(
    "supervisor",
    route_supervisor,
    {
        "drafter": "drafter",
        "safety_guardian": "safety_guardian",
        "clinical_critic": "clinical_critic",
        "human_review": END, 
        "end": END
    }
)


def route_intent(state: AgentState):
    next_node = state["next_worker"]
    if next_node == "chat":
        return "chat"
    return "supervisor"

workflow.add_conditional_edges(
    "intent_router",
    route_intent,
    {
        "chat": "chat",
        "supervisor": "supervisor"
    }
)

workflow.add_edge("chat", END)

workflow.set_entry_point("intent_router")


def get_graph():
    return workflow
