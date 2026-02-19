# Consensus

140,000+ films mapped by where critics, cinephiles, and casual viewers agree — and where they violently disagree.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![JavaScript](https://img.shields.io/badge/JavaScript-vanilla-yellow.svg)](https://developer.mozilla.org/en-US/docs/Web/JavaScript)
[![D3.js](https://img.shields.io/badge/D3.js-v7-orange.svg)](https://d3js.org/)
[![Live](https://img.shields.io/badge/live-dr.eamer.dev-cyan.svg)](https://dr.eamer.dev/datavis/consensus/)

## What It Does

Pulls rating data from IMDb, MovieLens (32M ratings), Rotten Tomatoes, and Letterboxd, normalizes them to a common scale, runs UMAP to find natural clustering, then renders everything as a zoomable star field. Each dot is a film. Position, color, and size all carry meaning.

Four views:

- **Nebula** — the full cloud, colored by consensus score, polarization, source platform, or genre
- **The Divide** — films sorted by the gap between critic and audience scores
- **Timeline** — the same data laid out by decade
- **Constellations** — genre clusters, spatially separated

## Features

- Pan and zoom the canvas with mouse or touch
- Search 140K film titles with instant results
- Quick filters: most reviewed, award contenders, hidden gems, high consensus
- Genre pills for filtering by category
- Film detail panel on hover/click with all four platform scores
- Keyboard navigation: `N` `D` `T` `C` to switch views, arrows to cycle, `1–4` for color modes
- Fullscreen mode
- Fully responsive down to mobile

## Data Pipeline

The dataset comes from six source files joined on IMDb ID:

```
IMDb title basics + ratings
MovieLens 32M (movies.csv + links.csv + ratings.csv)
Rotten Tomatoes movies
Letterboxd movie data
```

To rebuild `consensus_data.json`:

```bash
pip install pandas numpy umap-learn
python3 build_nebula.py
```

Expects source files at `/home/coolhand/html/datavis/data_trove/entertainment/movies`. Output is `consensus_data.json` (~5–10 MB).

## Running Locally

No build step needed — it's a single HTML file plus the generated JSON:

```bash
python3 -m http.server 8000
# open http://localhost:8000/
```

## Live

[dr.eamer.dev/datavis/consensus/](https://dr.eamer.dev/datavis/consensus/)

## Stack

- Vanilla JavaScript + HTML5 Canvas
- D3.js v7 (scales and projections)
- Python (pandas, numpy, UMAP) for the data pipeline

## Author

**Luke Steuber**
- [dr.eamer.dev](https://dr.eamer.dev)
- Bluesky: [@lukesteuber.com](https://bsky.app/profile/lukesteuber.com)

## License

MIT
