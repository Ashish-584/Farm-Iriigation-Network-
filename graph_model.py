"""Graph data model for the Farm Irrigation Network Optimizer.

This module defines the core data structures used to represent a farm
irrigation network as a weighted, undirected graph:

    * Node  -> a physical location (water source, pump, junction, crop field)
    * Edge  -> a pipeline connecting two nodes
    * Graph -> a collection of nodes and edges with validation helpers

The model is intentionally kept independent of the GUI and of any specific
algorithm so that the algorithms (Kruskal, Dijkstra) can be tested on their
own.  An irrigation network is modelled as a graph where:

    - each *node* is a farm location (water source, pump station, junction box
      or crop field), and
    - each *edge* is a pipeline carrying water between two locations.

Each pipeline stores several attributes (length, installation cost, water-loss
percentage and max flow capacity).  The algorithms can pick which attribute is
the primary "weight".
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import math


# ---------------------------------------------------------------------------
# Node type constants
# ---------------------------------------------------------------------------

# The four location types a node can represent on the farm.
NODE_TYPES = ["water_source", "pump", "junction", "crop_field"]

# Human readable labels used in the GUI.
NODE_LABELS: Dict[str, str] = {
    "water_source": "Water Source",
    "pump": "Pump",
    "junction": "Junction",
    "crop_field": "Crop Field",
}

# Default visual style per node type (color and shape) used by Cytoscape.js.
NODE_STYLE: Dict[str, Dict[str, str]] = {
    "water_source": {"color": "#1976d2", "shape": "ellipse"},
    "pump": {"color": "#2e7d38", "shape": "triangle"},
    "junction": {"color": "#6a1b9a", "shape": "square"},
    "crop_field": {"color": "#c62828", "shape": "rectangle"},
}


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

class Node:
    """A physical location on the farm represented as a graph vertex.

    Attributes
    ----------
    node_id : str
        Unique identifier for the location (e.g. "S1", "F5").
    node_type : str
        One of the values in ``NODE_TYPES``.
    name : str
        Human friendly label shown in the UI.
    x, y : float
        Canvas coordinates used for the visual layout.
    water_requirement : float
        Litres of water needed by this location per planning period.  Only
        meaningful for crop fields, but stored for every node for simplicity.
    priority : int
        Scheduling priority (higher = more important).  Used by the greedy
        irrigation scheduler.
    """

    def __init__(
        self,
        node_id: str,
        node_type: str,
        name: Optional[str] = None,
        x: float = 0.0,
        y: float = 0.0,
        water_requirement: float = 0.0,
        priority: int = 1,
        urgency_score: float = 0.0,
    ) -> None:
        if node_type not in NODE_TYPES:
            raise ValueError(
                f"Invalid node type '{node_type}'. "
                f"Must be one of {NODE_TYPES}."
            )
        if node_id is None or str(node_id).strip() == "":
            raise ValueError("Node id must be a non-empty string.")

        self.node_id = str(node_id)
        self.node_type = node_type
        self.name = name if name else NODE_LABELS.get(node_type, str(node_id))
        self.x = float(x)
        self.y = float(y)
        self.water_requirement = float(water_requirement)
        self.priority = int(priority)
        self.urgency_score = float(urgency_score)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "water_requirement": self.water_requirement,
            "priority": self.priority,
            "urgency_score": self.urgency_score,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Node":
        return cls(
            node_id=data["node_id"],
            node_type=data["node_type"],
            name=data.get("name"),
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.0)),
            water_requirement=float(data.get("water_requirement", 0.0)),
            priority=int(data.get("priority", 1)),
            urgency_score=float(data.get("urgency_score", 0.0)),
        )

    def __repr__(self) -> str:
        return f"Node({self.node_id!r}, {self.node_type!r}, {self.name!r})"


# ---------------------------------------------------------------------------
# Edge
# ---------------------------------------------------------------------------

class Edge:
    """A weighted, undirected pipeline between two nodes.

    Parameters
    ----------
    u, v : str
        The ids of the two endpoint nodes.
    length : float
        Pipeline length in metres (must be >= 0).
    installation_cost : float
        Cost to install the pipeline in arbitrary rupees (must be >= 0).
    water_loss_percent : float
        Estimated water lost per 100 m of pipe ... actually a percentage of the
        water that traverses this segment (must be in [0, 100]).
    max_flow_capacity : float
        Maximum flow capacity in litres/minute (must be >= 0).
    edge_id : str, optional
        Optional explicit edge identifier.  If omitted one is derived from the
        endpoints so that each undirected edge has a stable id.
    """

    def __init__(
        self,
        u: str,
        v: str,
        length: float,
        installation_cost: float,
        water_loss_percent: float,
        max_flow_capacity: float,
        edge_id: Optional[str] = None,
    ) -> None:
        if u == v:
            raise ValueError(
                f"Self-loop on node '{u}' is not allowed: a pipeline must "
                f"connect two distinct locations."
            )
        if length < 0:
            raise ValueError(
                f"Pipeline length must be non-negative (got {length})."
            )
        if installation_cost < 0:
            raise ValueError(
                f"Installation cost must be non-negative (got {installation_cost})."
            )
        if not (0 <= water_loss_percent <= 100):
            raise ValueError(
                f"Water-loss percentage must be between 0 and 100 "
                f"(got {water_loss_percent})."
            )
        if max_flow_capacity < 0:
            raise ValueError(
                f"Max flow capacity must be non-negative (got {max_flow_capacity})."
            )

        self.u = str(u)
        self.v = str(v)
        self.length = float(length)
        self.installation_cost = float(installation_cost)
        self.water_loss_percent = float(water_loss_percent)
        self.max_flow_capacity = float(max_flow_capacity)
        # Stable id that is independent of the direction of the endpoints.
        self.edge_id = edge_id or self._make_id(u, v)

    @staticmethod
    def _make_id(u: str, v: str) -> str:
        return f"{u}__{v}" if u <= v else f"{v}__{u}"

    def other(self, node_id: str) -> str:
        """Return the endpoint that is NOT ``node_id``."""
        if node_id == self.u:
            return self.v
        return self.u

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "u": self.u,
            "v": self.v,
            "length": self.length,
            "installation_cost": self.installation_cost,
            "water_loss_percent": self.water_loss_percent,
            "max_flow_capacity": self.max_flow_capacity,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Edge":
        return cls(
            u=data["u"],
            v=data["v"],
            length=float(data["length"]),
            installation_cost=float(data["installation_cost"]),
            water_loss_percent=float(data["water_loss_percent"]),
            max_flow_capacity=float(data["max_flow_capacity"]),
            edge_id=data.get("edge_id"),
        )

    def __repr__(self) -> str:
        return (
            f"Edge({self.u}->{self.v}, len={self.length}, "
            f"cost={self.installation_cost}, loss={self.water_loss_percent}%)"
        )


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

class Graph:
    """A weighted undirected graph with validation.

    Internally nodes are kept in a dict keyed by id and edges are kept both in
    an ordered list (for iteration/display) and in an adjacency map (for fast
    neighbour lookup).  All mutation methods validate inputs and raise
    ``ValueError`` on anything invalid so the Flask layer can turn the error
    into a clear UI message rather than silently dropping bad data.
    """

    def __init__(self) -> None:
        # id -> Node
        self.nodes: Dict[str, Node] = {}
        # edge_id -> Edge (unique, undirected)
        self.edges: Dict[str, Edge] = {}
        # node_id -> list[Edge]  (each edge reference is shared)
        self._adj: Dict[str, List[Edge]] = defaultdict(list)

    # -- queries ----------------------------------------------------------------
    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    @property
    def total_length(self) -> float:
        return sum(e.length for e in self.edges.values())

    @property
    def total_cost(self) -> float:
        return sum(e.installation_cost for e in self.edges.values())

    def has_node(self, node_id: str) -> bool:
        return node_id in self.nodes

    def has_edge(self, u: str, v: str) -> bool:
        return Edge._make_id(u, v) in self.edges

    def neighbours(self, node_id: str) -> List[Tuple[str, Edge]]:
        """Return (neighbour_id, edge) pairs for a node."""
        return [(e.other(node_id), e) for e in self._adj.get(node_id, [])]

    def get_node(self, node_id: str) -> Optional[Node]:
        return self.nodes.get(node_id)

    def get_edge(self, edge_id: str) -> Optional[Edge]:
        return self.edges.get(edge_id)

    def node_ids(self) -> List[str]:
        return list(self.nodes.keys())

    def edge_list(self) -> List[Edge]:
        return list(self.edges.values())

    # -- mutations --------------------------------------------------------------
    def add_node(self, node: Node) -> None:
        if node.node_id in self.nodes:
            raise ValueError(
                f"Duplicate node id '{node.node_id}': each location on the "
                f"farm must have a unique id."
            )
        self.nodes[node.node_id] = node

    def remove_node(self, node_id: str) -> None:
        if node_id not in self.nodes:
            raise ValueError(f"Cannot delete node '{node_id}': it does not exist.")
        if self._adj.get(node_id):
            raise ValueError(
                f"Cannot delete node '{node_id}': it still has pipelines "
                f"connected to it. Remove the pipelines first."
            )
        del self.nodes[node_id]

    def add_edge(self, edge: Edge) -> None:
        self._validate_edge_endpoints(edge)
        if edge.edge_id in self.edges:
            raise ValueError(
                f"A pipeline already exists between {edge.u} and {edge.v} "
                f"(id {edge.edge_id}). Duplicate edges are not allowed."
            )
        self.edges[edge.edge_id] = edge
        self._adj[edge.u].append(edge)
        self._adj[edge.v].append(edge)

    def remove_edge(self, edge_id: str) -> None:
        if edge_id not in self.edges:
            raise ValueError(f"Cannot delete pipeline '{edge_id}': it does not exist.")
        edge = self.edges.pop(edge_id)
        self._adj[edge.u] = [
            e for e in self._adj[edge.u] if e.edge_id != edge_id
        ]
        self._adj[edge.v] = [
            e for e in self._adj[edge.v] if e.edge_id != edge_id
        ]

    def remove_edge_by_endpoints(self, u: str, v: str) -> None:
        edge_id = Edge._make_id(u, v)
        self.remove_edge(edge_id)

    def _validate_edge_endpoints(self, edge: Edge) -> None:
        if edge.u not in self.nodes:
            raise ValueError(
                f"Edge references unknown node '{edge.u}' (the pipeline's "
                f"first endpoint does not exist)."
            )
        if edge.v not in self.nodes:
            raise ValueError(
                f"Edge references unknown node '{edge.v}' (the pipeline's "
                f"second endpoint does not exist)."
            )

    # -- connectivity -----------------------------------------------------------
    def connected_components(self) -> int:
        """Return the number of connected components (Kruskal forest size)."""
        if not self.nodes:
            return 0
        seen = set()
        comp = 0
        for nid in self.nodes:
            if nid in seen:
                continue
            comp += 1
            stack = [nid]
            while stack:
                cur = stack.pop()
                if cur in seen:
                    continue
                seen.add(cur)
                for nb, _ in self.neighbours(cur):
                    if nb not in seen:
                        stack.append(nb)
        return comp

    # -- serialisation ----------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges.values()],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Graph":
        g = cls()
        for n in data.get("nodes", []):
            g.add_node(Node.from_dict(n))
        for e in data.get("edges", []):
            g.add_edge(Edge.from_dict(e))
        return g
