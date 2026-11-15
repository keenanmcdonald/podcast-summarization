from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agent.models.fact_check_state import FactCheckState
from src.agent.models.state import GraphState
from src.agent.nodes.extract_claims import extract_claims
from src.agent.nodes.generate_show_notes import generate_show_notes
from src.agent.nodes.verify_claims import verify_claims


def build_graph() -> CompiledStateGraph:
    graph = StateGraph(GraphState)
    graph.add_node("generate_show_notes", generate_show_notes)
    graph.add_node("fact_checks", build_fact_check_graph())

    graph.add_edge(START, "generate_show_notes")
    graph.add_edge(START, "fact_checks")
    graph.add_edge("generate_show_notes", END)
    graph.add_edge("fact_checks", END)
    return graph.compile()


def build_fact_check_graph() -> CompiledStateGraph:
    graph = StateGraph(FactCheckState)
    graph.add_node("extract_claims", extract_claims)
    graph.add_node("verify_claims", verify_claims)
    graph.add_edge(START, "extract_claims")
    graph.add_edge("extract_claims", "verify_claims")
    graph.add_edge("verify_claims", END)
    return graph.compile()
