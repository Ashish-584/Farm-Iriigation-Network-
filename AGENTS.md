# AGENTS.md

Project: Farm Irrigation Network Optimizer (Python + Flask)

## Commands to run in this project

| Action        | Command                                   |
|---------------|-------------------------------------------|
| Install deps  | `pip install -r requirements.txt`         |
| Run the app   | `python app.py` (then open http://127.0.0.1:5000) |
| Run tests     | `python -m pytest tests -v`               |
| Type check    | (not configured)                          |
| Lint          | (not configured)                          |

## Notes
- The project targets Python 3. The only non-stdlib dependency is Flask.
- Cytoscape.js and Chart.js are loaded from a CDN (no npm install needed).
- The Flask dev server auto-reloads source changes (debug mode).
- Tests must be run from the project root so `graph_model`/`kruskal` etc. import.
