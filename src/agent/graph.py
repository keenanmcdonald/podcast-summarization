from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from src.agent.claim_graph import build_claim_verification_graph
from src.agent.models.verification_state import VerificationState
from src.agent.models.state import GraphState
from src.agent.nodes.extract_claims import extract_claims
from src.agent.nodes.finish_verification import finish_verification
from src.agent.nodes.generate_show_notes import generate_show_notes

MAX_CONCURRENT_CLAIMS = 4


def build_graph() -> CompiledStateGraph:
    graph = StateGraph(GraphState)
    graph.add_node("generate_show_notes", generate_show_notes)
    graph.add_node("extract_claims", extract_claims)
    graph.add_node("verify_claim", build_claim_verification_graph())
    graph.add_node("finish_verification", finish_verification, defer=True)

    graph.add_edge(START, "generate_show_notes")
    graph.add_edge(START, "extract_claims")
    graph.add_conditional_edges(
        "extract_claims", dispatch_claims, ["verify_claim", "finish_verification"]
    )
    graph.add_edge("verify_claim", "finish_verification")
    graph.add_edge("generate_show_notes", END)
    graph.add_edge("finish_verification", END)
    return graph.compile().with_config(max_concurrency=MAX_CONCURRENT_CLAIMS)


def dispatch_claims(state: GraphState) -> list[Send] | Literal["finish_verification"]:
    if not state.pending_checks:
        return "finish_verification"
    return [
        Send(
            "verify_claim",
            VerificationState(fact_check=check, transcript=state.transcript),
        )
        for check in state.pending_checks
    ]
