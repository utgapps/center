# center

A small hub of browser-based creative tools.

## Tools

### 🎨 [Pixel Art Maker](./pixel-art-maker/)
A kid-friendly, Piskel-style pixel art editor that runs entirely in the browser — no install, no account.

**Drawing tools:** Pencil, Eraser, Fill (bucket), Color Picker, Line, Box, Circle, Mirror pen, Move.
**Magic (transformations):** Flip ↔, Flip ↕, Turn left, Turn right, Clear.
**Plus:** undo/redo, a friendly color palette + any custom color, transparent background, a grid toggle, and a Save Picture (PNG) export.

#### Pixel size vs. export size
- The **🔍 Pixel size** buttons only change how big the pixels look **on screen** (zoom). They never change the saved picture.
- The **saved picture size** is set in the **Save Picture** menu (or via a query string). Each drawing pixel becomes a block of real pixels in the exported PNG.

#### Query strings
Open the editor pre-configured by adding parameters to the URL:

| Parameter | Meaning | Example |
|-----------|---------|---------|
| `w`, `h` | Canvas grid size in cells | `?w=32&h=32` |
| `ew`, `eh` | Saved-picture size in real pixels | `?ew=512&eh=512` |
| `export` | Shorthand for a square export size | `?export=512` |
| `editor=1` | Skip the welcome screen, go straight to drawing | `?editor=1` |

Any of `w`, `h`, `ew`, `eh`, or `editor=1` lands you directly on the drawing editor.

**Examples**
- `pixel-art-maker/?editor=1` — open a default 32×32 canvas, ready to draw.
- `pixel-art-maker/?w=16&h=16&export=256` — 16×16 canvas, exports at 256×256.
- `pixel-art-maker/?w=64&h=32&ew=640&eh=320` — non-square canvas and matching export size.

## Run locally
It's all static files. Just open `pixel-art-maker/index.html`, or serve the folder:

```bash
python -m http.server 8000
# then visit http://localhost:8000/pixel-art-maker/
```
