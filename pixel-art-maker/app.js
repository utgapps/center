/* ============================================================
   🎨 Pixel Art Maker — a kid-friendly Piskel-style editor
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
  const MIN_PIXEL = 4;
  const MAX_PIXEL = 48;
  const DEFAULT_EXPORT_SCALE = 16; // saved picture = grid * 16 by default

  // ---------- State ----------
  const state = {
    w: 32,
    h: 32,
    pixelSize: 16,        // on-screen size of each cell (zoom only — never the export size)
    data: [],             // flat array, length w*h, each entry hex string or null
    tool: "pencil",
    color: "#ff4d6d",
    showGrid: true,
    exportW: null,        // saved-picture width in real pixels (independent of pixelSize)
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
  const canvasWrap = $("canvasWrap");
  const paletteEl = $("palette");
  const currentColorEl = $("currentColor");
  const colorInput = $("colorInput");
  const zoomLabel = $("zoomLabel");

  // ============================================================
  //  Setup helpers
  // ============================================================
  function idx(x, y) { return y * state.w + x; }
  function inBounds(x, y) { return x >= 0 && y >= 0 && x < state.w && y < state.h; }
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

  function blankData(w, h) { return new Array(w * h).fill(null); }

  function fitPixelSize() {
    // Pick an on-screen pixel size that fits the available canvas area.
    const area = document.querySelector(".canvas-area");
    const availW = (area ? area.clientWidth : 600) - 60;
    const availH = (area ? area.clientHeight : 600) - 60;
    const size = Math.floor(Math.min(availW / state.w, availH / state.h));
    return clamp(size, MIN_PIXEL, MAX_PIXEL);
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
    const c = Math.max(4, Math.floor(ps / 2));
    for (let y = 0; y < state.h; y++) {
      for (let x = 0; x < state.w; x++) {
        ctx.fillStyle = ((x + y) % 2 === 0) ? "#ffffff" : "#eef0f3";
        ctx.fillRect(x * ps, y * ps, ps, ps);
        // checker inside each empty cell for a "transparent" look
      }
    }
    // subtle checker overlay independent of cell color is skipped for clarity
    void c;
  }

  function render(preview) {
    const ps = state.pixelSize;
    drawChecker();

    // committed pixels
    for (let y = 0; y < state.h; y++) {
      for (let x = 0; x < state.w; x++) {
        const col = state.data[idx(x, y)];
        if (col) { ctx.fillStyle = col; ctx.fillRect(x * ps, y * ps, ps, ps); }
      }
    }

    // preview pixels (line / box / circle / move while dragging)
    if (preview) {
      for (const p of preview) {
        if (!inBounds(p.x, p.y)) continue;
        if (p.color === null) {
          // erase preview -> show checker cell
          ctx.fillStyle = ((p.x + p.y) % 2 === 0) ? "#ffffff" : "#eef0f3";
        } else {
          ctx.fillStyle = p.color;
        }
        ctx.fillRect(p.x * ps, p.y * ps, ps, ps);
      }
    }

    // grid
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
  //  History (undo / redo)
  // ============================================================
  function pushUndo() {
    state.undo.push(state.data.slice());
    if (state.undo.length > 60) state.undo.shift();
    state.redo.length = 0;
    updateHistoryButtons();
  }
  function undo() {
    if (!state.undo.length) return;
    state.redo.push(state.data.slice());
    state.data = state.undo.pop();
    updateHistoryButtons();
    render();
  }
  function redo() {
    if (!state.redo.length) return;
    state.undo.push(state.data.slice());
    state.data = state.redo.pop();
    updateHistoryButtons();
    render();
  }
  function updateHistoryButtons() {
    $("undoBtn").disabled = state.undo.length === 0;
    $("redoBtn").disabled = state.redo.length === 0;
  }

  // ============================================================
  //  Drawing primitives
  // ============================================================
  function setPixel(x, y, color) {
    if (inBounds(x, y)) state.data[idx(x, y)] = color;
  }

  function linePoints(x0, y0, x1, y1) {
    // Bresenham
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
    // midpoint ellipse over the bounding box
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
  let drawing = false;
  let startCell = null;
  let lastCell = null;

  function cellFromEvent(e) {
    const rect = canvas.getBoundingClientRect();
    const x = Math.floor((e.clientX - rect.left) / (rect.width / state.w));
    const y = Math.floor((e.clientY - rect.top) / (rect.height / state.h));
    return { x: clamp(x, 0, state.w - 1), y: clamp(y, 0, state.h - 1) };
  }

  function paintColor() {
    return state.tool === "eraser" ? null : state.color;
  }

  function onDown(e) {
    e.preventDefault();
    const cell = cellFromEvent(e);
    const t = state.tool;

    if (t === "picker") {
      const col = state.data[idx(cell.x, cell.y)];
      if (col) selectColor(col);
      return;
    }

    drawing = true;
    startCell = cell;
    lastCell = cell;
    pushUndo();

    if (t === "pencil" || t === "eraser") {
      setPixel(cell.x, cell.y, paintColor());
      render();
    } else if (t === "mirror") {
      setPixel(cell.x, cell.y, paintColor());
      setPixel(state.w - 1 - cell.x, cell.y, paintColor());
      render();
    } else if (t === "fill") {
      floodFill(cell.x, cell.y, paintColor());
      render();
      drawing = false; // single action
    }
    // line / rect / ellipse / move handled on move + up
  }

  function onMove(e) {
    if (!drawing) return;
    e.preventDefault();
    const cell = cellFromEvent(e);
    const t = state.tool;

    if (t === "pencil" || t === "eraser") {
      // connect with a line so fast strokes don't skip
      for (const p of linePoints(lastCell.x, lastCell.y, cell.x, cell.y)) setPixel(p.x, p.y, paintColor());
      lastCell = cell;
      render();
    } else if (t === "mirror") {
      for (const p of linePoints(lastCell.x, lastCell.y, cell.x, cell.y)) {
        setPixel(p.x, p.y, paintColor());
        setPixel(state.w - 1 - p.x, p.y, paintColor());
      }
      lastCell = cell;
      render();
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

    if (t === "line") {
      for (const p of linePoints(startCell.x, startCell.y, cell.x, cell.y)) setPixel(p.x, p.y, paintColor());
    } else if (t === "rect") {
      for (const p of rectPoints(startCell.x, startCell.y, cell.x, cell.y)) setPixel(p.x, p.y, paintColor());
    } else if (t === "ellipse") {
      for (const p of ellipsePoints(startCell.x, startCell.y, cell.x, cell.y)) setPixel(p.x, p.y, paintColor());
    } else if (t === "move") {
      commitMove(cell.x - startCell.x, cell.y - startCell.y);
    }
    drawing = false;
    render();
  }

  // Move tool — wrap-around shift so nothing is ever lost
  function movedPreview(dx, dy) {
    const out = [];
    for (let y = 0; y < state.h; y++) {
      for (let x = 0; x < state.w; x++) {
        const col = state.data[idx(x, y)];
        const nx = ((x + dx) % state.w + state.w) % state.w;
        const ny = ((y + dy) % state.h + state.h) % state.h;
        out.push({ x: nx, y: ny, color: col });
      }
    }
    return out;
  }
  function commitMove(dx, dy) {
    const next = blankData(state.w, state.h);
    for (let y = 0; y < state.h; y++) {
      for (let x = 0; x < state.w; x++) {
        const nx = ((x + dx) % state.w + state.w) % state.w;
        const ny = ((y + dy) % state.h + state.h) % state.h;
        next[idx(nx, ny)] = state.data[idx(x, y)];
      }
    }
    state.data = next;
  }

  // ============================================================
  //  Transformations
  // ============================================================
  function flipH() {
    pushUndo();
    const next = blankData(state.w, state.h);
    for (let y = 0; y < state.h; y++)
      for (let x = 0; x < state.w; x++)
        next[idx(state.w - 1 - x, y)] = state.data[idx(x, y)];
    state.data = next; render();
  }
  function flipV() {
    pushUndo();
    const next = blankData(state.w, state.h);
    for (let y = 0; y < state.h; y++)
      for (let x = 0; x < state.w; x++)
        next[idx(x, state.h - 1 - y)] = state.data[idx(x, y)];
    state.data = next; render();
  }
  function rotate(dir) {
    // dir: "L" or "R". Swaps width/height.
    pushUndo();
    const nw = state.h, nh = state.w;
    const next = new Array(nw * nh).fill(null);
    for (let y = 0; y < state.h; y++) {
      for (let x = 0; x < state.w; x++) {
        let nx, ny;
        if (dir === "R") { nx = state.h - 1 - y; ny = x; }
        else { nx = y; ny = state.w - 1 - x; }
        next[ny * nw + nx] = state.data[idx(x, y)];
      }
    }
    state.w = nw; state.h = nh; state.data = next;
    state.pixelSize = fitPixelSize();
    syncExportToGridDefault();
    resizeCanvas();
    updateZoomLabel();
  }
  function clearAll() {
    pushUndo();
    state.data = blankData(state.w, state.h);
    render();
  }

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
        if (col === null) { selectTool("eraser"); }
        else { selectColor(col); selectTool(state.tool === "eraser" ? "pencil" : state.tool); }
        markSwatch(col);
      });
      s._col = col;
      paletteEl.appendChild(s);
    });
  }
  function markSwatch(col) {
    [...paletteEl.children].forEach(s => s.classList.toggle("selected", s._col === col));
  }
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
    document.querySelectorAll(".tool[data-tool]").forEach(b =>
      b.classList.toggle("selected", b.dataset.tool === tool));
  }

  // ============================================================
  //  Zoom (pixel size on screen — NOT export size)
  // ============================================================
  function setPixelSize(ps) {
    state.pixelSize = clamp(ps, MIN_PIXEL, MAX_PIXEL);
    resizeCanvas();
    updateZoomLabel();
  }
  function updateZoomLabel() { zoomLabel.textContent = "Pixel size: " + state.pixelSize; }

  // ============================================================
  //  Export
  // ============================================================
  function syncExportToGridDefault() {
    state.exportW = state.w * DEFAULT_EXPORT_SCALE;
    state.exportH = state.h * DEFAULT_EXPORT_SCALE;
  }

  function openExport() {
    $("gridInfo").textContent = `${state.w} × ${state.h}`;
    $("exportW").value = state.exportW;
    $("exportH").value = state.exportH;
    $("exportModal").classList.remove("hidden");
  }
  function closeExport() { $("exportModal").classList.add("hidden"); }

  function doDownload() {
    const ew = clamp(parseInt($("exportW").value, 10) || state.w, 1, 8192);
    const eh = clamp(parseInt($("exportH").value, 10) || state.h, 1, 8192);
    state.exportW = ew; state.exportH = eh;
    const transparent = $("transparentBg").checked;

    const off = document.createElement("canvas");
    off.width = ew; off.height = eh;
    const octx = off.getContext("2d");
    octx.imageSmoothingEnabled = false;

    if (!transparent) { octx.fillStyle = "#ffffff"; octx.fillRect(0, 0, ew, eh); }

    const cw = ew / state.w, ch = eh / state.h;
    for (let y = 0; y < state.h; y++) {
      for (let x = 0; x < state.w; x++) {
        const col = state.data[idx(x, y)];
        if (col) {
          octx.fillStyle = col;
          // +1 avoids hairline gaps from fractional cell sizes
          octx.fillRect(Math.floor(x * cw), Math.floor(y * ch),
            Math.ceil(cw) + 1, Math.ceil(ch) + 1);
        }
      }
    }

    const a = document.createElement("a");
    a.download = `pixel-art-${state.w}x${state.h}.png`;
    a.href = off.toDataURL("image/png");
    a.click();
    closeExport();
  }

  // ============================================================
  //  Start / New
  // ============================================================
  function startEditor(w, h, opts = {}) {
    state.w = clamp(w | 0, 2, 128);
    state.h = clamp(h | 0, 2, 128);
    state.data = blankData(state.w, state.h);
    state.undo.length = 0; state.redo.length = 0;

    // export size: query string wins, otherwise default scale
    if (opts.exportW || opts.exportH) {
      state.exportW = clamp((opts.exportW || opts.exportH) | 0, 1, 8192);
      state.exportH = clamp((opts.exportH || opts.exportW) | 0, 1, 8192);
    } else {
      syncExportToGridDefault();
    }

    welcome.classList.add("hidden");
    editor.classList.remove("hidden");
    // measure AFTER the editor is visible, or the canvas area has zero size
    state.pixelSize = fitPixelSize();
    resizeCanvas();
    updateZoomLabel();
    updateHistoryButtons();
    selectColor(state.color);
    selectTool("pencil");
  }

  function goToWelcome() {
    editor.classList.add("hidden");
    welcome.classList.remove("hidden");
  }

  // ============================================================
  //  Query string
  //    ?w=32&h=32     -> canvas grid size (cells)
  //    ?ew=512&eh=512 -> saved-picture size in real pixels
  //    ?export=512    -> shorthand for square export size
  //    ?editor=1      -> skip the welcome screen and open the editor
  // ============================================================
  function readQuery() {
    const q = new URLSearchParams(location.search);
    const num = (k) => { const v = parseInt(q.get(k), 10); return Number.isFinite(v) ? v : null; };

    const w = num("w") ?? num("gw");
    const h = num("h") ?? num("gh");
    let ew = num("ew");
    let eh = num("eh");
    const exp = num("export");
    if (exp != null) { ew = ew ?? exp; eh = eh ?? exp; }

    const wantsEditor = q.get("editor") === "1" || w != null || h != null || ew != null || eh != null;
    return { w, h, ew, eh, wantsEditor };
  }

  // ============================================================
  //  Wire up events
  // ============================================================
  function bind() {
    // welcome presets
    document.querySelectorAll(".preset").forEach(p => {
      p.addEventListener("click", () => {
        document.querySelectorAll(".preset").forEach(x => x.classList.remove("selected"));
        p.classList.add("selected");
        $("customW").value = p.dataset.w;
        $("customH").value = p.dataset.h;
      });
    });
    $("startBtn").addEventListener("click", () => {
      startEditor(parseInt($("customW").value, 10) || 32, parseInt($("customH").value, 10) || 32);
    });

    // canvas pointer
    canvas.addEventListener("pointerdown", (e) => { canvas.setPointerCapture(e.pointerId); onDown(e); });
    canvas.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);

    // tools
    document.querySelectorAll(".tool[data-tool]").forEach(b =>
      b.addEventListener("click", () => selectTool(b.dataset.tool)));

    // transforms
    document.querySelectorAll(".tool[data-act]").forEach(b =>
      b.addEventListener("click", () => {
        const a = b.dataset.act;
        if (a === "flipH") flipH();
        else if (a === "flipV") flipV();
        else if (a === "rotateL") rotate("L");
        else if (a === "rotateR") rotate("R");
        else if (a === "clear") { if (confirm("Clear the whole drawing?")) clearAll(); }
      }));

    // top bar
    $("undoBtn").addEventListener("click", undo);
    $("redoBtn").addEventListener("click", redo);
    $("zoomIn").addEventListener("click", () => setPixelSize(state.pixelSize + 2));
    $("zoomOut").addEventListener("click", () => setPixelSize(state.pixelSize - 2));
    $("gridBtn").addEventListener("click", () => {
      state.showGrid = !state.showGrid;
      $("gridBtn").classList.toggle("active", state.showGrid);
      render();
    });
    $("exportBtn").addEventListener("click", openExport);
    $("newBtn").addEventListener("click", () => {
      if (confirm("Start a new drawing? Your current one will be cleared.")) goToWelcome();
    });

    // colors
    colorInput.addEventListener("input", () => {
      selectColor(colorInput.value);
      if (state.tool === "eraser") selectTool("pencil");
    });

    // export modal
    $("cancelExport").addEventListener("click", closeExport);
    $("downloadBtn").addEventListener("click", doDownload);
    $("exportModal").addEventListener("click", (e) => { if (e.target.id === "exportModal") closeExport(); });
    document.querySelectorAll(".scaleBtn").forEach(b =>
      b.addEventListener("click", () => {
        const s = parseInt(b.dataset.scale, 10);
        const ew = state.w * s, eh = state.h * s;
        $("exportW").value = ew; $("exportH").value = eh;
      }));
    // lock aspect ratio while typing export size
    const baseRatio = () => state.w / state.h;
    $("exportW").addEventListener("input", () => {
      if (!$("lockAspect").checked) return;
      const v = parseInt($("exportW").value, 10);
      if (Number.isFinite(v)) $("exportH").value = Math.round(v / baseRatio());
    });
    $("exportH").addEventListener("input", () => {
      if (!$("lockAspect").checked) return;
      const v = parseInt($("exportH").value, 10);
      if (Number.isFinite(v)) $("exportW").value = Math.round(v * baseRatio());
    });

    // keyboard shortcuts (handy for older kids / parents)
    window.addEventListener("keydown", (e) => {
      if (editor.classList.contains("hidden")) return;
      if (e.target.tagName === "INPUT") return;
      const map = { b: "pencil", e: "eraser", g: "fill", i: "picker", l: "line", r: "rect", c: "ellipse", m: "mirror", v: "move" };
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); e.shiftKey ? redo() : undo(); return; }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") { e.preventDefault(); redo(); return; }
      if (map[e.key.toLowerCase()]) selectTool(map[e.key.toLowerCase()]);
    });

    // keep a sensible zoom when the window resizes (only if user hasn't gone tiny/huge)
    window.addEventListener("resize", () => {
      if (editor.classList.contains("hidden")) return;
    });
  }

  // ============================================================
  //  Boot
  // ============================================================
  function init() {
    buildPalette();
    bind();
    selectColor(state.color);

    const q = readQuery();
    if (q.wantsEditor) {
      startEditor(q.w ?? 32, q.h ?? 32, { exportW: q.ew, exportH: q.eh });
    }
  }

  init();
})();
