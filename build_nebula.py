"""
Build Consensus dataset from 6 movie data sources.

Joins MovieLens 32M, IMDb, Rotten Tomatoes (2 datasets), and Letterboxd (2 datasets)
on IMDb ID. Normalizes ratings to 0-100, computes consensus/polarization metrics,
runs UMAP for 2D layout, and exports JSON for the frontend visualization.

Output: consensus_data.json (~5-10 MB)
"""

import csv
import gzip
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA = Path('/home/coolhand/html/datavis/data_trove/entertainment/movies')
OUT = Path(__file__).parent / 'consensus_data.json'

IMDB_BASICS  = DATA / 'imdb' / 'title.basics.tsv.gz'
IMDB_RATINGS = DATA / 'imdb' / 'title.ratings.tsv.gz'
ML_MOVIES    = DATA / 'ml-32m' / 'movies.csv'
ML_LINKS     = DATA / 'ml-32m' / 'links.csv'
ML_RATINGS   = DATA / 'ml-32m' / 'ratings.csv'
RT_MOVIES    = DATA / 'rotten_tomatoes' / 'rotten_tomatoes_movies.csv'
LB_MOVIES    = DATA / 'letterboxd' / 'movie_data.csv'

# ---------------------------------------------------------------------------
# 1. Load IMDb (base table)
# ---------------------------------------------------------------------------
def load_imdb():
    print("Loading IMDb basics...", flush=True)
    basics = pd.read_csv(IMDB_BASICS, sep='\t', na_values='\\N',
                         usecols=['tconst', 'titleType', 'primaryTitle', 'startYear', 'genres', 'runtimeMinutes'],
                         dtype={'tconst': str, 'titleType': str, 'primaryTitle': str,
                                'startYear': str, 'genres': str})
    # Filter to movies only
    basics = basics[basics['titleType'].isin(['movie', 'tvMovie'])].copy()
    basics['year'] = pd.to_numeric(basics['startYear'], errors='coerce')
    basics = basics[basics['year'].notna()].copy()
    basics['year'] = basics['year'].astype(int)
    basics = basics[basics['year'] >= 1920].copy()
    basics.rename(columns={'primaryTitle': 'title'}, inplace=True)

    print(f"  {len(basics):,} movies after filtering", flush=True)

    print("Loading IMDb ratings...", flush=True)
    ratings = pd.read_csv(IMDB_RATINGS, sep='\t',
                          usecols=['tconst', 'averageRating', 'numVotes'],
                          dtype={'tconst': str})

    df = basics.merge(ratings, on='tconst', how='inner')
    print(f"  {len(df):,} movies with ratings", flush=True)
    return df[['tconst', 'title', 'year', 'genres', 'averageRating', 'numVotes', 'runtimeMinutes']]


# ---------------------------------------------------------------------------
# 2. Load MovieLens
# ---------------------------------------------------------------------------
def load_movielens():
    print("Loading MovieLens links...", flush=True)
    links = pd.read_csv(ML_LINKS, dtype={'movieId': int, 'imdbId': str, 'tmdbId': str})
    # Convert imdbId to tconst format
    links['tconst'] = 'tt' + links['imdbId'].str.zfill(7)

    print("Computing MovieLens aggregates...", flush=True)
    # Compute per-movie average from the 32M ratings file
    chunks = pd.read_csv(ML_RATINGS, usecols=['movieId', 'rating'],
                         dtype={'movieId': int, 'rating': float},
                         chunksize=5_000_000)
    sums = {}
    counts = {}
    for i, chunk in enumerate(chunks):
        print(f"  chunk {i+1}...", end=' ', flush=True)
        grouped = chunk.groupby('movieId')['rating']
        for mid, s in grouped.sum().items():
            sums[mid] = sums.get(mid, 0) + s
        for mid, c in grouped.count().items():
            counts[mid] = counts.get(mid, 0) + c
    print(flush=True)

    ml_agg = pd.DataFrame({
        'movieId': list(sums.keys()),
        'ml_avg': [sums[k] / counts[k] for k in sums],
        'ml_ratings': [counts[k] for k in sums]
    })

    ml = links[['movieId', 'tconst']].merge(ml_agg, on='movieId', how='inner')
    print(f"  {len(ml):,} MovieLens movies with tconst", flush=True)
    return ml[['tconst', 'ml_avg', 'ml_ratings']]


# ---------------------------------------------------------------------------
# 3. Load Rotten Tomatoes (fuzzy match by title+year)
# ---------------------------------------------------------------------------
def load_rotten_tomatoes():
    print("Loading Rotten Tomatoes...", flush=True)
    rt = pd.read_csv(RT_MOVIES, usecols=['title', 'audienceScore', 'tomatoMeter',
                                          'releaseDateTheaters', 'genre'],
                     dtype={'title': str, 'tomatoMeter': str, 'audienceScore': str})
    rt['tomatoMeter'] = pd.to_numeric(rt['tomatoMeter'], errors='coerce')
    rt['audienceScore'] = pd.to_numeric(rt['audienceScore'], errors='coerce')

    # Extract year from release date
    rt['year'] = rt['releaseDateTheaters'].str[:4]
    rt['year'] = pd.to_numeric(rt['year'], errors='coerce')
    rt = rt[rt['year'].notna()].copy()
    rt['year'] = rt['year'].astype(int)

    # Keep only rows with at least one score
    rt = rt[rt['tomatoMeter'].notna() | rt['audienceScore'].notna()].copy()

    # Create normalized title for matching
    rt['title_norm'] = rt['title'].str.lower().str.strip()
    rt['title_norm'] = rt['title_norm'].str.replace(r'[^\w\s]', '', regex=True)

    print(f"  {len(rt):,} RT movies with scores", flush=True)
    return rt[['title_norm', 'year', 'tomatoMeter', 'audienceScore']]


# ---------------------------------------------------------------------------
# 4. Load Letterboxd
# ---------------------------------------------------------------------------
def load_letterboxd():
    print("Loading Letterboxd...", flush=True)
    lb = pd.read_csv(LB_MOVIES,
                     usecols=['imdb_id', 'imdb_link', 'vote_average', 'vote_count', 'movie_title',
                              'year_released', 'genres'],
                     dtype={'imdb_id': str, 'imdb_link': str, 'movie_title': str},
                     on_bad_lines='skip',
                     engine='python')

    # Extract IMDb ID — try imdb_id column first, fall back to imdb_link URL
    lb['tconst'] = lb['imdb_id'].where(lb['imdb_id'].str.startswith('tt', na=False))
    mask = lb['tconst'].isna() & lb['imdb_link'].notna()
    lb.loc[mask, 'tconst'] = lb.loc[mask, 'imdb_link'].str.extract(r'(tt\d{7,8})', expand=False)
    lb = lb[lb['tconst'].notna()].copy()

    lb.rename(columns={'vote_average': 'lb_avg', 'vote_count': 'lb_ratings'}, inplace=True)
    lb = lb[lb['lb_avg'] > 0].copy()  # Remove unrated

    print(f"  {len(lb):,} Letterboxd movies with tconst", flush=True)
    return lb[['tconst', 'lb_avg', 'lb_ratings']]


# ---------------------------------------------------------------------------
# 5. Join everything
# ---------------------------------------------------------------------------
def merge_all(imdb, ml, lb, rt):
    print("\nMerging datasets...", flush=True)

    # IMDb is the base
    df = imdb.copy()

    # Join MovieLens on tconst
    df = df.merge(ml, on='tconst', how='left')
    print(f"  After ML join: {df['ml_avg'].notna().sum():,} have MovieLens", flush=True)

    # Join Letterboxd on tconst
    df = df.merge(lb, on='tconst', how='left')
    print(f"  After LB join: {df['lb_avg'].notna().sum():,} have Letterboxd", flush=True)

    # Join RT via fuzzy title+year match
    df['title_norm'] = df['title'].str.lower().str.strip()
    df['title_norm'] = df['title_norm'].str.replace(r'[^\w\s]', '', regex=True)
    df = df.merge(rt, on=['title_norm', 'year'], how='left')
    print(f"  After RT join: {df['tomatoMeter'].notna().sum():,} have RT tomatometer", flush=True)

    # Drop title_norm helper
    df.drop(columns=['title_norm'], inplace=True)

    return df


# ---------------------------------------------------------------------------
# 6. Normalize ratings & compute metrics
# ---------------------------------------------------------------------------
def compute_metrics(df):
    print("\nNormalizing ratings...", flush=True)

    # Normalize all to 0-100
    df['imdb_norm'] = (df['averageRating'] - 1) * (100 / 9)         # 1-10 → 0-100
    df['ml_norm'] = (df['ml_avg'] - 0.5) * (100 / 4.5)              # 0.5-5 → 0-100
    df['rt_critic_norm'] = df['tomatoMeter']                         # already 0-100
    df['rt_audience_norm'] = df['audienceScore']                      # already 0-100
    df['lb_norm'] = df['lb_avg'] * 10                                # 0-10 → 0-100

    # Count how many platforms each film has
    norm_cols = ['imdb_norm', 'ml_norm', 'rt_critic_norm', 'lb_norm']
    df['platform_count'] = df[norm_cols].notna().sum(axis=1)

    # Filter: need at least 2 platforms
    before = len(df)
    df = df[df['platform_count'] >= 2].copy()
    print(f"  {before:,} → {len(df):,} films with ≥2 platforms", flush=True)

    # Consensus: weighted average of normalized scores
    def weighted_consensus(row):
        scores = []
        weights = []
        for norm_col, vote_col in [('imdb_norm', 'numVotes'),
                                    ('ml_norm', 'ml_ratings'),
                                    ('rt_critic_norm', 'numVotes'),  # use imdb votes as proxy
                                    ('lb_norm', 'lb_ratings')]:
            if pd.notna(row[norm_col]):
                w = row.get(vote_col, 1)
                if pd.isna(w):
                    w = 1
                scores.append(row[norm_col])
                weights.append(max(w, 1))
        if not scores:
            return np.nan
        return np.average(scores, weights=weights)

    print("  Computing consensus scores...", flush=True)
    df['consensus'] = df.apply(weighted_consensus, axis=1)

    # Polarization: stddev of normalized scores (higher = more disagreement)
    print("  Computing polarization...", flush=True)
    df['polarization'] = df[norm_cols].std(axis=1)
    # Scale to 0-100
    p_max = df['polarization'].quantile(0.99)
    df['polarization'] = (df['polarization'] / p_max * 100).clip(0, 100)

    # Critic vs crowd gap (RT specific)
    df['critic_gap'] = df['tomatoMeter'] - df['audienceScore']

    # Total review count
    vote_cols = ['numVotes', 'ml_ratings', 'lb_ratings']
    df['total_reviews'] = df[vote_cols].fillna(0).sum(axis=1)

    # Radius: sqrt scale, 2-20px
    df['radius'] = np.sqrt(df['total_reviews'])
    r_min, r_max = df['radius'].min(), df['radius'].quantile(0.99)
    df['radius_px'] = 2 + (df['radius'] - r_min) / (r_max - r_min) * 18
    df['radius_px'] = df['radius_px'].clip(2, 20)

    return df


# ---------------------------------------------------------------------------
# 7. UMAP embedding
# ---------------------------------------------------------------------------
def compute_layout(df):
    """Position films using consensus (X) and polarization (Y) with jitter to reduce overlap."""
    print("\nComputing layout...", flush=True)

    # X = consensus (0-100 → 50-950 with padding)
    # Y = polarization (0-100 → 50-950 with padding)
    # Add small random jitter to prevent exact overlaps
    rng = np.random.default_rng(42)
    jitter_x = rng.normal(0, 8, len(df))
    jitter_y = rng.normal(0, 8, len(df))

    df['x'] = (df['consensus'].fillna(50) * 9 + 50 + jitter_x).clip(10, 990)
    df['y'] = (df['polarization'].fillna(0) * 9 + 50 + jitter_y).clip(10, 990)

    print(f"  Layout computed for {len(df):,} films", flush=True)
    print(f"  X range: {df['x'].min():.0f} - {df['x'].max():.0f}", flush=True)
    print(f"  Y range: {df['y'].min():.0f} - {df['y'].max():.0f}", flush=True)
    return df


# ---------------------------------------------------------------------------
# 8. Export JSON
# ---------------------------------------------------------------------------
def export_json(df):
    print(f"\nExporting {len(df):,} films to {OUT}...", flush=True)

    # Extract primary genre
    def first_genre(g):
        if pd.isna(g):
            return 'Unknown'
        parts = re.split(r'[|,]', str(g))
        return parts[0].strip() if parts else 'Unknown'

    df['genre'] = df['genres'].apply(first_genre)

    # Build compact output
    # Use packed arrays for size efficiency (same pattern as steam-network)
    genres_list = sorted(df['genre'].unique().tolist())
    genre_idx = {g: i for i, g in enumerate(genres_list)}

    records = []
    for _, r in df.iterrows():
        records.append([
            r['title'],                                          # [0] title
            int(r['year']),                                      # [1] year
            round(r['x'], 1),                                    # [2] x
            round(r['y'], 1),                                    # [3] y
            round(r['radius_px'], 1),                            # [4] radius
            round(r['consensus'], 1) if pd.notna(r['consensus']) else None,  # [5] consensus
            round(r['polarization'], 1),                         # [6] polarization
            round(r['imdb_norm'], 1) if pd.notna(r['imdb_norm']) else None,  # [7] imdb
            round(r['ml_norm'], 1) if pd.notna(r['ml_norm']) else None,      # [8] ml
            round(r['rt_critic_norm'], 1) if pd.notna(r['rt_critic_norm']) else None,  # [9] rt_critic
            round(r['rt_audience_norm'], 1) if pd.notna(r['rt_audience_norm']) else None,  # [10] rt_audience
            round(r['lb_norm'], 1) if pd.notna(r['lb_norm']) else None,      # [11] letterboxd
            int(r['total_reviews']),                              # [12] total_reviews
            genre_idx.get(r['genre'], 0),                         # [13] genre_idx
            int(r['platform_count']),                             # [14] platform_count
            round(r['critic_gap'], 1) if pd.notna(r['critic_gap']) else None,  # [15] critic_gap
        ])

    output = {
        'genres': genres_list,
        'films': records,
        'meta': {
            'count': len(records),
            'generated': time.strftime('%Y-%m-%d %H:%M'),
            'sources': ['IMDb', 'MovieLens 32M', 'Rotten Tomatoes', 'Letterboxd'],
        }
    }

    with open(OUT, 'w') as f:
        json.dump(output, f, separators=(',', ':'))

    size_mb = OUT.stat().st_size / 1024 / 1024
    print(f"  Written {size_mb:.1f} MB", flush=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    t0 = time.time()
    print("=" * 60)
    print("CONSENSUS — Data Pipeline")
    print("=" * 60)

    imdb = load_imdb()
    ml = load_movielens()
    lb = load_letterboxd()
    rt = load_rotten_tomatoes()

    df = merge_all(imdb, ml, lb, rt)
    df = compute_metrics(df)
    df = compute_layout(df)
    export_json(df)

    print(f"\nDone in {time.time() - t0:.0f}s")
    print(f"Films exported: {len(df):,}")


if __name__ == '__main__':
    main()
