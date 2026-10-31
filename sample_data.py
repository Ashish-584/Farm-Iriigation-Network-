"""Predefined demonstration data for the sample farm irrigation network.

The sample network below is explicitly *illustrative*.  It models a small farm
with:

    * 1 water source (S)
    * 2 pumps / junctions (P1, J1)
    * 6 crop fields (F1..F6)
    * 11 pipeline connections (some forming a cycle so Kruskal has edges it can
      reject)
    * realistic-looking but illustrative distances, costs, loss percentages
      and capacities.

The network is connected, so Kruskal will produce a single tree.

Layout (not to precise scale, x/y are canvas coordinates in the frontend):

    S ----- P1 ----- J1
    |  \     |      /  |
    |   \    |     /   |
    F1   F2  F3  F4   F5
               | \
               |  F6
"""

from __future__ import annotations

from typing import Any, Dict

from graph_model import Edge, Graph, Node


def build_sample_graph() -> Graph:
    """Return a fresh :class:`Graph` containing the sample network."""
    g = Graph()

    # -- nodes ----------------------------------------------------------------
    g.add_node(Node("S", "water_source", name="Main Reservoir",
                    x=150, y=150, water_requirement=0, priority=0))
    g.add_node(Node("P1", "pump", name="Pump Station 1",
                    x=300, y=150, water_requirement=0, priority=0))
    g.add_node(Node("J1", "junction", name="Junction Box A",
                    x=450, y=150, water_requirement=0, priority=0))

    g.add_node(Node("F1", "crop_field", name="Wheat Field 1",
                    x=80, y=50, water_requirement=1200, priority=3))
    g.add_node(Node("F2", "crop_field", name="Wheat Field 2",
                    x=80, y=250, water_requirement=900, priority=2))
    g.add_node(Node("F3", "crop_field", name="Corn Field 1",
                    x=300, y=50, water_requirement=1500, priority=4))
    g.add_node(Node("F4", "crop_field", name="Corn Field 2",
                    x=300, y=250, water_requirement=1100, priority=3))
    g.add_node(Node("F5", "crop_field", name="Rice Field",
                    x=450, y=50, water_requirement=2000, priority=1))
    g.add_node(Node("F6", "crop_field", name="Soybean Field",
                    x=450, y=250, water_requirement=800, priority=5))

    # -- edges (pipelines) ----------------------------------------------------
    # (u, v, length(m), cost, water_loss_% per segment, max_flow l/min)
    # NOTE: every pipeline connects a distinct pair of locations (no duplicate
    # edges). Two cycles exist:  P1-J1-F3-P1  and  J1-F3-F4-J1  and  J1-F4-F5-J1,
    # so Kruskal has edges it can reject.
    edges = [
        ("S", "P1", 120, 6000, 2.0, 250),
        ("S", "F1", 80, 4000, 3.0, 150),
        ("S", "F2", 90, 4500, 3.5, 150),
        ("P1", "J1", 150, 7500, 1.5, 300),
        ("P1", "F3", 60, 3200, 2.5, 200),
        ("J1", "F5", 70, 3800, 2.2, 180),
        ("J1", "F4", 85, 4400, 2.8, 180),
        ("J1", "F6", 95, 4900, 3.0, 170),
        ("J1", "F3", 130, 6600, 2.0, 200),
        ("F3", "F4", 50, 2700, 4.0, 120),  # cycle within crop area
        ("F4", "F5", 65, 3500, 2.5, 160),  # cycle within crop area
    ]

    for u, v, length, cost, loss, cap in edges:
        g.add_edge(
            Edge(u, v, length=length, installation_cost=cost,
                 water_loss_percent=loss, max_flow_capacity=cap)
        )

    return g


def sample_as_dict() -> Dict[str, Any]:
    return build_sample_graph().to_dict()


# The total water available for the planning period in the scheduling demo.
SAMPLE_AVAILABLE_WATER = 3500.0
