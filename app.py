"""Flask application for the Farm Irrigation Network Optimizer.

Run with::

    python app.py

and open http://127.0.0.1:5000/ in a browser.

The backend exposes both HTML pages (rendered with Jinja2 templates) and a
small JSON API used by the frontend JavaScript.  The irrigation network is
persisted to ``data/farm_network.json`` so edits survive between page reloads.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from flask import Flask, jsonify, render_template, request

from graph_model import Edge, Graph, Node, NODE_LABELS
from kruskal import kruskal_mst, savings_percent, WEIGHT_KEYS
from dijkstra import dijkstra
from irrigation_schedule import greedy_irrigation_schedule
from performance_test import run_performance_test, generate_random_graph
from sample_data import build_sample_graph, SAMPLE_AVAILABLE_WATER

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DATA_FILE = os.path.join(DATA_DIR, "farm_network.json")

os.makedirs(DATA_DIR, exist_ok=True)

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def load_graph() -> Graph:
    """Load the network from the JSON file, or fall back to the sample."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            g = Graph.from_dict(data)
            return g
        except (ValueError, KeyError, json.JSONDecodeError):
            # Corrupt file -> fall back to the sample demo so the user is not
            # stranded on an error screen.
            pass
    return build_sample_graph()


def save_graph(graph: Graph) -> None:
    """Persist the network to the JSON file."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(graph.to_dict(), f, indent=2)


# ---------------------------------------------------------------------------
# JSON API helpers
# ---------------------------------------------------------------------------

def json_error(message: str, status: int = 400) -> Any:
    resp = jsonify({"error": True, "message": message})
    resp.status_code = status
    return resp


# ---------------------------------------------------------------------------
# HTML pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/network")
def network():
    return render_template("network.html")


@app.route("/optimize")
def optimize():
    return render_template("optimize.html")


@app.route("/schedule")
def schedule():
    return render_template("schedule.html")


@app.route("/performance")
def performance():
    return render_template("performance.html")


@app.route("/about")
def about():
    return render_template("about.html")


# ---------------------------------------------------------------------------
# Network API
# ---------------------------------------------------------------------------

@app.route("/api/network")
def api_network():
    """Return the whole current network as JSON."""
    g = load_graph()
    return jsonify(g.to_dict())


@app.route("/api/network/save", methods=["POST"])
def api_network_save():
    """Replace the persisted network with the JSON body."""
    payload = request.get_json(silent=True) or {}
    try:
        g = Graph.from_dict(payload)
        save_graph(g)
        return jsonify({"ok": True, "nodes": g.node_count, "edges": g.edge_count})
    except ValueError as exc:
        return json_error(str(exc))


@app.route("/api/nodes")
def api_nodes():
    g = load_graph()
    return jsonify({"nodes": [n.to_dict() for n in g.nodes.values()],
                    "node_types": NODE_LABELS})


@app.route("/api/nodes", methods=["POST"])
def api_add_node():
    data = request.get_json(silent=True) or {}
    try:
        node = Node(
            node_id=data.get("node_id"),
            node_type=data.get("node_type", "crop_field"),
            name=data.get("name"),
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            water_requirement=float(data.get("water_requirement", 0)),
            priority=int(data.get("priority", 1)),
            urgency_score=float(data.get("urgency_score", 0)),
        )
        g = load_graph()
        g.add_node(node)
        save_graph(g)
        return jsonify({"ok": True, "node": node.to_dict()})
    except (ValueError, TypeError) as exc:
        return json_error(str(exc))


@app.route("/api/nodes/<node_id>", methods=["PUT"])
def api_update_node(node_id):
    data = request.get_json(silent=True) or {}
    try:
        g = load_graph()
        if node_id not in g.nodes:
            return json_error(f"Node '{node_id}' not found.", 404)
        node = g.nodes[node_id]
        node.node_type = data.get("node_type", node.node_type)
        node.name = data.get("name", node.name)
        node.x = float(data.get("x", node.x))
        node.y = float(data.get("y", node.y))
        node.water_requirement = float(data.get("water_requirement", node.water_requirement))
        node.priority = int(data.get("priority", node.priority))
        node.urgency_score = float(data.get("urgency_score", node.urgency_score))
        save_graph(g)
        return jsonify({"ok": True, "node": node.to_dict()})
    except (ValueError, TypeError) as exc:
        return json_error(str(exc))


@app.route("/api/nodes/<node_id>", methods=["DELETE"])
def api_delete_node(node_id):
    try:
        g = load_graph()
        g.remove_node(node_id)
        save_graph(g)
        return jsonify({"ok": True, "deleted": node_id})
    except ValueError as exc:
        return json_error(str(exc))


@app.route("/api/edges", methods=["POST"])
def api_add_edge():
    data = request.get_json(silent=True) or {}
    try:
        g = load_graph()
        edge = Edge(
            u=data.get("u"),
            v=data.get("v"),
            length=float(data.get("length", 0)),
            installation_cost=float(data.get("installation_cost", 0)),
            water_loss_percent=float(data.get("water_loss_percent", 0)),
            max_flow_capacity=float(data.get("max_flow_capacity", 0)),
            edge_id=data.get("edge_id"),
        )
        g.add_edge(edge)
        save_graph(g)
        return jsonify({"ok": True, "edge": edge.to_dict()})
    except (ValueError, TypeError) as exc:
        return json_error(str(exc))


@app.route("/api/edges/<edge_id>", methods=["DELETE"])
def api_delete_edge(edge_id):
    try:
        g = load_graph()
        g.remove_edge(edge_id)
        save_graph(g)
        return jsonify({"ok": True, "deleted": edge_id})
    except ValueError as exc:
        return json_error(str(exc))


@app.route("/api/sample")
def api_sample():
    """Restore the original sample demonstration network."""
    g = build_sample_graph()
    save_graph(g)
    return jsonify({"ok": True, "message": "Sample demonstration network loaded.",
                    "nodes": g.node_count, "edges": g.edge_count})


# ---------------------------------------------------------------------------
# Algorithm API
# ---------------------------------------------------------------------------

@app.route("/api/mst")
def api_mst():
    weight = request.args.get("weight", "length")
    if weight not in WEIGHT_KEYS:
        return json_error(f"weight must be one of {list(WEIGHT_KEYS)}.")
    g = load_graph()
    result = kruskal_mst(g, weight=weight)
    # Attach the original (ungraph) totals for the side-by-side comparison.
    original_total = getattr(g, "total_length" if weight == "length"
                             else "total_cost")
    original_other = g.total_cost if weight == "length" else g.total_length
    result["original_total"] = original_total
    result["original_other_total"] = original_other
    result["savings_percent"] = savings_percent(original_total, result["total_weight"])
    return jsonify(result)


@app.route("/api/shortest-path")
def api_shortest_path():
    source = request.args.get("source")
    target = request.args.get("target")
    objective = request.args.get("objective", "distance")
    if not source or not target:
        return json_error("Both 'source' and 'target' query parameters are required.")
    try:
        g = load_graph()
        result = dijkstra(g, source, target, objective=objective)
        return jsonify(result)
    except ValueError as exc:
        return json_error(str(exc))


@app.route("/api/schedule", methods=["POST"])
def api_schedule():
    data = request.get_json(silent=True) or {}
    try:
        available = float(data.get("available_water", SAMPLE_AVAILABLE_WATER))
        g = load_graph()
        result = greedy_irrigation_schedule(g, available_water=available)
        return jsonify(result)
    except (ValueError, TypeError) as exc:
        return json_error(str(exc))


# ---------------------------------------------------------------------------
# Performance API
# ---------------------------------------------------------------------------

@app.route("/api/performance")
def api_performance():
    try:
        sizes = [int(s) for s in request.args.get("sizes", "50,200,800,2000,5000").split(",")]
        repeat = int(request.args.get("repeat", "5"))
        seed = int(request.args.get("seed", "42"))
        result = run_performance_test(sizes=sizes, seed=seed, repeat=repeat)
        return jsonify(result)
    except (ValueError, TypeError) as exc:
        return json_error(str(exc))


# ---------------------------------------------------------------------------
# Summary cards data (used by every page)
# ---------------------------------------------------------------------------

@app.route("/api/summary")
def api_summary():
    g = load_graph()
    # Recompute the MST length for the optimized metric.
    mst = kruskal_mst(g, weight="length")
    total_loss = sum(e.water_loss_percent for e in g.edge_list()) / max(1, g.edge_count)
    return jsonify({
        "num_nodes": g.node_count,
        "num_pipelines": g.edge_count,
        "total_original_length": round(g.total_length, 2),
        "optimized_length": round(mst["total_length"], 2),
        "estimated_installation_cost": round(g.total_cost, 2),
        "estimated_water_loss": round(total_loss, 2),
        "savings_percent": savings_percent(g.total_length, mst["total_length"]),
        "node_types": NODE_LABELS,
    })


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
