# Repository Guidelines

## Project Structure & Module Organization
- `index.html`: single-page visualization app (UI, styles, rendering logic, and keyboard controls).
- `build_nebula.py`: offline pipeline that joins movie datasets and regenerates `consensus_data.json`.
- `consensus_data.json`: generated packed data consumed by the frontend (`fetch('consensus_data.json?'+_v)`).
- `../steam/`: sibling visualization project with similar static D3/Canvas patterns; use it as a reference when splitting modules or tuning performance.

## Build, Test, and Development Commands
- `python3 -m http.server 8000` - serve this directory locally at `http://localhost:8000`.
- `python3 -m pip install pandas numpy` - install data-pipeline dependencies.
- `python3 build_nebula.py` - rebuild the dataset from local sources in `/home/coolhand/html/datavis/data_trove/entertainment/movies`.
- `python3 -m json.tool consensus_data.json >/dev/null` - validate generated JSON after rebuilds.

## Coding Style & Naming Conventions
- Use 4-space indentation in both JavaScript and Python.
- JavaScript: vanilla style, `camelCase` for functions/variables, and semicolon-terminated statements.
- Python: follow PEP 8 and `snake_case`; keep pipeline stages in focused functions (`load_*`, `compute_*`, `export_*`).
- Keep the packed film array schema stable (`[0] title ... [15] critic_gap`) unless frontend decoding is updated in the same change.

## Testing Guidelines
- No formal automated suite exists yet; use repeatable smoke testing.
- Minimum PR checks:
  1. Page loads with no console errors.
  2. All four views switch correctly (`N`, `D`, `T`, `C`, plus arrow keys).
  3. Search, hover/pin info panel, and genre filters behave correctly.
  4. Rebuilt data renders and includes updated `meta.count`/`meta.generated`.

## Commit & Pull Request Guidelines
- This repo currently has no commit history; use the nearby `../steam` pattern: `feat:`, `fix:`, `chore:` with concise imperative subjects.
- Avoid vague merge-ready commit messages like `checkpoint`.
- PRs should include: objective, key file changes, data/schema impact, verification commands, and screenshots or GIFs for UI changes.
