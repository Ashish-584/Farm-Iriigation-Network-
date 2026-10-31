"""Kruskal's algorithm for the Minimum Spanning Tree / Forest.

Kruskal's algorithm builds a minimum spanning tree (MST) of a weighted,
undirected graph by greedily adding the cheapest edge that does not create a
cycle.  Cycles are detected with a *Disjoint Set Union* (DSU) data structure,
also called a *Union-Find*.  The DSU is made fast with two standard tricks:

    * **Path compression** -- when we look up the root of a node we flatten the
      tree along the way, so future lookups are nearly O(1).
    * **Union by rank** -- we always hang the shorter tree under the root of the
      taller one, keeping the DSU trees shallow.

This implementation is standalone: it depends only on :class:`graph_model.Graph`
and the Python standard library.  No graph library is used to compute the MST.

Why does Kruskal produce a *minimum* spanning tree?
    The greedy choice property holds: at every step we add the globally
    cheapest edge that connects two *different* components.  Suppose an optimal
    MST ``T`` did not contain the edge ``e`` chosen by Kruskal.  Adding ``e`` to
    ``T`` forms a cycle; removing the heaviest edge on that cycle that is not
    lighter than ``e`` keeps ``T`` a spanning tree and does not increase its
    total weight.  Repeating this exchange argument proves the greedy tree is
    optimal.  (This is the classic cut property / exchange argument.)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from graph_model import Edge, Graph


class DisjointSetUnion:
    """A Union-Find structure with path compression and union by rank.

    Each node is an integer index.  ``parent[i]`` is the parent of ``i`` and
    ``rank[i]`` is an upper bound on the height of the subtree rooted at ``i``.
    """

    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.rank = [0] * n
        self.num_components = n

    def find(self, x: int) -> int:
        # Path compression: point every node on the path directly at the root.
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, x: int, y: int) -> bool:
        """Merge the sets containing ``x`` and ``y``.

        Returns ``True`` if a merge happened (the two were in different sets)
        and ``False`` if they were already in the same set (would form a cycle).
        """
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return False  # same component -> adding this edge makes a cycle
        # Union by rank: hang the shorter tree under the taller one.
        if self.rank[rx] < self.rank[ry]:
            self.parent[rx] = ry
        elif self.rank[rx] > self.rank[ry]:
            self.parent[ry] = rx
        else:
            self.parent[ry] = rx
            self.rank[rx] += 1
        self.num_components -= 1
        return True


# Valid choices for the primary edge weight.
WEIGHT_KEYS = ("length", "installation_cost")


def kruskal_mst(
    graph: Graph,
    weight: str = "length",
) -> Dict[str, Any]:
    """Compute a minimum spanning tree (or forest) of ``graph``.

    Parameters
    ----------
    graph : Graph
        The input irrigation network (weighted, undirected).
    weight : str
        Which edge attribute is the primary "cost" to minimise.  Either
        ``"length"`` (metres of pipe) or ``"installation_cost"`` (rupees).
        Whichever is *not* chosen is still reported in the totals.

    Returns
    -------
    dict with keys:
        selected_edges : list[dict]   edges chosen for the tree/forest
        total_weight   : float        sum of the *chosen* weight of selected edges
        total_length   : float        sum of lengths of selected edges
        total_cost     : float        sum of installation costs of selected edges
        num_edges      : int          number of selected edges
        weight_key     : str          the weight attribute used
        is_connected   : bool         True iff the whole graph is connected
        components     : int          number of connected components
        cycle_edges    : int          number of edges Kruskal rejected (cycles)
        explanation    : str          human readable description
    """
    if weight not in WEIGHT_KEYS:
        raise ValueError(
            f"weight must be one of {WEIGHT_KEYS} (got {weight!r})."
        )

    n = graph.node_count
    selected_ids: List[str] = []
    cycle_edges = 0

    # The empty / single-node cases are trivially handled: an MST of a graph
    # with no edges (or 0/1 nodes) is just the set of vertices itself.
    if n <= 1 or graph.edge_count == 0:
        total_length = 0.0
        total_cost = 0.0
        selected_edges = []
        return {
            "selected_edges": selected_edges,
            "selected_edge_ids": [],
            "total_weight": 0.0,
            "total_length": total_length,
            "total_cost": total_cost,
            "num_edges": 0,
            "weight_key": weight,
            "is_connected": graph.node_count <= 1,
            "components": max(1, graph.connected_components()) if graph.node_count else 0,
            "cycle_edges": 0,
            "explanation": (
                "A spanning tree of a graph with no pipelines is just the set "
                "of locations themselves, so 0 edges are selected."
                if graph.node_count
                else "The graph is empty; there is nothing to connect."
            ),
        }

    # 1) Sort edges by the chosen weight (ascending).  This is the "greedy"
    #    ordering -- cheapest first.
    edges = sorted(
        graph.edge_list(),
        key=lambda e: getattr(e, weight),
    )

    # 2) Map node ids (strings) to integer indices for the DSU.
    node_ids = graph.node_ids()
    index = {nid: i for i, nid in enumerate(node_ids)}
    dsu = DisjointSetUnion(len(node_ids))

    # 3) Consider edges cheapest-first; add an edge iff its endpoints are in
    #    different components (i.e. it does not create a cycle).
    for e in edges:
        if dsu.union(index[e.u], index[e.v]):
            selected_ids.append(e.edge_id)
        else:
            # Same component on both ends -> this edge would form a cycle,
            # so Kruskal correctly rejects it.
            cycle_edges += 1

    selected_edges = [
        graph.get_edge(eid).to_dict() for eid in selected_ids if graph.get_edge(eid)
    ]

    total_length = sum(graph.get_edge(eid).length for eid in selected_ids)
    total_cost = sum(
        graph.get_edge(eid).installation_cost for eid in selected_ids
    )
    total_weight = sum(
        getattr(graph.get_edge(eid), weight) for eid in selected_ids
    )

    components = dsu.num_components
    is_connected = components == 1

    # Build an explanation string depending on whether the graph connected.
    if is_connected:
        explanation = (
            f"Kruskal's algorithm processed every pipeline ordered by "
            f"{weight}. Because the selected edges connect all {n} locations "
            f"without any cycle and have the minimum possible total {weight}, "
            f"they form a minimum spanning Tree. {cycle_edges} pipeline(s) were "
            f"rejected because adding them would have created a cycle."
        )
    else:
        explanation = (
            f"The network has {components} separate group(s) of locations that "
            f"are not connected to each other by any pipeline. Kruskal "
            f"therefore produced a minimum spanning Forest (one tree per "
            f"connected component) rather than a single tree. "
            f"To connect the whole farm, {components - 1} additional pipeline(s) "
            f"are required. {cycle_edges} pipeline(s) were rejected as redundant "
            f"(cyclic)."
        )

    return {
        "selected_edges": selected_edges,
        "selected_edge_ids": selected_ids,
        "total_weight": total_weight,
        "total_length": total_length,
        "total_cost": total_cost,
        "num_edges": len(selected_ids),
        "weight_key": weight,
        "is_connected": is_connected,
        "components": components,
        "cycle_edges": cycle_edges,
        "explanation": explanation,
    }


def savings_percent(original_total: float, optimized_total: float) -> Optional[float]:
    """Percentage saved: ``(original - optimized) / original * 100``.

    Returns ``None`` when the denominator (original total) is zero or invalid,
    so the caller never divides by zero.
    """
    if not original_total or original_total <= 0:
        return None
    if optimized_total < 0:
        return None
    return round((original_total - optimized_total) / original_total * 100, 2)
