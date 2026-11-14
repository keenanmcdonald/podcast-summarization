from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agent.models.verification_state import VerificationState
from src.agent.nodes.assess_claim import assess_claim
from src.agent.nodes.search_evidence import search_evidence


def build_claim_verification_graph() -> CompiledStateGraph:
    graph = StateGraph(VerificationState)
    graph.add_node("assess_claim", assess_claim)
    graph.add_node("search_evidence", search_evidence)
    graph.add_edge(START, "assess_claim")
    graph.add_conditional_edges(
        "assess_claim",
        route_verification,
        {"search": "search_evidence", "finish": END},
    )
    graph.add_edge("search_evidence", "assess_claim")
    return graph.compile(name="verify_claim")


def route_verification(state: VerificationState) -> Literal["search", "finish"]:
    if state.progress.next_step is None:
        raise ValueError("Claim assessment must select the next step")
    return state.progress.next_step
