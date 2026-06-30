/* ============================================================
   🎨 Pixel Art Maker — a kid-friendly Piskel-style editor

   Model
   -----
   • CANVAS  : the picture, a fixed size in real pixels (canvasW × canvasH).
               This is also the default saved-picture (export) size.
   • TILE    : how many real pixels make up one colorable block (8/16/32/64).
               "8-bit" = every 8 px is one tile. Bigger number = chunkier.
   • GRID    : the colorable squares = round(canvas / tile). DERIVED.
   • EXPORT  : the saved image size. Defaults to the canvas size, and only
               changes through the Save Picture menu or a query string —
               never by changing the tile size.
   ============================================================ */

(() => {
  "use strict";

  // ---------- Config ----------
  const PALETTE = [
    null,        // transparent (eraser color)
    "#000000", "#ffffff", "#9b9b9b", "#5a3921",
    "#ff4d6d", "#ff7b00", "#ffd000", "#9be800",
    "#19c37d", "#00c2d1", "#3b82f6", "#6c63ff",
    "#b14df0", "#ff8fc7", "#ffc9a8", "#7cf5d6",
  ];
  const TILES = [4, 8, 16, 32, 64];   // pixel-tile sizes (real px per drawing pixel)
  const MIN_PIXEL = 3;
  const MAX_PIXEL = 48;
  const MAX_GRID = 256;               // safety cap on colorable squares per side
  const DEFAULT_CANVAS = 512;
  const DEFAULT_TILE = 16;
  const DEFAULT_NAME = "my-art";

  // ---------- State ----------
  const state = {
    canvasW: DEFAULT_CANVAS,   // picture size in real pixels
    canvasH: DEFAULT_CANVAS,
    tile: DEFAULT_TILE,        // real pixels per colorable tile
    w: 32,                     // grid columns (derived = round(canvasW/tile))
    h: 32,                     // grid rows
    pixelSize: 16,             // on-screen size of one tile (display fit only)
    data: [],                  // flat array length w*h, hex string or null
    tool: "pencil",
    name: DEFAULT_NAME,        // sprite file name (editable title; used on export)
    color: "#ff4d6d",
    showGrid: true,
    exportW: null,             // saved-picture size (defaults to canvas size)
    exportH: null,
    undo: [],
    redo: [],
  };

  // ---------- Elements ----------
  const $ = (id) => document.getElementById(id);
  const welcome = $("welcome");
  const editor = $("editor");
  const canvas = $("canvas");
  const ctx = canvas.getContext("2d");
  const paletteEl = $("palette");
  const currentColorEl = $("currentColor");
  const colorInput = $("colorInput");

  // ============================================================
  //  Helpers
  // ============================================================
  function idx(x, y) { return y * state.w + x; }
  function inBounds(x, y) { return x >= 0 && y >= 0 && x < state.w && y < state.h; }
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
  function blankData(w, h) { return new Array(w * h).fill(null); }

  function gridFor(canvasW, canvasH, tile) {
    return {
      w: clamp(Math.max(1, Math.round(canvasW / tile)), 1, MAX_GRID),
      h: clamp(Math.max(1, Math.round(canvasH / tile)), 1, MAX_GRID),
    };
  }

  function fitPixelSize() {
    const area = document.querySelector(".canvas-area");
    const availW = (area ? area.clientWidth : 600) - 60;
    const availH = (area ? area.clientHeight : 600) - 80;
    const size = Math.floor(Math.min(availW / state.w, availH / state.h));
    return clamp(size, MIN_PIXEL, MAX_PIXEL);
  }

  // nearest-neighbour resample of the current grid into a new grid
  function resampleTo(newW, newH) {
    if (state.data.length !== state.w * state.h) return blankData(newW, newH);
    const next = blankData(newW, newH);
    for (let ny = 0; ny < newH; ny++) {
      for (let nx = 0; nx < newW; nx++) {
        const sx = Math.min(state.w - 1, Math.floor(nx * state.w / newW));
        const sy = Math.min(state.h - 1, Math.floor(ny * state.h / newH));
        next[ny * newW + nx] = state.data[sy * state.w + sx];
      }
    }
    return next;
  }

  // ============================================================
  //  Rendering
  // ============================================================
  function resizeCanvas() {
    canvas.width = state.w * state.pixelSize;
    canvas.height = state.h * state.pixelSize;
    render();
  }

  function drawChecker() {
    const ps = state.pixelSize;
    for (let y = 0; y < state.h; y++) {
      for (let x = 0; x < state.w; x++) {
        ctx.fillStyle = ((x + y) % 2 === 0) ? "#ffffff" : "#eef0f3";
        ctx.fillRect(x * ps, y * ps, ps, ps);
      }
    }
  }

  function render(preview) {
    const ps = state.pixelSize;
    drawChecker();

    for (let y = 0; y < state.h; y++) {
      for (let x = 0; x < state.w; x++) {
        const col = state.data[idx(x, y)];
        if (col) { ctx.fillStyle = col; ctx.fillRect(x * ps, y * ps, ps, ps); }
      }
    }

    if (preview) {
      for (const p of preview) {
        if (!inBounds(p.x, p.y)) continue;
        ctx.fillStyle = p.color === null
          ? (((p.x + p.y) % 2 === 0) ? "#ffffff" : "#eef0f3")
          : p.color;
        ctx.fillRect(p.x * ps, p.y * ps, ps, ps);
      }
    }

    if (state.showGrid && ps >= 6) {
      ctx.strokeStyle = "rgba(58,44,70,.10)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let x = 0; x <= state.w; x++) { ctx.moveTo(x * ps + .5, 0); ctx.lineTo(x * ps + .5, canvas.height); }
      for (let y = 0; y <= state.h; y++) { ctx.moveTo(0, y * ps + .5); ctx.lineTo(canvas.width, y * ps + .5); }
      ctx.stroke();
    }
  }

  // ============================================================
  //  History (undo / redo) — snapshots size + tile too
  // ============================================================
  function snapshot() {
    return {
      w: state.w, h: state.h, tile: state.tile,
      canvasW: state.canvasW, canvasH: state.canvasH,
      exportW: state.exportW, exportH: state.exportH,
      data: state.data.slice(),
    };
  }
  function restore(s) {
    state.w = s.w; state.h = s.h; state.tile = s.tile;
    state.canvasW = s.canvasW; state.canvasH = s.canvasH;
    state.exportW = s.exportW; state.exportH = s.exportH;
    state.data = s.data.slice();
    state.pixelSize = fitPixelSize();
    resizeCanvas();
    updateTileButtons();
    updateStatus();
  }
  function pushUndo() {
    state.undo.push(snapshot());
    if (state.undo.length > 60) state.undo.shift();
    state.redo.length = 0;
    updateHistoryButtons();
  }
  function undo() { if (state.undo.length) { state.redo.push(snapshot()); restore(state.undo.pop()); updateHistoryButtons(); } }
  function redo() { if (state.redo.length) { state.undo.push(snapshot()); restore(state.redo.pop()); updateHistoryButtons(); } }
  function updateHistoryButtons() {
    $("undoBtn").disabled = state.undo.length === 0;
    $("redoBtn").disabled = state.redo.length === 0;
  }

  // ============================================================
  //  Drawing primitives
  // ============================================================
  function setPixel(x, y, color) { if (inBounds(x, y)) state.data[idx(x, y)] = color; }

  function linePoints(x0, y0, x1, y1) {
    const pts = [];
    let dx = Math.abs(x1 - x0), dy = Math.abs(y1 - y0);
    let sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
    let err = dx - dy;
    while (true) {
      pts.push({ x: x0, y: y0 });
      if (x0 === x1 && y0 === y1) break;
      const e2 = 2 * err;
      if (e2 > -dy) { err -= dy; x0 += sx; }
      if (e2 < dx) { err += dx; y0 += sy; }
    }
    return pts;
  }
  function rectPoints(x0, y0, x1, y1) {
    const pts = [];
    const xa = Math.min(x0, x1), xb = Math.max(x0, x1);
    const ya = Math.min(y0, y1), yb = Math.max(y0, y1);
    for (let x = xa; x <= xb; x++) { pts.push({ x, y: ya }); pts.push({ x, y: yb }); }
    for (let y = ya; y <= yb; y++) { pts.push({ x: xa, y }); pts.push({ x: xb, y }); }
    return pts;
  }
  function ellipsePoints(x0, y0, x1, y1) {
    const xa = Math.min(x0, x1), xb = Math.max(x0, x1);
    const ya = Math.min(y0, y1), yb = Math.max(y0, y1);
    const rx = (xb - xa) / 2, ry = (yb - ya) / 2;
    const cx = (xa + xb) / 2, cy = (ya + yb) / 2;
    const pts = [];
    const steps = Math.max(24, Math.floor((rx + ry) * 4));
    for (let i = 0; i < steps; i++) {
      const t = (i / steps) * Math.PI * 2;
      pts.push({ x: Math.round(cx + rx * Math.cos(t)), y: Math.round(cy + ry * Math.sin(t)) });
    }
    return pts;
  }
  function floodFill(sx, sy, newColor) {
    const target = state.data[idx(sx, sy)];
    if (target === newColor) return;
    const stack = [[sx, sy]];
    while (stack.length) {
      const [x, y] = stack.pop();
      if (!inBounds(x, y)) continue;
      if (state.data[idx(x, y)] !== target) continue;
      state.data[idx(x, y)] = newColor;
      stack.push([x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]);
    }
  }

  // ============================================================
  //  Pointer interaction
  // ============================================================
  let drawing = false, startCell = null, lastCell = null;

  function cellFromEvent(e) {
    const rect = canvas.getBoundingClientRect();
    const x = Math.floor((e.clientX - rect.left) / (rect.width / state.w));
    const y = Math.floor((e.clientY - rect.top) / (rect.height / state.h));
    return { x: clamp(x, 0, state.w - 1), y: clamp(y, 0, state.h - 1) };
  }
  function paintColor() { return state.tool === "eraser" ? null : state.color; }

  function onDown(e) {
    e.preventDefault();
    const cell = cellFromEvent(e);
    const t = state.tool;
    if (t === "picker") {
      const col = state.data[idx(cell.x, cell.y)];
      if (col) selectColor(col);
      return;
    }
    drawing = true; startCell = cell; lastCell = cell; pushUndo();
    if (t === "pencil" || t === "eraser") { setPixel(cell.x, cell.y, paintColor()); render(); }
    else if (t === "mirror") { setPixel(cell.x, cell.y, paintColor()); setPixel(state.w - 1 - cell.x, cell.y, paintColor()); render(); }
    else if (t === "fill") { floodFill(cell.x, cell.y, paintColor()); render(); drawing = false; }
  }
  function onMove(e) {
    if (!drawing) return;
    e.preventDefault();
    const cell = cellFromEvent(e);
    const t = state.tool;
    if (t === "pencil" || t === "eraser") {
      for (const p of linePoints(lastCell.x, lastCell.y, cell.x, cell.y)) setPixel(p.x, p.y, paintColor());
      lastCell = cell; render();
    } else if (t === "mirror") {
      for (const p of linePoints(lastCell.x, lastCell.y, cell.x, cell.y)) {
        setPixel(p.x, p.y, paintColor());
        setPixel(state.w - 1 - p.x, p.y, paintColor());
      }
      lastCell = cell; render();
    } else if (t === "line") {
      render(linePoints(startCell.x, startCell.y, cell.x, cell.y).map(p => ({ ...p, color: paintColor() })));
    } else if (t === "rect") {
      render(rectPoints(startCell.x, startCell.y, cell.x, cell.y).map(p => ({ ...p, color: paintColor() })));
    } else if (t === "ellipse") {
      render(ellipsePoints(startCell.x, startCell.y, cell.x, cell.y).map(p => ({ ...p, color: paintColor() })));
    } else if (t === "move") {
      render(movedPreview(cell.x - startCell.x, cell.y - startCell.y));
    }
  }
  function onUp(e) {
    if (!drawing) return;
    const cell = cellFromEvent(e);
    const t = state.tool;
    if (t === "line") for (const p of linePoints(startCell.x, startCell.y, cell.x, cell.y)) setPixel(p.x, p.y, paintColor());
    else if (t === "rect") for (const p of rectPoints(startCell.x, startCell.y, cell.x, cell.y)) setPixel(p.x, p.y, paintColor());
    else if (t === "ellipse") for (const p of ellipsePoints(startCell.x, startCell.y, cell.x, cell.y)) setPixel(p.x, p.y, paintColor());
    else if (t === "move") commitMove(cell.x - startCell.x, cell.y - startCell.y);
    drawing = false; render();
  }

  function movedPreview(dx, dy) {
    const out = [];
    for (let y = 0; y < state.h; y++) for (let x = 0; x < state.w; x++) {
      const nx = ((x + dx) % state.w + state.w) % state.w;
      const ny = ((y + dy) % state.h + state.h) % state.h;
      out.push({ x: nx, y: ny, color: state.data[idx(x, y)] });
    }
    return out;
  }
  function commitMove(dx, dy) {
    const next = blankData(state.w, state.h);
    for (let y = 0; y < state.h; y++) for (let x = 0; x < state.w; x++) {
      const nx = ((x + dx) % state.w + state.w) % state.w;
      const ny = ((y + dy) % state.h + state.h) % state.h;
      next[idx(nx, ny)] = state.data[idx(x, y)];
    }
    state.data = next;
  }

  // ============================================================
  //  Transformations
  // ============================================================
  function flipH() {
    pushUndo();
    const next = blankData(state.w, state.h);
    for (let y = 0; y < state.h; y++) for (let x = 0; x < state.w; x++) next[idx(state.w - 1 - x, y)] = state.data[idx(x, y)];
    state.data = next; render();
  }
  function flipV() {
    pushUndo();
    const next = blankData(state.w, state.h);
    for (let y = 0; y < state.h; y++) for (let x = 0; x < state.w; x++) next[idx(x, state.h - 1 - y)] = state.data[idx(x, y)];
    state.data = next; render();
  }
  function rotate(dir) {
    pushUndo();
    const nw = state.h, nh = state.w;
    const next = new Array(nw * nh).fill(null);
    for (let y = 0; y < state.h; y++) for (let x = 0; x < state.w; x++) {
      let nx, ny;
      if (dir === "R") { nx = state.h - 1 - y; ny = x; } else { nx = y; ny = state.w - 1 - x; }
      next[ny * nw + nx] = state.data[idx(x, y)];
    }
    state.w = nw; state.h = nh; state.data = next;
    // rotating swaps the picture's width/height too
    let t = state.canvasW; state.canvasW = state.canvasH; state.canvasH = t;
    t = state.exportW; state.exportW = state.exportH; state.exportH = t;
    state.pixelSize = fitPixelSize();
    resizeCanvas();
    updateStatus();
  }
  function clearAll() { pushUndo(); state.data = blankData(state.w, state.h); render(); }

  // ============================================================
  //  Colors
  // ============================================================
  function buildPalette() {
    paletteEl.innerHTML = "";
    PALETTE.forEach((col) => {
      const s = document.createElement("button");
      s.className = "swatch" + (col === null ? " transparent" : "");
      if (col) s.style.background = col;
      s.title = col === null ? "Transparent (eraser)" : col;
      s.addEventListener("click", () => {
        if (col === null) selectTool("eraser");
        else { selectColor(col); selectTool(state.tool === "eraser" ? "pencil" : state.tool); }
        markSwatch(col);
      });
      s._col = col;
      paletteEl.appendChild(s);
    });
  }
  function markSwatch(col) { [...paletteEl.children].forEach(s => s.classList.toggle("selected", s._col === col)); }
  function selectColor(col) {
    state.color = col;
    currentColorEl.style.background = col;
    colorInput.value = col;
    markSwatch(col);
  }

  // ============================================================
  //  Tools UI
  // ============================================================
  function selectTool(tool) {
    state.tool = tool;
    document.querySelectorAll(".tool[data-tool]").forEach(b => b.classList.toggle("selected", b.dataset.tool === tool));
  }

  // ============================================================
  //  Tile size — "the bit buttons". Changes chunkiness only;
  //  the canvas / export size is left untouched.
  // ============================================================
  function setTile(tile) {
    if (tile === state.tile) { updateTileButtons(); return; }
    pushUndo();
    state.tile = tile;
    const g = gridFor(state.canvasW, state.canvasH, tile);
    state.data = resampleTo(g.w, g.h);
    state.w = g.w; state.h = g.h;
    state.pixelSize = fitPixelSize();
    resizeCanvas();
    updateTileButtons();
    updateStatus();
    // export size deliberately unchanged
  }
  function updateTileButtons() {
    document.querySelectorAll(".tileBtn").forEach(b => {
      const n = parseInt(b.dataset.tile, 10);
      b.classList.toggle("active", n === state.tile);
      const g = gridFor(state.canvasW, state.canvasH, n);
      const small = b.querySelector("small");
      if (small) small.textContent = `${g.w}×${g.h}`;
    });
  }
  function updateStatus() {
    const el = $("statusBar");
    if (el) el.textContent = `${state.canvasW}×${state.canvasH} canvas · ${state.tile}px pixels · ${state.w}×${state.h} grid`;
  }

  // ============================================================
  //  Game-scale preview (press & hold) — show the art inside a to-scale
  //  1280×720 PixelPad game window, then zoom back to fill the viewport.
  // ============================================================
  const GAME_W = 1280, GAME_H = 720;
  let previewing = false;
  function enterPreview() {
    if (previewing || editor.classList.contains("hidden")) return;
    previewing = true;
    const area = document.querySelector(".canvas-area");
    const availW = Math.max(40, area.clientWidth - 56);
    const availH = Math.max(40, area.clientHeight - 72);
    const s = Math.min(availW / GAME_W, availH / GAME_H);   // viewport px per game px
    const frame = $("gameFrame");
    frame.style.width = (GAME_W * s) + "px";
    frame.style.height = (GAME_H * s) + "px";
    // scale the art so it shows at its true size inside the game window
    const shown = state.w * state.pixelSize;                // current art display width
    const factor = shown > 0 ? (state.canvasW * s) / shown : 1;
    $("canvasWrap").style.transform = `scale(${factor})`;
    area.classList.add("previewing");
  }
  function exitPreview() {
    if (!previewing) return;
    previewing = false;
    $("canvasWrap").style.transform = "";
    document.querySelector(".canvas-area").classList.remove("previewing");
  }

  // ============================================================
  //  Canvas (picture) size — keeps pixel size, recomputes the grid.
  //  The saved-picture (export) size follows the new picture size.
  // ============================================================
  function setCanvasSize(cw, ch) {
    cw = clamp(cw | 0, 8, 4096);
    ch = clamp(ch | 0, 8, 4096);
    if (cw === state.canvasW && ch === state.canvasH) return;
    pushUndo();
    state.canvasW = cw; state.canvasH = ch;
    const g = gridFor(cw, ch, state.tile);
    state.data = resampleTo(g.w, g.h);
    state.w = g.w; state.h = g.h;
    state.exportW = cw; state.exportH = ch;   // export default tracks the picture size
    state.pixelSize = fitPixelSize();
    resizeCanvas();
    updateTileButtons();
    updateStatus();
  }

  // ============================================================
  //  Export
  // ============================================================
  // Turn the sprite title into a safe .png file name.
  function fileName() {
    let n = (state.name || "").trim();
    if (!n) n = "my-art";
    n = n.replace(/[\\/:*?"<>|]/g, "").trim();   // strip illegal filename characters
    if (!n) n = "my-art";
    if (!/\.png$/i.test(n)) n += ".png";
    return n;
  }
  function setName(n) {
    state.name = (n || "").replace(/[\\/:*?"<>|]/g, "");
    const top = $("spriteName"); if (top && top.value !== state.name) top.value = state.name;
  }

  // Save = download a transparent PNG straight away (no popup). The image is the
  // canvas size; the file name is the editable sprite title (with .png added).
  function doDownload() {
    const ew = clamp(state.exportW || state.canvasW, 1, 8192);
    const eh = clamp(state.exportH || state.canvasH, 1, 8192);

    const off = document.createElement("canvas");
    off.width = ew; off.height = eh;
    const octx = off.getContext("2d");
    octx.imageSmoothingEnabled = false;

    const cw = ew / state.w, ch = eh / state.h;
    for (let y = 0; y < state.h; y++) for (let x = 0; x < state.w; x++) {
      const col = state.data[idx(x, y)];
      if (col) {
        octx.fillStyle = col;
        octx.fillRect(Math.floor(x * cw), Math.floor(y * ch), Math.ceil(cw) + 1, Math.ceil(ch) + 1);
      }
    }

    const a = document.createElement("a");
    a.download = fileName();
    a.href = off.toDataURL("image/png");
    a.click();
  }

  // ============================================================
  //  Canvas size modal
  // ============================================================
  function openCanvas() {
    $("canvasModalW").value = state.canvasW;
    $("canvasModalH").value = state.canvasH;
    updateCanvasHint();
    $("canvasModal").classList.remove("hidden");
  }
  function closeCanvas() { $("canvasModal").classList.add("hidden"); }
  function updateCanvasHint() {
    const w = parseInt($("canvasModalW").value, 10) || state.canvasW;
    const h = parseInt($("canvasModalH").value, 10) || state.canvasH;
    const g = gridFor(w, h, state.tile);
    $("canvasModalHint").textContent = `Pixel size ${state.tile}px → a ${g.w} × ${g.h} grid of pixels.`;
  }
  function applyCanvas() {
    setCanvasSize(parseInt($("canvasModalW").value, 10) || state.canvasW,
                  parseInt($("canvasModalH").value, 10) || state.canvasH);
    closeCanvas();
  }

  // ============================================================
  //  Start / New
  // ============================================================
  function startEditor(canvasW, canvasH, opts = {}) {
    state.canvasW = clamp(canvasW | 0, 8, 4096);
    state.canvasH = clamp(canvasH | 0, 8, 4096);
    state.tile = TILES.includes(opts.tile) ? opts.tile : (opts.tile ? clamp(opts.tile | 0, 1, 256) : DEFAULT_TILE);

    const g = gridFor(state.canvasW, state.canvasH, state.tile);
    state.w = g.w; state.h = g.h;
    state.data = blankData(state.w, state.h);
    state.undo.length = 0; state.redo.length = 0;

    // export size: query string wins, otherwise = the picture size
    state.exportW = opts.exportW ? clamp(opts.exportW | 0, 1, 8192) : state.canvasW;
    state.exportH = opts.exportH ? clamp(opts.exportH | 0, 1, 8192) : state.canvasH;

    setName(opts.name || DEFAULT_NAME);   // sprite title / file name

    welcome.classList.add("hidden");
    editor.classList.remove("hidden");
    state.pixelSize = fitPixelSize();   // measure after the editor is visible
    resizeCanvas();
    updateTileButtons();
    updateStatus();
    updateHistoryButtons();
    selectColor(state.color);
    selectTool("pencil");
  }
  function goToWelcome() { editor.classList.add("hidden"); welcome.classList.remove("hidden"); }

  // ============================================================
  //  Query string
  //    ?canvas=512        picture size in real px (square)  [alias: size]
  //    ?cw=640&ch=320     non-square picture size
  //    ?tile=8            tile size (8/16/32/64) — the "bit" value
  //    ?ew=1024&eh=1024   saved-picture size override (else = picture size)
  //    ?export=1024       shorthand square export override
  //    ?name=bird.png     sprite title / saved file name  [aliases: file, sprite, filename]
  //    ?editor=1          skip the welcome screen
  // ============================================================
  function readQuery() {
    const q = new URLSearchParams(location.search);
    const num = (k) => { const v = parseInt(q.get(k), 10); return Number.isFinite(v) ? v : null; };
    const canvas = num("canvas") ?? num("size");
    const cw = num("cw") ?? canvas;
    const ch = num("ch") ?? canvas;
    const tile = num("tile") ?? num("px") ?? num("pixelsize");
    let ew = num("ew"), eh = num("eh");
    const exp = num("export");
    if (exp != null) { ew = ew ?? exp; eh = eh ?? exp; }
    const name = q.get("name") || q.get("file") || q.get("sprite") || q.get("filename");
    const wantsEditor = q.get("editor") === "1" || cw != null || ch != null || tile != null || ew != null || eh != null || !!name;
    return { cw, ch, tile, ew, eh, name, wantsEditor };
  }

  // ============================================================
  //  Wire up events
  // ============================================================
  function welcomeGrid() {
    const sel = document.querySelector(".preset.selected");
    const tile = sel ? parseInt(sel.dataset.tile, 10) : DEFAULT_TILE;
    const size = parseInt($("canvasSize").value, 10) || DEFAULT_CANVAS;
    return gridFor(size, size, tile);
  }
  function updateWelcomeHint() {
    const g = welcomeGrid();
    $("welcomeHint").textContent = `That gives you a ${g.w} × ${g.h} pixel grid.`;
  }

  function bind() {
    document.querySelectorAll(".preset").forEach(p => {
      p.addEventListener("click", () => {
        document.querySelectorAll(".preset").forEach(x => x.classList.remove("selected"));
        p.classList.add("selected");
        updateWelcomeHint();
      });
    });
    $("canvasSize").addEventListener("input", updateWelcomeHint);
    $("startBtn").addEventListener("click", () => {
      const sel = document.querySelector(".preset.selected");
      const tile = sel ? parseInt(sel.dataset.tile, 10) : DEFAULT_TILE;
      const size = parseInt($("canvasSize").value, 10) || DEFAULT_CANVAS;
      startEditor(size, size, { tile });
    });

    canvas.addEventListener("pointerdown", (e) => { canvas.setPointerCapture(e.pointerId); onDown(e); });
    canvas.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);

    document.querySelectorAll(".tool[data-tool]").forEach(b => b.addEventListener("click", () => selectTool(b.dataset.tool)));
    document.querySelectorAll(".tool[data-act]").forEach(b => b.addEventListener("click", () => {
      const a = b.dataset.act;
      if (a === "flipH") flipH();
      else if (a === "flipV") flipV();
      else if (a === "rotateL") rotate("L");
      else if (a === "rotateR") rotate("R");
      else if (a === "clear") { if (confirm("Clear the whole drawing?")) clearAll(); }
    }));

    $("undoBtn").addEventListener("click", undo);
    $("redoBtn").addEventListener("click", redo);
    document.querySelectorAll(".tileBtn").forEach(b => b.addEventListener("click", () => setTile(parseInt(b.dataset.tile, 10))));
    $("gridBtn").addEventListener("click", () => {
      state.showGrid = !state.showGrid;
      $("gridBtn").classList.toggle("active", state.showGrid);
      render();
    });
    $("exportBtn").addEventListener("click", doDownload);
    $("canvasBtn").addEventListener("click", openCanvas);
    $("newBtn").addEventListener("click", () => { if (confirm("Start a new drawing? Your current one will be cleared.")) goToWelcome(); });

    // game-scale preview: press & hold the Preview button
    const pv = $("previewBtn");
    pv.addEventListener("mousedown", (e) => { e.preventDefault(); enterPreview(); });
    pv.addEventListener("touchstart", (e) => { e.preventDefault(); enterPreview(); }, { passive: false });
    window.addEventListener("mouseup", exitPreview);
    window.addEventListener("touchend", exitPreview);
    window.addEventListener("touchcancel", exitPreview);
    window.addEventListener("blur", exitPreview);

    colorInput.addEventListener("input", () => { selectColor(colorInput.value); if (state.tool === "eraser") selectTool("pencil"); });

    $("spriteName").addEventListener("input", () => { state.name = $("spriteName").value; });

    // canvas size modal
    let canvasRatio = 1;
    $("cancelCanvas").addEventListener("click", closeCanvas);
    $("applyCanvas").addEventListener("click", applyCanvas);
    $("canvasModal").addEventListener("click", (e) => { if (e.target.id === "canvasModal") closeCanvas(); });
    $("canvasBtn").addEventListener("click", () => { canvasRatio = state.canvasW / state.canvasH; });
    $("canvasModalW").addEventListener("input", () => {
      if ($("canvasLockAspect").checked) {
        const v = parseInt($("canvasModalW").value, 10);
        if (Number.isFinite(v)) $("canvasModalH").value = Math.max(8, Math.round(v / canvasRatio));
      }
      updateCanvasHint();
    });
    $("canvasModalH").addEventListener("input", () => {
      if ($("canvasLockAspect").checked) {
        const v = parseInt($("canvasModalH").value, 10);
        if (Number.isFinite(v)) $("canvasModalW").value = Math.max(8, Math.round(v * canvasRatio));
      }
      updateCanvasHint();
    });
    $("canvasLockAspect").addEventListener("change", () => { canvasRatio = (parseInt($("canvasModalW").value, 10) || 1) / (parseInt($("canvasModalH").value, 10) || 1); });

    window.addEventListener("keydown", (e) => {
      if (editor.classList.contains("hidden")) return;
      if (e.target.tagName === "INPUT") return;
      const map = { b: "pencil", e: "eraser", g: "fill", i: "picker", l: "line", r: "rect", c: "ellipse", m: "mirror", v: "move" };
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); e.shiftKey ? redo() : undo(); return; }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") { e.preventDefault(); redo(); return; }
      if (map[e.key.toLowerCase()]) selectTool(map[e.key.toLowerCase()]);
    });

    window.addEventListener("resize", () => {
      if (editor.classList.contains("hidden")) return;
      state.pixelSize = fitPixelSize();
      resizeCanvas();
    });
  }

  // ============================================================
  //  Boot
  // ============================================================
  function init() {
    buildPalette();
    bind();
    selectColor(state.color);
    updateWelcomeHint();

    const q = readQuery();
    if (q.wantsEditor) {
      startEditor(q.cw ?? DEFAULT_CANVAS, q.ch ?? DEFAULT_CANVAS, { tile: q.tile, exportW: q.ew, exportH: q.eh, name: q.name });
    }
  }

  init();
})();
