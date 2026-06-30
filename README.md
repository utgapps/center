# center

A small hub of browser-based creative tools.

## Tools

### 🎨 [Pixel Art Maker](./pixel-art-maker/)
A kid-friendly, Piskel-style pixel art editor that runs entirely in the browser — no install, no account.

**Drawing tools:** Pencil, Eraser, Fill (bucket), Color Picker, Line, Box, Circle, Mirror pen, Move.
**Magic (transformations):** Flip ↔, Flip ↕, Turn left, Turn right, Clear.
**Plus:** undo/redo, a friendly color palette + any custom color, transparent background, a grid toggle, and a Save Picture (PNG) export.

#### Pixel size (tile size) vs. picture / export size
- The **picture** is a fixed-size image in real pixels (default **512 × 512**), which is also the default saved (export) size.
- The **Pixel size** buttons — **8-bit / 16-bit / 32-bit / 64-bit** — set the **tile size**: how many real pixels make up one colorable block. *8-bit means every 8 px is one tile.* So on a 512px picture: 8-bit = 64×64 tiles, 16-bit = 32×32, 32-bit = 16×16, 64-bit = 8×8 (chunkier).
- Changing the tile size **never changes the picture or export size** — it only changes how chunky the pixels are (and resamples your art to fit). The saved-image size changes only through the **Save Picture** menu or a query string.

#### Query strings
Open the editor pre-configured by adding parameters to the URL:

| Parameter | Meaning | Example |
|-----------|---------|---------|
| `canvas` / `size` | Picture size in real pixels (square) | `?canvas=512` |
| `cw`, `ch` | Non-square picture size | `?cw=640&ch=320` |
| `tile` | Tile size — the "bit" value (8/16/32/64) | `?tile=8` |
| `ew`, `eh` | Saved-picture size override (defaults to picture size) | `?ew=1024&eh=1024` |
| `export` | Shorthand for a square export override | `?export=1024` |
| `editor=1` | Skip the welcome screen, go straight to drawing | `?editor=1` |

Any of `canvas`, `cw`, `ch`, `tile`, `ew`, `eh`, or `editor=1` lands you directly on the drawing editor.

**Examples**
- `pixel-art-maker/?editor=1` — default 512px picture, 16-bit tiles (32×32 grid).
- `pixel-art-maker/?canvas=512&tile=8` — 512px picture with 8-bit tiles (64×64 grid).
- `pixel-art-maker/?canvas=256&tile=32&export=1024` — chunky 8×8 tiles on a 256px picture, saved at 1024×1024.

## Run locally
It's all static files. Just open `pixel-art-maker/index.html`, or serve the folder:

```bash
python -m http.server 8000
# then visit http://localhost:8000/pixel-art-maker/
```
