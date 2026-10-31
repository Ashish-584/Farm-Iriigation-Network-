"""Performance testing for Kruskal and Dijkstra.

Generates random but *reproducible* weighted graphs (a fixed random seed
guarantees the same graphs across runs) of increasing size, then times the
algorithms.  Because a single run of an O(n log n) algorithm can take only a few
microseconds, each measurement averages over several *repeat* runs to reduce
timer noise.

Theoretical complexity (documented separately in the README):
    * Kruskal            : O(E log E)   (dominated by sorting the edges)
    * Dijkstra (heap)    : O((V + E) log V)
    * Greedy scheduling  : O(F log F)   (dominated by sorting the fields)

The measured numbers on your machine will, of course, differ from these
asymptotic formulas -- the theory describes growth rate, the timing describes
actual wall-clock seconds.  Both are reported.
"""

from __future__ import annotations

import random
import time
from typing import Any, Dict, List

from graph_model import Edge, Graph, Node
from kruskal import kruskal_mst
from dijkstra import dijkstra


def generate_random_graph(
    num_vertices: int,
    seed: int,
    edge_factor: float = 1.6,
) -> Graph:
    """Build a connected random weighted graph.

    Parameters
    ----------
    num_vertices : int
        Number of nodes.
    seed : int
        Deterministic RNG seed for reproducibility.
    edge_factor : float
        Average number of edges per vertex (controls density).  With
        ``edge_factor >= 1`` the generated graph is very likely connected.

    The graph is guaranteed connected by first building a random spanning
    tree, then sprinkling extra random edges on top.
    """
    rng = random.Random(seed)
    g = Graph()
    # Add vertices laid out on a circle (layout is cosmetic only).
    for i in range(num_vertices):
        nid = f"N{i}"
        g.add_node(Node(nid, "junction", name=nid))

    # 1) Base spanning tree so the graph is connected.
    ids = g.node_ids()
    shuffled = ids[:]
    rng.shuffle(shuffled)
    for i in range(1, len(shuffled)):
        u, v = shuffled[i - 1], shuffled[i]
        g.add_edge(
            Edge(u, v, length=rng.uniform(10, 100),
                 installation_cost=rng.uniform(200, 5000),
                 water_loss_percent=rng.uniform(1, 12),
                 max_flow_capacity=rng.uniform(80, 500))
        )

    # 2) Add extra random edges to create cycles / density.
    num_edges = int(num_vertices * edge_factor)
    attempts = 0
    while g.edge_count < num_edges and attempts < num_edges * 5:
        attempts += 1
        u = rng.choice(ids)
        v = rng.choice(ids)
        if u == v or g.has_edge(u, v):
            continue
        g.add_edge(
            Edge(u, v, length=rng.uniform(10, 100),
                 installation_cost=rng.uniform(200, 5000),
                 water_loss_percent=rng.uniform(1, 12),
                 max_flow_capacity=rng.uniform(80, 500))
        )

    return g


def _time_ms(func, *args, repeat: int = 5, **kwargs) -> float:
    """Run ``func`` ``repeat`` times and return the average milliseconds.

    Using the best-of / average approach keeps results stable for very fast
    operations (a single call can be sub-millisecond and noisy).
    """
    times: List[float] = []
    result = None
    for _ in range(repeat):
        t0 = time.perf_counter()
        result = func(*args, **kwargs)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000.0)
    avg = sum(times) / len(times)
    return avg, result


def run_performance_test(
    sizes: List[int] = None,
    seed: int = 42,
    repeat: int = 5,
) -> Dict[str, Any]:
    """Run Kruskal and Dijkstra across graphs of increasing size.

    Returns a dict suitable for JSON serialization containing the per-size
    measurements plus the theoretical complexity notes.
    """
    if sizes is None:
        sizes = [50, 200, 800, 2000, 5000]

    results: List[Dict[str, Any]] = []
    for n in sizes:
        g = generate_random_graph(n, seed=seed)
        edge_count = g.edge_count

        kruskal_ms, mst = _time_ms(kruskal_mst, g, weight="length", repeat=repeat)

        # Pick a deterministic source/target pair that are very likely connected.
        first, last = g.node_ids()[0], g.node_ids()[-1]
        dijkstra_ms, path = _time_ms(
            dijkstra, g, first, last, objective="distance", repeat=repeat
        )

        results.append(
            {
                "vertices": g.node_count,
                "edges": edge_count,
                "kruskal_ms": round(kruskal_ms, 4),
                "dijkstra_ms": round(dijkstra_ms, 4),
                "mst_total_weight": round(mst["total_weight"], 4),
                "mst_edges": mst["num_edges"],
                "dijkstra_found": path["found"],
                "dijkstra_route_cost": round(path.get("total_distance", 0.0), 4),
                "connected": mst["is_connected"],
            }
        )

    return {
        "seed": seed,
        "repeat": repeat,
        "sizes": sizes,
        "results": results,
        "theoretical": {
            "kruskal": "O(E log E)  -- dominated by sorting the edges",
            "dijkstra": "O((V + E) log V) -- adjacency list + binary heap",
            "greedy_scheduling": "O(F log F) -- dominated by sorting fields",
            "note": "Theoretical complexity describes growth rate, not measured "
                    "seconds.  Measured times are averages of repeated runs.",
        },
    }
