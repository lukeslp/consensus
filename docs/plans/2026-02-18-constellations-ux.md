# Constellations Rebuild + UX Compaction

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the broken parallel-coordinates Constellations view with a platform scatter (individual dots + genre-cluster toggle), and compact the bottom dock by replacing genre pills with a dropdown and color pills with a `<select>`.

**Architecture:** All changes are in the single file `index.html`. No build step. Two completely independent feature areas — do them in order (Constellations first, UX second) with a commit after each task.

**Tech Stack:** Vanilla JS, D3.js v7, HTML5 Canvas, CSS custom properties.

---

## Task 1: New state variables + platform select HTML

**Files:**
- Modify: `index.html:1024–1050` (state block)
- Modify: `index.html:993–1015` (dock HTML)

**Step 1: Add state variables**

Inside the state block (after line `let activeView = 'nebula';`, around line 1041), add:

```js
let constXAxis = 'imdb';      // platform shown on X axis in Constellations
let constYAxis = 'lb';        // platform shown on Y axis in Constellations
let showGenreClusters = false; // toggle aggregate genre bubbles overlay
let constTransform = d3.zoomIdentity; // zoom state for constellations view
```

**Step 2: Add HTML to the dock**

Inside `.ctrl-views` div (after the 4 view-tab buttons, before the closing `</div>`), add:

```html
<!-- Platform axis selects — only visible in Constellations view -->
<div class="ctrl-sep const-only" id="constAxisSep"></div>
<div class="ctrl-const-axes const-only" id="constAxes">
    <select id="constX" aria-label="X axis platform" class="axis-select">
        <option value="imdb" selected>IMDb</option>
        <option value="ml">MovieLens</option>
        <option value="rt_critic">RT Critics</option>
        <option value="rt_audience">RT Audience</option>
        <option value="lb">Letterboxd</option>
    </select>
    <span class="axis-vs">vs</span>
    <select id="constY" aria-label="Y axis platform" class="axis-select">
        <option value="imdb">IMDb</option>
        <option value="ml">MovieLens</option>
        <option value="rt_critic">RT Critics</option>
        <option value="rt_audience">RT Audience</option>
        <option value="lb" selected>Letterboxd</option>
    </select>
</div>
<div class="ctrl-sep const-only"></div>
<button type="button" class="clusters-btn const-only" id="clustersBtn" aria-pressed="false">Clusters</button>
```

**Step 3: Manual test**

Open `http://localhost:8000/`. The selects and Clusters button should not be visible yet (they'll be shown only in Constellations view in Task 4). No JS errors in console.

**Step 4: Commit**

```bash
git add index.html
git commit -m "feat: add constellation state + axis select HTML"
```

---

## Task 2: CSS for new elements

**Files:**
- Modify: `index.html` — inside `<style>` block, after `.ctrl-sep` rules (around line 283)

**Step 1: Add styles**

Find `.ctrl-views {` (line ~283) and after that block's closing brace, add:

```css
/* Constellations-only controls */
.const-only { display: none !important; }

.axis-select {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 4px;
    color: rgba(255,255,255,0.5);
    font-size: 0.6rem;
    font-family: inherit;
    padding: 2px 4px;
    cursor: pointer;
    outline: none;
    appearance: none;
    -webkit-appearance: none;
}
.axis-select:focus-visible {
    outline: 2px solid rgba(212,192,255,0.9);
    outline-offset: 2px;
}
.axis-select option { background: #111; }

.axis-vs {
    font-size: 0.55rem;
    color: rgba(255,255,255,0.2);
    padding: 0 2px;
}

.ctrl-const-axes {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 0 4px;
    height: 100%;
}

.clusters-btn {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 4px;
    padding: 3px 9px;
    font-size: 0.6rem;
    color: rgba(255,255,255,0.3);
    cursor: pointer;
    font-family: inherit;
    transition: all 0.2s;
    white-space: nowrap;
}
.clusters-btn:hover { color: rgba(255,255,255,0.5); background: rgba(255,255,255,0.05); }
.clusters-btn.active {
    background: rgba(180,140,255,0.12);
    border-color: rgba(180,140,255,0.25);
    color: rgba(220,200,255,0.85);
}
```

**Step 2: Manual test**

No visual change expected. No console errors.

**Step 3: Commit**

```bash
git add index.html
git commit -m "feat: CSS for constellation axis selects and clusters toggle"
```

---

## Task 3: Rewrite `renderConstellations()`

**Files:**
- Modify: `index.html:1988–2052` (replace the entire function)

**Step 1: Replace the function**

Delete lines 1988–2052 (old `renderConstellations`) and replace with:

```js
// ── CONSTELLATIONS VIEW ──
const PLATFORM_LABELS = {
    imdb: 'IMDb', ml: 'MovieLens',
    rt_critic: 'RT Critics', rt_audience: 'RT Audience', lb: 'Letterboxd'
};

function renderConstellations() {
    ctx.save();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = '#050505';
    ctx.fillRect(0, 0, W, H);

    const k = constTransform.k;
    const tx = constTransform.x;
    const ty = constTransform.y;

    const margin = 72;
    const plotW = W - margin * 2;
    const plotH = H - margin * 2;

    function toScreen(xScore, yScore) {
        const sx = margin + (xScore / 100) * plotW;
        const sy = margin + (1 - yScore / 100) * plotH;
        return [sx * k + tx, sy * k + ty];
    }

    // Agreement diagonal
    ctx.strokeStyle = 'rgba(255,255,255,0.05)';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 6]);
    const [dx0, dy0] = toScreen(0, 0);
    const [dx1, dy1] = toScreen(100, 100);
    ctx.beginPath();
    ctx.moveTo(dx0, dy0);
    ctx.lineTo(dx1, dy1);
    ctx.stroke();
    ctx.setLineDash([]);

    // Quadrant labels
    const xLabel = PLATFORM_LABELS[constXAxis];
    const yLabel = PLATFORM_LABELS[constYAxis];
    ctx.font = '10px Inter, sans-serif';
    ctx.fillStyle = 'rgba(255,255,255,0.06)';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const [tlx, tly] = toScreen(15, 85);
    const [trx, try_] = toScreen(85, 85);
    const [blx, bly] = toScreen(15, 15);
    const [brx, bry] = toScreen(85, 15);
    ctx.fillText(`Low ${xLabel} / High ${yLabel}`, tlx, tly);
    ctx.fillText(`High ${xLabel} / High ${yLabel}`, trx, try_);
    ctx.fillText(`Low ${xLabel} / Low ${yLabel}`, blx, bly);
    ctx.fillText(`High ${xLabel} / Low ${yLabel}`, brx, bry);

    // Individual film dots
    const genreCentroids = {}; // collect for cluster layer

    for (const film of visibleFilms) {
        const xScore = film[constXAxis];
        const yScore = film[constYAxis];
        if (xScore == null || yScore == null) continue;

        const [sx, sy] = toScreen(xScore, yScore);
        const sr = Math.max(Math.sqrt(film.reviews) * 0.018 * k, 0.7);

        // store screen coords for hit detection
        film.sx = sx; film.sy = sy; film.sr = sr;

        const isHighlighted = film === hoveredFilm || film === pinnedFilm;
        const alpha = isHighlighted ? 1 : (hoveredFilm || pinnedFilm ? 0.15 : 0.55);
        const color = GENRE_COLORS[film.genreIdx % GENRE_COLORS.length];
        const c = d3.color(color);
        if (c) { c.opacity = alpha; ctx.fillStyle = c.formatRgb(); }
        else { ctx.fillStyle = color; }

        ctx.beginPath();
        ctx.arc(sx, sy, Math.max(sr, 0.5), 0, Math.PI * 2);
        ctx.fill();

        if (isHighlighted) {
            ctx.strokeStyle = 'rgba(255,255,255,0.6)';
            ctx.lineWidth = 1.5;
            ctx.stroke();
        }

        // accumulate centroids
        if (!genreCentroids[film.genre]) genreCentroids[film.genre] = { sx: 0, sy: 0, n: 0, genreIdx: film.genreIdx };
        genreCentroids[film.genre].sx += sx;
        genreCentroids[film.genre].sy += sy;
        genreCentroids[film.genre].n++;
    }

    // Genre cluster overlay
    if (showGenreClusters) {
        for (const [genre, c] of Object.entries(genreCentroids)) {
            const cx = c.sx / c.n;
            const cy = c.sy / c.n;
            const br = Math.max(Math.sqrt(c.n) * 1.8, 14) * Math.min(k, 1.5);
            const color = GENRE_COLORS[c.genreIdx % GENRE_COLORS.length];
            const dc = d3.color(color);

            // bubble
            if (dc) { dc.opacity = 0.12; ctx.fillStyle = dc.formatRgb(); }
            ctx.beginPath();
            ctx.arc(cx, cy, br, 0, Math.PI * 2);
            ctx.fill();

            // ring
            if (dc) { dc.opacity = 0.3; ctx.strokeStyle = dc.formatRgb(); }
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.arc(cx, cy, br, 0, Math.PI * 2);
            ctx.stroke();

            // label
            ctx.font = `${Math.max(8, Math.min(11, br * 0.55))}px Inter, sans-serif`;
            ctx.fillStyle = 'rgba(255,255,255,0.55)';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(genre, cx, cy);

            // count
            ctx.font = '7px "JetBrains Mono", monospace';
            ctx.fillStyle = 'rgba(255,255,255,0.2)';
            ctx.fillText(c.n.toLocaleString(), cx, cy + Math.max(9, br * 0.55));
        }
    }

    ctx.restore();
    updateStatsBar();
}
```

**Step 2: Manual test**

Switch to Constellations view. Should see a scatter of colored dots (IMDb vs Letterboxd). Diagonal line visible. No console errors.

**Step 3: Commit**

```bash
git add index.html
git commit -m "feat: rewrite Constellations as platform scatter with genre cluster overlay"
```

---

## Task 4: Wire up Constellations controls in `switchView()` and event handlers

**Files:**
- Modify: `index.html:1658–1665` (`else if (view === 'constellations')` block in `switchView`)
- Modify: `index.html` — after `// ── View Tabs ──` (around line 2360), add event listeners

**Step 1: Update `switchView` for constellations**

Replace the existing `else if (view === 'constellations') {` block (~lines 1658–1665) with:

```js
} else if (view === 'constellations') {
    axisX.style.display = 'none';
    axisY.style.display = 'none';
    colorSection.style.display = 'none';
    legendSection.style.display = 'none';
    quickFilters.style.display = 'flex';
    genreFilters.style.display = 'flex';
    document.querySelectorAll('.const-only').forEach(el => el.style.setProperty('display', '', 'important'));
    constTransform = d3.zoomIdentity;
}
```

Also, in every other view's block (`nebula`, `divide`, `timeline`), add at the end of each block:

```js
document.querySelectorAll('.const-only').forEach(el => el.style.removeProperty('display'));
```

Wait — `.const-only` uses `display: none !important`. The `removeProperty` call removes the inline override added when entering constellations, so the CSS rule takes over and hides them again. That pattern works cleanly.

**Step 2: Wire axis selects + clusters toggle**

Find `// ── View Tabs ──` (around line 2360) and after the existing view tab event listener block, add:

```js
// ── Constellations controls ──
document.getElementById('constX').addEventListener('change', e => {
    constXAxis = e.target.value;
    scheduleRender();
});
document.getElementById('constY').addEventListener('change', e => {
    constYAxis = e.target.value;
    scheduleRender();
});
document.getElementById('clustersBtn').addEventListener('click', () => {
    showGenreClusters = !showGenreClusters;
    const btn = document.getElementById('clustersBtn');
    btn.classList.toggle('active', showGenreClusters);
    btn.setAttribute('aria-pressed', showGenreClusters ? 'true' : 'false');
    scheduleRender();
});
```

**Step 3: Wire zoom for constellations**

Find the zoom event handler (around line 2054). The existing zoom applies to `transform`. Add a branch so Constellations gets `constTransform`:

Find:
```js
.on('zoom', e => {
    if (activeView === 'nebula' || activeView === 'timeline') {
        transform = e.transform;
    } else if (activeView === 'divide') {
        divideTransform = e.transform;
    }
    scheduleRender();
    isInteracting = true;
})
```

Add `else if (activeView === 'constellations') { constTransform = e.transform; }` before `scheduleRender()`.

**Step 4: Hit detection for constellations**

The existing quadtree hit detection works off `film.sx/sy/sr` which `renderConstellations` now sets. But the quadtree is built from UMAP positions, not scatter positions. Need a simple linear scan fallback for constellations.

Find the hit detection function (`// ── Hit Detection ──`, around line 2073). The existing function uses quadtree for nebula. Add a branch:

```js
function hitFilm(mx, my) {
    if (activeView === 'constellations') {
        // linear scan on visible films (capped for performance)
        let best = null, bestDist = Infinity;
        const cap = Math.min(visibleFilms.length, 8000);
        for (let i = 0; i < cap; i++) {
            const f = visibleFilms[i]; // sorted by reviews, so top films first
            if (f.sx == null) continue;
            const dx = mx - f.sx, dy = my - f.sy;
            const dist = Math.sqrt(dx*dx + dy*dy);
            if (dist < Math.max(f.sr + 4, 6) && dist < bestDist) {
                best = f; bestDist = dist;
            }
        }
        return best;
    }
    // ... existing quadtree logic below
}
```

**Step 5: Manual test**

1. Switch to Constellations. Dots appear as scatter.
2. Change X axis dropdown to "RT Critics" — dots reposition.
3. Click "Clusters" — genre bubbles appear with labels and counts.
4. Hover a dot — info panel appears.
5. Zoom and pan work.
6. Switch to another view — axis selects disappear, zoom resets.

**Step 6: Commit**

```bash
git add index.html
git commit -m "feat: wire constellation zoom, axis selects, clusters toggle, hit detection"
```

---

## Task 5: Genre dropdown (replace genre-pill row)

**Files:**
- Modify: `index.html:996` (HTML — replace `.genre-row` div)
- Modify: `index.html` — CSS (replace `.genre-row`/`.genre-pill` block)
- Modify: `index.html:1448–1480` (replace `buildGenreFilters` function)

**Step 1: Replace HTML**

Replace:
```html
<div class="genre-row" id="genreFilters"></div>
```
With:
```html
<div class="genre-dropdown-wrap" id="genreWrap">
    <button type="button" class="genre-dropdown-btn" id="genreBtn" aria-haspopup="listbox" aria-expanded="false">
        Genre: All ▾
    </button>
    <div class="genre-dropdown-panel" id="genrePanel" role="listbox" aria-multiselectable="true" aria-label="Filter by genre"></div>
</div>
```

**Step 2: Replace CSS**

Remove the `.genre-row` and `.genre-pill` / `.genre-pill:hover` / `.genre-pill.active` rules. Replace with:

```css
.genre-dropdown-wrap {
    position: relative;
    margin-bottom: 6px;
}
.genre-dropdown-btn {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 12px;
    padding: 5px 13px;
    font-size: 0.62rem;
    color: rgba(255,255,255,0.4);
    cursor: pointer;
    font-family: inherit;
    transition: all 0.2s;
    white-space: nowrap;
}
.genre-dropdown-btn:hover { color: rgba(255,255,255,0.65); background: rgba(255,255,255,0.06); }
.genre-dropdown-btn.active {
    background: rgba(180,140,255,0.12);
    border-color: rgba(180,140,255,0.28);
    color: rgba(220,200,255,0.9);
}
.genre-dropdown-panel {
    display: none;
    position: absolute;
    bottom: calc(100% + 6px);
    left: 50%;
    transform: translateX(-50%);
    background: rgba(10,10,10,0.96);
    border: 1px solid rgba(255,255,255,0.09);
    border-radius: 8px;
    padding: 8px;
    display: none;
    flex-direction: column;
    gap: 2px;
    min-width: 180px;
    max-height: 260px;
    overflow-y: auto;
    backdrop-filter: blur(16px);
    z-index: 40;
}
.genre-dropdown-panel.open { display: flex; }
.genre-option {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 5px 9px;
    border-radius: 5px;
    cursor: pointer;
    font-size: 0.68rem;
    color: rgba(255,255,255,0.45);
    transition: background 0.12s;
    user-select: none;
}
.genre-option:hover { background: rgba(255,255,255,0.05); color: rgba(255,255,255,0.7); }
.genre-option.active {
    background: rgba(180,140,255,0.12);
    color: rgba(220,200,255,0.9);
}
.genre-option-count {
    font-size: 0.55rem;
    color: rgba(255,255,255,0.2);
    font-family: 'JetBrains Mono', monospace;
}
.genre-clear {
    margin-top: 4px;
    padding: 4px 9px;
    border-top: 1px solid rgba(255,255,255,0.05);
    font-size: 0.6rem;
    color: rgba(255,255,255,0.25);
    cursor: pointer;
    text-align: center;
    border-radius: 0 0 5px 5px;
}
.genre-clear:hover { color: rgba(255,255,255,0.5); }
```

**Step 3: Replace `buildGenreFilters`**

Replace the entire `buildGenreFilters` function (lines 1448–1480) with:

```js
// ── Genre Dropdown ──
function buildGenreFilters(genres) {
    const panel = document.getElementById('genrePanel');
    const btn = document.getElementById('genreBtn');
    const genreCounts = {};
    allFilms.forEach(f => { genreCounts[f.genre] = (genreCounts[f.genre] || 0) + 1; });
    const topGenres = Object.entries(genreCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 14)
        .map(d => d[0]);

    topGenres.forEach(g => {
        const row = document.createElement('div');
        row.className = 'genre-option';
        row.setAttribute('role', 'option');
        row.setAttribute('aria-selected', 'false');
        row.innerHTML = `<span>${g}</span><span class="genre-option-count">${genreCounts[g].toLocaleString()}</span>`;
        row.addEventListener('click', () => {
            if (activeGenres.has(g)) {
                activeGenres.delete(g);
                row.classList.remove('active');
                row.setAttribute('aria-selected', 'false');
            } else {
                activeGenres.add(g);
                row.classList.add('active');
                row.setAttribute('aria-selected', 'true');
            }
            updateGenreBtn();
            filterFilms();
            scheduleRender();
        });
        panel.appendChild(row);
    });

    // Clear all row
    const clear = document.createElement('div');
    clear.className = 'genre-clear';
    clear.textContent = 'Clear all';
    clear.addEventListener('click', () => {
        activeGenres.clear();
        panel.querySelectorAll('.genre-option').forEach(r => {
            r.classList.remove('active');
            r.setAttribute('aria-selected', 'false');
        });
        updateGenreBtn();
        filterFilms();
        scheduleRender();
    });
    panel.appendChild(clear);

    // Toggle panel
    btn.addEventListener('click', e => {
        e.stopPropagation();
        const open = panel.classList.toggle('open');
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
}

function updateGenreBtn() {
    const btn = document.getElementById('genreBtn');
    if (activeGenres.size === 0) {
        btn.textContent = 'Genre: All ▾';
        btn.classList.remove('active');
    } else {
        const label = activeGenres.size === 1 ? [...activeGenres][0] : `${activeGenres.size} genres`;
        btn.textContent = `Genre: ${label} ▾`;
        btn.classList.add('active');
    }
}
```

**Step 4: Update `switchView` references**

`switchView` currently does `genreFilters.style.display = 'flex'` and `genreFilters.style.display = 'none'`. Replace the `const genreFilters` line:

```js
const genreFilters = document.getElementById('genreWrap');
```

The same show/hide calls now apply to the dropdown wrapper. (The panel itself is hidden by default and opens/closes independently.)

**Step 5: Close panel on outside click**

Find `// ── Close panels on click outside ──` (around line 2433). Add:

```js
const gp = document.getElementById('genrePanel');
if (gp && !gp.contains(e.target) && !document.getElementById('genreBtn').contains(e.target)) {
    gp.classList.remove('open');
    document.getElementById('genreBtn').setAttribute('aria-expanded', 'false');
}
```

**Step 6: Manual test**

1. "Genre: All ▾" button visible in dock. Genre row is gone.
2. Click button — panel opens with genre list + film counts.
3. Select a genre — button updates label, films filter.
4. Select multiple — button shows "N genres".
5. "Clear all" resets.
6. Click outside — panel closes.

**Step 7: Commit**

```bash
git add index.html
git commit -m "feat: replace genre pills with compact dropdown panel"
```

---

## Task 6: Color mode `<select>` (replace color pills)

**Files:**
- Modify: `index.html:1005–1007` (HTML — `.ctrl-color` div)
- Modify: `index.html` — CSS (add color select styles, remove color-pill styles)
- Modify: `index.html:1482–1507` (replace `buildColorPills`)

**Step 1: Replace HTML**

Replace:
```html
<div class="ctrl-color">
    <div class="color-pills" id="colorPills"></div>
</div>
```
With:
```html
<div class="ctrl-color">
    <select id="colorSelect" class="color-select" aria-label="Color mode"></select>
</div>
```

**Step 2: Replace CSS**

Remove `.color-pills`, `.color-pill`, `.color-pill:hover`, `.color-pill.active` rule blocks. Replace with:

```css
.color-select {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 4px;
    color: rgba(255,255,255,0.5);
    font-size: 0.6rem;
    font-family: inherit;
    padding: 3px 6px;
    cursor: pointer;
    outline: none;
    appearance: none;
    -webkit-appearance: none;
    min-width: 90px;
}
.color-select:focus-visible {
    outline: 2px solid rgba(212,192,255,0.9);
    outline-offset: 2px;
}
.color-select option { background: #111; color: rgba(255,255,255,0.7); }
```

**Step 3: Replace `buildColorPills`**

Replace the entire `buildColorPills` function (lines 1482–1507) with:

```js
// ── Color Mode Select ──
function buildColorPills() {
    const sel = document.getElementById('colorSelect');
    const modes = ['consensus', 'polarization', 'platforms', 'genre'];
    modes.forEach(mode => {
        const opt = document.createElement('option');
        opt.value = mode;
        opt.textContent = COLORS[mode].label;
        if (mode === colorMode) opt.selected = true;
        sel.appendChild(opt);
    });
    sel.addEventListener('change', () => {
        colorMode = sel.value;
        updateLegendScale();
        scheduleRender();
    });
    updateLegendScale();
}
```

**Step 4: Update keyboard shortcut**

Find the keyboard handler for `1`–`4` color mode shortcuts (around line 2409). It currently calls `buildColorPills()` or sets active pill. Update it to also keep the select in sync:

After `colorMode = modes[idx];`, add:

```js
const sel = document.getElementById('colorSelect');
if (sel) sel.value = colorMode;
```

**Step 5: Manual test**

1. Color section shows a compact dropdown instead of 4 pills.
2. Changing it updates the visualization and legend.
3. Pressing `1`–`4` keyboard keys updates the select's displayed value.
4. The dock strip is noticeably narrower.

**Step 6: Commit**

```bash
git add index.html
git commit -m "feat: replace color mode pills with compact select"
```

---

## Task 7: Final QA pass

**Checks:**

1. All 4 views switch correctly — Nebula, The Divide, Timeline, Constellations.
2. Constellations: axis selects reposition dots, Clusters toggle shows/hides bubbles, genre filter works, zoom/pan works, hover/pin info panel works.
3. Genre dropdown: opens, multi-select, clear, updates filter, closes on outside click.
4. Color select: all 4 modes work, keyboard `1–4` stays in sync.
5. Quick filter pills still work (unchanged).
6. No console errors.
7. Mobile: dock fits in 2 rows (quick filters + controls strip).

**Commit:**

```bash
git add index.html docs/
git commit -m "chore: constellation + UX compaction complete"
git push
```
