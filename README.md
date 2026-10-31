# Farm Irrigation Network Optimizer

A college-level **Design and Analysis of Algorithms (DAA)** project that models a
farm irrigation network as a weighted graph and solves three classic problems
through an interactive web GUI:

| Page | Algorithm | Goal |
|------|-----------|------|
| Optimize Network | **Kruskal's MST** | Minimum-cost pipeline network connecting every location |
| Optimize Network | **Dijkstra** | Shortest water-loss path between a source and a crop field |
| Irrigation Schedule | **Greedy priority scheduling** | Fairly allocate limited water to crop fields |
| Performance Analysis | all of the above | Measure and chart real run-time vs theoretical complexity |

---

## 1. Project Objective & Problem Statement

Efficient irrigation is vital: water is scarce and pipelines are expensive to
install and lose water through leaks. This project helps a farmer reason about
three questions:

1. **What is the cheapest set of pipelines that connects the whole farm?**
   (Minimum Spanning Tree)
2. **Which route carries water to a field with the least loss?**
   (Shortest Path)
3. **Given limited water, which fields should be irrigated first?**
   (Greedy Scheduling)

The irrigation network is represented as a **weighted undirected graph** where
*each node is a farm location* (water source, pump, junction, crop field) and
*each edge is a pipeline* with length, installation cost, estimated water-loss
percentage and max flow capacity.

---

## 2. Technology Stack

| Layer | Technology |
|-------|------------|
| Backend & algorithms | Python 3 (Flask) |
| Graph model | `graph_model.py` (own classes, **no graph library for the core algorithms**) |
| MST | `kruskal.py` (DSU with path compression + union by rank, implemented from scratch) |
| Shortest path | `dijkstra.py` (adjacency list + `heapq` priority queue, from scratch) |
| Scheduling | `irrigation_schedule.py` (greedy, from scratch) |
| Benchmarking | `performance_test.py` (deterministic seeds) |
| Frontend | HTML5, CSS3, vanilla JavaScript |
| Graph visualization | **Cytoscape.js** (loaded via CDN) |
| Charts | **Chart.js** (loaded via CDN) |
| Data storage | JSON file (`data/farm_network.json`) |
| Tests | `pytest` |

No paid APIs, external databases or heavy frameworks are required. Only
**Flask** needs to be installed from PyPI; Cytoscape.js and Chart.js are loaded
from a CDN, so no Node.js / npm is needed.

---

## 3. Installation (Windows, VS Code)

Open **PowerShell** in the project folder and run:

```powershell
# 1. (Optional but recommended) create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) install the test runner
pip install pytest
```

> If you see *"execution of scripts is disabled on this system"* when
> activating the venv, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`
> first, then `git bash` users can use `source venv/Scripts/activate`.

---

## 4. Running the Application

```powershell
# activate the venv (if created in step 1 above)
.\venv\Scripts\Activate.ps1

# start Flask
python app.py
```

Then open a browser and go to:

```
http://127.0.0.1:5000/
```

The Flask development server runs in debug mode and auto-reloads when you edit
source files, so you can keep it running while you work.

---

## 5. System Architecture

```
app.py                       <-- Flask app + HTTP/JSON API  <--->  browser
  |-- graph_model.py         <-- Node / Edge / Graph (data model + validation)
  |-- kruskal.py             <-- Kruskal MST + DisjointSetUnion
  |-- dijkstra.py            <-- Dijkstra shortest path + loss model
  |-- irrigation_schedule.py <-- Greedy irrigation scheduling
  |-- performance_test.py    <-- Random graph generator + timing harness
  |-- sample_data.py         <-- Predefined demonstration network
  |-- data/farm_network.json <-- Persisted network state (JSON)
templates/                   <-- Jinja2 HTML pages
static/css/style.css         <-- Green / white / dark-green dashboard
static/js/common.js          <-- Cytoscape graph + legends + summary cards
static/js/{dashboard,network,optimize,schedule,performance}.js  <-- page logic
tests/                       <-- pytest unit tests
```

The **algorithms are independent of the GUI**: every algorithm module imports
only `graph_model` and the standard library, so it can be unit-tested without a
web server. The Flask layer merely loads the persisted graph, calls the
algorithm, and returns JSON. The frontend renders the JSON with Cytoscape.js
and Chart.js.

---

## 6. Algorithms

### 6.1 Kruskal's Minimum Spanning Tree

Sorts all pipelines by the chosen weight (length or installation cost) and greedily
adds the cheapest edge that joins two different components, detected by a
**Disjoint Set Union** (Union-Find) with path compression and union by rank.

```
sort edges E by weight ascending
DSU init(V)                         // parent[i]=i, rank[i]=0
MST = []
for each edge (u,v) in sorted E:
    if DSU.find(u) != DSU.find(v):  // different components -> safe to add
        MST.add(edge)
        DSU.union(u,v)
    else:
        discard edge                 // would create a cycle
return MST
```

* Produces a **minimum spanning forest** when the graph is disconnected.
* Reports the number of rejected cycle edges and the number of connected
  components.
* Shows original vs optimized totals and percentage savings.

**Why is the result a minimum spanning tree?** The *cut property*: at each step
the cheapest edge crossing a cut between two components is part of some MST.
Adding it and never removing it keeps the growing tree optimal (classic
exchange argument).

### 6.2 Dijkstra's Shortest Path

Uses an adjacency list and a binary min-heap (`heapq`) to repeatedly extend the
cheapest known path.

```
dist[source]=0, prev[source]=nil
PQ = min-heap; PQ.push((0, source))
while PQ not empty:
    (d,u) = PQ.pop()
    if u visited: continue
    mark u visited
    for each (v, w) in adj[u]:
        if d + w < dist[v]:
            dist[v] = d + w; prev[v] = u
            PQ.push((dist[v], v))
```

Two route objectives:

* **distance** — minimise total pipeline length (metres).
* **loss** — minimise the *summed* water-loss percentage (a fast heuristic
  proxy — non-negative, so Dijkstra is valid).

**Water-loss model (documented):** physical survival over a route is
multiplicative: `surviving = ∏ (1 − pᵢ/100)`. The **true** cumulative loss is
`100 × (1 − surviving)`. Because Dijkstra requires *additive* weights, the
`loss` objective minimises the *sum* of the percentages, which is **not**
equivalent to minimising the true physical loss. The UI reports both numbers so
the user sees the real loss rather than the proxy.

*If no route exists, a friendly "no route" message is shown.*

### 6.3 Greedy Irrigation Scheduling

```
score(f) = priority * 1_000_000 + urgency_score      // higher first
sort crop fields by score descending, tie-break: lower requirement
remaining = available_water
for each field f:
    if remaining >= f.requirement:    fully serve; remaining -= requirement
    elif remaining > 0:               partially serve remaining; remaining = 0
    else:                             f must wait
```

> This is a **simplified heuristic**, not a guaranteed globally optimal
> schedule. A full linear-programming / knapsack model could do better for some
> demand patterns.

---

## 7. Time & Space Complexity

| Algorithm | Time | Space |
|-----------|------|-------|
| Kruskal (DSU) | **O(E log E)** — dominated by sorting the edges | O(V + E) |
| Dijkstra (adjacency + binary heap) | **O((V + E) log V)** | O(V + E) |
| Greedy scheduling | **O(F log F)** — dominated by sorting fields | O(F) |

**Theoretical complexity** (the formulas above) describes *asymptotic growth*.
The **Performance Analysis** page shows *measured* wall-clock times, which are
machine-dependent and must be read as complementary evidence, not a replacement
for the theory.

---

## 8. Demonstration Network

The sample data (`sample_data.py` / "Load Demo") provides a connected network
with one cycle:

* 1 water source — `S` (Main Reservoir)
* 1 pump — `P1` (Pump Station 1)
* 1 junction — `J1` (Junction Box A)
* 6 crop fields — `F1`…`F6`
* 11 pipelines with varied length / cost / loss / capacity

Cycles present so Kruskal rejects edges:
`P1–J1–F3–P1`, `J1–F3–F4–J1`, `J1–F4–F5–J1`.

---

## 9. Sample Input / Output

**MST (weight = length)** on the demo network (9 nodes, 11 edges):

```
Selected edges : 8      ( = 9 - 1  -> a spanning Tree)
Total length   : 630 m  (original 995 m -> 36.68% savings)
Rejected cycles: 3
Connected      : Yes
```

**Dijkstra (S → F6, distance):**

```
Path   : S -> P1 -> J1 -> F6
Length : 365 m
Loss % : 6.37  (true multiplicative)   proxy(summed) = 6.5
Cost   : ₹18,400
Min capacity : 170 L/min
```

**Greedy Schedule (available water = 3500 L, required = 7500 L):**

```
Fully served : Soybean Field (800 L), Corn Field 1 (1500 L), Corn Field 2 (1100 L)
Partial      : Wheat Field 1 (100 / 1200 L)
Waiting      : Wheat Field 2, Rice Field
Allocated    : 3500 / 3500 L   (never exceeds the supply)
```

---

## 10. Testing

Unit tests live in `tests/` and run with **pytest**:

```powershell
python -m pytest tests -v
```

Covered cases:

* **MST correctness** (triangle & cycle graphs)
* **Disconnected graphs** (minimum spanning forest)
* **Shortest path correctness** and detour selection
* **Unreachable destinations**
* **Invalid weights / objectives** (negative weight, bogus objective)
* **Scheduling** within/against the water limit, partial & no-supply cases
* **Empty graphs** and **single-node graphs**

```
============================= 29 passed in 1.88s ==============================
```

---

## 11. Limitations & Future Scope

* Kruskal chooses a single global weight; a multi-objective optimisation
  (length + cost + loss) would be more realistic.
* Dijkstra on the `loss` objective minimises a summed proxy, not the true
  multiplicative physical loss.
* Greedy scheduling is a heuristic, not a guaranteed optimum.
* Future work: max-flow analysis, time-varying demands, interactive node
  repositioning on the canvas, and a comparison with Prim's algorithm.

---

## 12. DAA Viva Preparation

**Q: Why does Kruskal need to sort edges?**
A: Sorting lets the algorithm always consider the cheapest remaining edge, which
the *cut property* proves is a safe greedy choice for an MST.

**Q: What are path compression and union by rank?**
A: Both keep the Union-Find tree shallow. Union by rank hangs the shorter tree
under the taller root; path compression flattens the search path on `find`.
Together they give near-O(1) amortized lookups so the DSU never dominates Kruskal.

**Q: When does Dijkstra fail?**
A: With negative edge weights, because a "finalised" distance can later be
reduced by a negative edge. Water-loss percentages are always non-negative, so
Dijkstra is valid here.

**Q: Difference between a spanning tree and a spanning forest?**
A: A spanning tree of a connected graph has V−1 edges and one component. A
spanning forest of a graph with C connected components has V−C edges (one tree
per component).

**Q: What is the complexity of Kruskal?**
A: O(E log E) time — sorting dominates — and O(V + E) space for the DSU and
adjacency structure.

**Q: Why does Dijkstra use a priority queue?**
A: The priority queue always expands the currently cheapest tentative path,
which is the greedy choice the algorithm relies on; without it the algorithm
would degrade to linear scanning each iteration.

---

## 13. Quick Start (one-liner for Windows)

```powershell
python -m venv venv; .\venv\Scripts\activate; pip install -r requirements.txt; python app.py; # then open http://127.0.0.1:5000
```
