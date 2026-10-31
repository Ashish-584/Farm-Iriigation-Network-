"""Dijkstra's algorithm for the shortest path between two farm locations.

Dijkstra's algorithm finds the cheapest path between a source and a
destination in a graph whose edge weights are **non-negative**.  It works by
repeatedly extending the currently cheapest known path using a *priority queue*
(a min-heap).  With an adjacency list representation and a binary heap the
complexity is ``O((V + E) log V)``.

This implementation is standalone: it depends only on :class:`graph_model.Graph`
and the Python standard library.  No graph library is used to compute the path.

Loss model for the "minimum water-loss" objective
-------------------------------------------------
Water loss in a pipeline is a *percentage* of the water that flows through a
segment.  If segment ``i`` loses ``p_i`` percent of its water, the fraction that
survives is ``(1 - p_i / 100)``.  Over a whole route the physically surviving
fraction is the product of the survivors of every segment::

    surviving = (1 - p1/100) * (1 - p2/100) * ... * (1 - pk/100)

and the total physical loss percentage is ``(1 - surviving) * 100``.

Minimising the *sum* of the percentages ``p_1 + ... + p_k`` (the weight used by
Dijkstra) is a simple, fast proxy, but it is **not** equivalent to minimising
the true physical loss above, because the true loss is multiplicative and
nonlinear.  We therefore:

    * run Dijkstra on the summed-loss percentage (documented as a heuristic), and
    * report the *true* cumulative physical loss using the multiplicative model
      so the user sees the real number rather than the proxy.

Edge weights must be non-negative.  A water-loss percentage is in ``[0, 100]``
so it satisfies Dijkstra's precondition; we still guard against negative lengths
which Dijkstra cannot handle correctly.
"""

from __future__ import annotations

import heapq
from typing import Any, Dict, List, Optional

from graph_model import Graph


def _cumulative_physical_loss(loss_percentages: List[float]) -> float:
    """True cumulative loss (percentage) over a sequence of segments.

    Uses the multiplicative survival model: ``loss = 100*(1 - prod(1 - p/100))``.
    """
    surviving = 1.0
    for p in loss_percentages:
        surviving *= (1.0 - p / 100.0)
    return round((1.0 - surviving) * 100.0, 4)


def dijkstra(
    graph: Graph,
    source: str,
    target: str,
    objective: str = "distance",
) -> Dict[str, Any]:
    """Find the cheapest route between ``source`` and ``target``.

    Parameters
    ----------
    graph : Graph
        The farm irrigation network (weighted, undirected).
    source : str
        Id of the starting location (normally the water source).
    target : str
        Id of the destination location (normally a crop field).
    objective : str
        ``"distance"``  -> minimise total pipeline length (metres).
        ``"loss"``     -> minimise the *summed* water-loss percentage (a
                          heuristic proxy for physical loss).

    Returns
    -------
    dict with keys:
        found          : bool     True iff a route exists
        path_nodes     : list[str]   node ids from source to target
        path_edges     : list[dict]  edges along the route
        total_distance : float    total metres of pipe on the route
        cumulative_loss: float    TRUE physical loss (%) via multiplicative model
        total_cost     : float    installation cost of the route's pipes
        min_capacity   : float    smallest max-flow capacity on the route
        objective      : str      the objective used
        message        : str      status message (e.g. "no route exists")
    """
    if objective not in ("distance", "loss"):
        raise ValueError(
            f"objective must be 'distance' or 'loss' (got {objective!r})."
        )
    if source not in graph.nodes:
        raise ValueError(f"Unknown source node '{source}'.")
    if target not in graph.nodes:
        raise ValueError(f"Unknown target node '{target}'.")

    if source == target:
        return {
            "found": True,
            "path_nodes": [source],
            "path_edges": [],
            "total_distance": 0.0,
            "cumulative_loss": 0.0,
            "total_cost": 0.0,
            "min_capacity": 0.0,
            "objective": objective,
            "message": "Source and destination are the same location.",
        }

    # Weight of an edge for the chosen objective.
    def weight(e) -> float:
        if objective == "distance":
            w = e.length
        else:  # "loss" -> summed loss percentage (a non-negative proxy)
            w = e.water_loss_percent
        if w < 0:
            raise ValueError(
                f"Negative weight detected on pipeline {e.edge_id}: "
                f"Dijkstra requires non-negative weights."
            )
        return w

    # Dijkstra over the adjacency list using a binary min-heap.
    dist: Dict[str, float] = {source: 0.0}
    prev: Dict[str, Optional[str]] = {source: None}
    visited: set = set()
    heap: List[tuple] = [(0.0, source)]

    while heap:
        d, u = heapq.heappop(heap)
        if u in visited:
            continue
        visited.add(u)
        if u == target:
            break
        for v, e in graph.neighbours(u):
            if v in visited:
                continue
            nd = d + weight(e)
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))

    if target not in prev:
        return {
            "found": False,
            "path_nodes": [],
            "path_edges": [],
            "total_distance": 0.0,
            "cumulative_loss": 0.0,
            "total_cost": 0.0,
            "min_capacity": 0.0,
            "objective": objective,
            "message": (
                f"No route exists between '{source}' and '{target}'. The "
                f"destination is unreachable from the source over the current "
                f"pipelines."
            ),
        }

    # Reconstruct the path by walking the ``prev`` pointers backwards.
    path_nodes: List[str] = []
    node = target
    while node is not None:
        path_nodes.append(node)
        node = prev[node]
    path_nodes.reverse()

    # Collect the edges along the reconstructed path.
    path_edges = []
    for a, b in zip(path_nodes, path_nodes[1:]):
        for v, e in graph.neighbours(a):
            if v == b:
                path_edges.append(e)
                break

    total_distance = round(sum(e.length for e in path_edges), 4)
    cumulative_loss = _cumulative_physical_loss(
        [e.water_loss_percent for e in path_edges]
    )
    total_cost = round(sum(e.installation_cost for e in path_edges), 4)
    min_capacity = (
        round(min((e.max_flow_capacity for e in path_edges), default=0.0), 4)
    )

    if objective == "distance":
        obj_total = total_distance
        obj_label = "total length (metres)"
    else:
        # The proxy minimised by Dijkstra (summed loss %). Reported alongside
        # the true cumulative_loss for transparency.
        obj_total = round(sum(e.water_loss_percent for e in path_edges), 4)
        obj_label = "summed loss percentage (proxy)"

    return {
        "found": True,
        "path_nodes": path_nodes,
        "path_edges": [e.to_dict() for e in path_edges],
        "total_distance": total_distance,
        "cumulative_loss": cumulative_loss,
        "total_cost": total_cost,
        "min_capacity": min_capacity,
        "objective": objective,
        "objective_total": obj_total,
        "objective_label": obj_label,
        "message": (
            f"Route found via {objective}. Note: for the 'loss' objective the "
            f"route minimises the *summed* loss percentage, a heuristic proxy; "
            f"the reported cumulative_loss uses the true multiplicative loss "
            f"model and may differ."
        ),
    }
