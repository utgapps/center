# center

A small hub of browser-based resources.

## Class access (the 4-letter code gate)

The home page is locked behind a **4-letter class code** so kids can't use the tools outside of class. Codes live in **[`class-codes.js`](./class-codes.js)** — edit that file and push to control access. Each entry:

```js
{ code: "DEMO", label: "Open access (demo)", enabled: true, tools: "all" }
```

- **`enabled`** — `true` = the code works now; `false` = locked. To lock a class out after class / at home, set its code to `false` and push; to let them in, set it `true`.
- **`tools`** — `"all"`, or a list of `"pixel-art"` / `"camp"`, to control *which* resources that code reveals.
- **`print`** — `true` lets that code use **Print to PDF** on the coding workbooks; leave it out / `false` to block printing. (When blocked, the button is hidden *and* Ctrl+P prints a blank page, so it can't be bypassed.)
- **`play`** — who may **play the finished games** (the "Play" buttons): `"all"`, a list of game slugs (e.g. `["flappy","drift"]`), or `[]` / leave out for none. When a game isn't allowed its Play button is hidden, and opening its `-final.html` directly bounces to that game's guide. (Game slugs are listed in `class-codes.js`.)

Out of the box: **`QWER`** = students (all resources, **no** printing, **no** playing — guides only), **`ASDF`** = teacher (all resources, **can** print and play). To let students play a specific game, add its slug to QWER's `play` list.

Entering a valid, enabled code reveals the matching resources and remembers it on that device. Tool pages (and the games/guides) check the code too, so typing a direct URL at home still bounces back to the gate. It's a simple gate, **not real security** — the codes are public in the repo; it just keeps kids out of the resources outside class. (Browsers may cache `class-codes.js` for a few minutes, so a lock can take a little while to take effect.)

## Resources

### 🎨 [Pixel Art Maker](./pixel-art-maker/)
A kid-friendly, Piskel-style pixel art editor that runs entirely in the browser — no install, no account.

**Drawing tools:** Pencil, Eraser, Fill (bucket), Color Picker, Line, Box, Circle, Mirror pen, Move.
**Magic (transformations):** Flip ↔, Flip ↕, Turn left, Turn right, Clear.
**Plus:** undo/redo, a friendly color palette + any custom color, transparent background, a grid toggle, and a Save Picture (PNG) export.

#### Pixel size vs. picture / export size
- The **picture** is a fixed-size image in real pixels (default **512 × 512**), which is also the default saved (export) size.
- The **Pixel size** buttons — **8px / 16px / 32px / 64px** — set how many real pixels make up one drawing pixel (one colorable block). So on a 512px picture: 8px → 64×64 grid, 16px → 32×32, 32px → 16×16, 64px → 8×8 (chunkier). Bigger pixel size = chunkier art.
- (Note: "8-bit / 16-bit" is *color depth*, not size — that's why this control is called **pixel size**, not "bit". The number of pixels across is the **resolution** / grid.)
- Changing the pixel size **never changes the picture or export size** — it only changes how chunky the pixels are (and resamples your art to fit). The saved-image size matches the canvas size (change it with the **Canvas** button or a query string).
- **Save** downloads a transparent PNG straight away — no dialog. The file name is the editable sprite title in the toolbar (`.png` is added automatically).

#### Query strings
Open the editor pre-configured by adding parameters to the URL:

| Parameter | Meaning | Example |
|-----------|---------|---------|
| `canvas` / `size` | Picture size in real pixels (square) | `?canvas=512` |
| `cw`, `ch` | Non-square picture size | `?cw=640&ch=320` |
| `px` / `tile` | Pixel size — real px per drawing pixel (8/16/32/64) | `?px=8` |
| `ew`, `eh` | Saved-picture size override (defaults to picture size) | `?ew=1024&eh=1024` |
| `export` | Shorthand for a square export override | `?export=1024` |
| `name` | Sprite title / saved file name (aliases: `file`, `sprite`, `filename`) | `?name=bird.png` |
| `editor=1` | Skip the welcome screen, go straight to drawing | `?editor=1` |

Any of `canvas`, `cw`, `ch`, `px`/`tile`, `ew`, `eh`, or `editor=1` lands you directly on the drawing editor.

**Examples**
- `pixel-art-maker/?editor=1` — default 512px picture, 16px pixels (32×32 grid).
- `pixel-art-maker/?canvas=512&px=8` — 512px picture with 8px pixels (64×64 grid).
- `pixel-art-maker/?canvas=256&px=32&export=1024` — chunky 8×8 grid on a 256px picture, saved at 1024×1024.

### 🏕️ [Camp Coding Projects](./camp-coding-projects/)
20 printable, step-by-step game workbooks (built on [PixelPad](https://pixelpad.io)) — Flappy Bird, Pac-Man, Pong, and more. Each lands on a hub linking every workbook and its playable finished game.

Every workbook's "Before you start" sprite list is **clickable**: each sprite (e.g. *"bird.png — draw it 30×30, yellow"*) links straight to the Pixel Art Maker with the canvas size pre-filled (`?cw=30&ch=30&px=1&editor=1`), so a kid taps it, draws the sprite at exactly the right size, and saves the PNG. `px=1` makes the drawing grid match the sprite's native pixel dimensions.

This whole folder is generated — edit `camp-coding-projects/workbooks.py` and run `python workbooks.py` from that folder to rebuild every workbook, finished game, and the hub. The sprite-linking lives in `setup_block()`, so it survives regeneration. See `camp-coding-projects/RULES.md` for the full design rules.

## Run locally
It's all static files. Just open `pixel-art-maker/index.html`, or serve the folder:

```bash
python -m http.server 8000
# then visit http://localhost:8000/pixel-art-maker/
```
