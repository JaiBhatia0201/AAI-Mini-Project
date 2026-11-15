"""NetworkX prerequisite DAG validation, cycle breaking, ordering, and root-cause lookup."""

import heapq
from typing import Any, Iterable
import networkx as nx


def build_nx_graph(
    topics: Iterable[Any],
    edges: Iterable[Any],
) -> nx.DiGraph:
    """Build a directed prerequisite graph (prerequisite -> dependent) from topics and edges."""
    graph = nx.DiGraph()
    valid_ids: set[str] = set()

    for topic in topics:
        tid = topic["id"] if isinstance(topic, dict) else topic.id
        valid_ids.add(tid)
        graph.add_node(
            tid,
            title=topic["title"] if isinstance(topic, dict) else topic.title,
            subject=topic["subject"] if isinstance(topic, dict) else topic.subject,
            order_index=int(
                topic.get("order_index", 0) if isinstance(topic, dict) else getattr(topic, "order_index", 0)
            ),
            exam_weightage=float(
                topic.get("exam_weightage", 1.0) if isinstance(topic, dict) else getattr(topic, "exam_weightage", 1.0)
            ),
        )

    for edge in edges:
        src = edge["prerequisite_topic_id"] if isinstance(edge, dict) else edge.prerequisite_topic_id
        dst = edge["dependent_topic_id"] if isinstance(edge, dict) else edge.dependent_topic_id
        conf = (
            edge.get("confidence_status", "verified_seed")
            if isinstance(edge, dict)
            else getattr(edge, "confidence_status", "verified_seed")
        )
        if src in valid_ids and dst in valid_ids and src != dst:
            graph.add_edge(src, dst, confidence_status=conf)

    return graph


def resolve_cycles(
    edges: list[tuple[str, str, str]],
    order_lookup: dict[str, int] | None = None,
) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    """Break directed cycles deterministically, dropping uncertain/backward edges first."""
    confidence_rank = {
        "needs_review": 0,
        "llm_extracted": 1,
        "user_confirmed": 2,
        "verified_seed": 3,
    }
    graph = nx.DiGraph()
    kept: list[tuple[str, str, str]] = []
    removed: list[tuple[str, str, str]] = []

    for src, dst, conf in edges:
        if src != dst and not graph.has_edge(src, dst):
            graph.add_edge(src, dst, confidence_status=conf)
            kept.append((src, dst, conf))

    while not nx.is_directed_acyclic_graph(graph):
        cycle = nx.find_cycle(graph, orientation="original")
        cycle_edges = [(u, v, graph[u][v].get("confidence_status", "llm_extracted")) for u, v, _ in cycle]

        def _drop_key(item: tuple[str, str, str]) -> tuple[int, int]:
            u, v, conf = item
            is_backward = 0 if (order_lookup and order_lookup.get(u, 0) > order_lookup.get(v, 0)) else 1
            return (confidence_rank.get(conf, 1), is_backward)

        to_drop = min(cycle_edges, key=_drop_key)
        graph.remove_edge(to_drop[0], to_drop[1])
        kept = [e for e in kept if not (e[0] == to_drop[0] and e[1] == to_drop[1])]
        removed.append(to_drop)

    return kept, removed


def topological_order(
    graph: nx.DiGraph,
    priority_weights: dict[str, float] | None = None,
) -> list[str]:
    """Return a valid prerequisite-respecting order biased by topic priority weights."""
    working = graph.copy()
    if not nx.is_directed_acyclic_graph(working):
        kept, _ = resolve_cycles(
            [(u, v, working[u][v].get("confidence_status", "llm_extracted")) for u, v in working.edges()]
        )
        dag = nx.DiGraph()
        dag.add_nodes_from(working.nodes(data=True))
        for u, v, conf in kept:
            dag.add_edge(u, v, confidence_status=conf)
        working = dag

    in_deg = {node: working.in_degree(node) for node in working.nodes()}
    weights = priority_weights or {}
    heap: list[tuple[float, int, str]] = []

    for node, deg in in_deg.items():
        if deg == 0:
            order_idx = int(working.nodes[node].get("order_index", 0))
            heapq.heappush(heap, (-float(weights.get(node, 1.0)), order_idx, node))

    result: list[str] = []
    while heap:
        _, _, curr = heapq.heappop(heap)
        result.append(curr)
        for nxt in working.successors(curr):
            in_deg[nxt] -= 1
            if in_deg[nxt] == 0:
                order_idx = int(working.nodes[nxt].get("order_index", 0))
                heapq.heappush(heap, (-float(weights.get(nxt, 1.0)), order_idx, nxt))

    return result


def find_root_cause_blockers(
    graph: nx.DiGraph,
    topic_id: str,
    mastery_map: dict[str, float],
    threshold: float = 65.0,
) -> list[str]:
    """Find weak upstream prerequisite ancestors ordered earliest-first."""
    if topic_id not in graph:
        return []
    ancestors = nx.ancestors(graph, topic_id)
    weak_ancestors = {anc for anc in ancestors if float(mastery_map.get(anc, 40.0)) < threshold}
    if not weak_ancestors:
        return []
    sub = graph.subgraph(weak_ancestors)
    return topological_order(sub)
