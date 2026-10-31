"""Greedy irrigation scheduling.

This module assigns a limited amount of water to the crop fields on the farm.
The approach is a simple *greedy* heuristic, **not** a mathematically
guaranteed globally optimal schedule (that would require solving a
multi-dimensional knapsack / LP problem).  It is, however, easy to explain and
fast.

Priority score
--------------
Each crop field already has a ``priority`` (set by the farmer) and may optionally
carry an ``urgency_score``.  We combine them into a single score so that, all
else being equal, more urgent / higher-priority fields are served first::

    score = priority * 1_000_000 + urgency_score

Higher score -> served earlier.  Ties are broken by lower water requirement so
that small fields are filled completely before large ones (a variant of
"best-effort first").

Allocation rule
---------------
Walk the sorted fields and give each one as much of the remaining water as
possible:

    * fully served   -> requirement met entirely, water is deducted;
    * partially served -> some, but not all, of the requirement is met;
    * waiting        -> no water left at all.

The total allocated never exceeds the available supply.
"""

from __future__ import annotations

from typing import Any, Dict, List

from graph_model import Graph


def greedy_irrigation_schedule(
    graph: Graph,
    available_water: float,
) -> Dict[str, Any]:
    """Produce a greedy irrigation schedule for the crop fields in ``graph``.

    Parameters
    ----------
    graph : Graph
        The farm network; every ``crop_field`` node contributes its
        ``water_requirement``, ``priority`` and ``urgency_score``.
    available_water : float
        Total litres of water available for the planning period.

    Returns
    -------
    dict with keys:
        fully_served    : list[dict]   fields that received their full requirement
        partial_served  : list[dict]   fields that received some water but not all
        waiting         : list[dict]   fields that received nothing
        total_required  : float
        total_allocated : float
        available_water : float
        num_fields      : int
        explanation     : str
    """
    if available_water < 0:
        raise ValueError(
            f"Available water must be non-negative (got {available_water})."
        )

    # Gather crop fields as (node_id, requirement, priority, urgency, name).
    fields: List[Dict[str, Any]] = []
    for node in graph.nodes.values():
        if node.node_type == "crop_field":
            fields.append(
                {
                    "node_id": node.node_id,
                    "name": node.name,
                    "requirement": float(node.water_requirement),
                    "allocated": 0.0,
                    "priority": int(node.priority),
                    "urgency_score": float(node.urgency_score),
                    "status": "waiting",
                }
            )

    # Sort by the documented priority score (higher first); tie-break by lower
    # requirement so small fields can be fully served.
    fields.sort(
        key=lambda f: (
            -(f["priority"] * 1_000_000 + f["urgency_score"]),
            f["requirement"],
        )
    )

    remaining = float(available_water)
    for f in fields:
        if f["requirement"] <= 0:
            f["status"] = "fully_served" if f["requirement"] == 0 else "waiting"
            f["allocated"] = 0.0
            continue
        if remaining <= 0:
            f["status"] = "waiting"
            continue
        if remaining >= f["requirement"]:
            # Fully served.
            f["allocated"] = f["requirement"]
            f["status"] = "fully_served"
            remaining -= f["requirement"]
        else:
            # Partially served with whatever remains.
            f["allocated"] = round(remaining, 4)
            f["status"] = "partial"
            remaining = 0.0

    total_required = round(sum(f["requirement"] for f in fields), 4)
    total_allocated = round(available_water - remaining, 4)

    explanation = (
        "Water was distributed field-by-field in order of a greedy priority "
        "score (priority*1,000,000 + urgency_score, higher first).  Each field "
        "received as much of the remaining supply as its requirement allowed.  "
        "This is a simplified heuristic and is NOT guaranteed to be globally "
        "optimal; a full linear-programming or knapsack model could do better "
        "for some demand patterns."
    )

    return {
        "fully_served": [
            {k: v for k, v in f.items() if k != "priority"} for f in fields if f["status"] == "fully_served"
        ],
        "partial_served": [
            {k: v for k, v in f.items()} for f in fields if f["status"] == "partial"
        ],
        "waiting": [
            {k: v for k, v in f.items()} for f in fields if f["status"] == "waiting"
        ],
        "total_required": total_required,
        "total_allocated": total_allocated,
        "available_water": available_water,
        "num_fields": len(fields),
        "explanation": explanation,
    }
