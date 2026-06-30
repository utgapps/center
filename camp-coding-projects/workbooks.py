# Builds printable step-by-step workbooks for ALL arcade games, plus the assembled
# playable game for each (to verify the steps really make a working game), plus an
# index page linking them. Run: python workbooks.py
#
# Structure (real PixelPad rooms):
#   Game        - holds globals (score, lives); start() sets them and set_room('Play')
#   Play room   - creates the objects + the HUD; the game is played here
#   GameOver    - a separate room shown when you lose; tap goes back to Play
# Rules: each step edits ONE tab, adds a few NEW lines (green), playable often,
#        named variables, no arrays, white text (.color = "white").
import json, html

CDN = "https://cdn.jsdelivr.net/gh/pixelpad-io/pixelpad.min@main/pixelpad.min.js"

import zlib, struct, base64, re
# Colour names -> RGB. Sprites are drawn at their NATIVE pixel size (no scaling in code),
# so the kid draws each sprite at the dimensions listed in the workbook's setup.
RGB = {
 "white":(255,255,255),"dark":(20,24,31),"yellow":(244,208,63),"green":(90,208,107),
 "red":(230,75,75),"blue":(74,163,255),"brown":(156,107,63),"gray":(138,147,163),
 "orange":(239,139,59),"purple":(168,107,214),"dgreen":(47,107,58),"cyan":(80,220,200),
}
def solid_png(rgb, w, h):
    # A solid-colour PNG of size w x h, as a data URI (placeholder art for the final game).
    def chunk(typ, data):
        c = typ + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
    row = b"\x00" + bytes(rgb + (255,)) * w
    raw = row * h
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw))
           + chunk(b"IEND", b""))
    return "data:image/png;base64," + base64.b64encode(png).decode()

def tex(mapping):
    return dict(mapping)   # {name: colour-name}; size comes from the code's scaleX/scaleY

def sprite_dims(game):
    # Read each sprite's pixel size from the scaleX/scaleY lines that follow its image line.
    dims = {}
    for s in game["steps"]:
        name = w = h = None
        for ln in s["lines"]:
            m = re.match(r"self\.image = sprite\('([^']+)'\)", ln)
            if m: name = m.group(1)
            m = re.match(r"self\.scaleX = (\d+)$", ln)
            if m: w = int(m.group(1))
            m = re.match(r"self\.scaleY = (\d+)$", ln)
            if m: h = int(m.group(1))
        if name and w and h:
            if name in dims and dims[name] != (w, h):
                raise ValueError("%s: sprite %s used at two sizes %s vs %s" % (game["slug"], name, dims[name], (w, h)))
            dims[name] = (w, h)
    return dims

def strip_scale(lines):
    # Remove constant scaleX/scaleY lines - sprites are native-size now.
    return [ln for ln in lines if not re.match(r"self\.scale[XY] = \d+$", ln)]

def split_if(line):
    # Turn a one-line "if cond: statement" into two lines (the body indented under the if).
    m = re.match(r"^(\s*)(if .+?|elif .+?): (\S.*)$", line)
    if m:
        return [m.group(1) + m.group(2) + ":", m.group(1) + "    " + m.group(3)]
    return [line]

def prefix_locals(lines, pfx):
    # Give every bare local variable a prefix (self. in a class, Game. in a room) so kids
    # never see a lonely name. Detect names used as "name = ..." (no dot), then prefix all
    # their whole-word uses, but never touch text inside quotes (e.g. sprite names).
    names = set()
    for ln in lines:
        m = re.match(r"^\s*([a-z][A-Za-z0-9]*) = ", ln)
        if m:
            names.add(m.group(1))
    if not names:
        return lines
    def fix(seg):
        for nm in names:
            seg = re.sub(r"(?<![\w.'])" + re.escape(nm) + r"(?![\w'])", pfx + nm, seg)
        return seg
    out = []
    for ln in lines:
        parts = re.split(r"('[^']*')", ln)   # odd parts are quoted strings - leave them alone
        out.append("".join(p if i % 2 else fix(p) for i, p in enumerate(parts)))
    return out

def prep(game, s):
    pfx = "Game." if s["asset"] in game["rooms"] else "self."
    lines = prefix_locals(strip_scale(s["lines"]), pfx)
    out = []
    for ln in lines:
        out.extend(split_if(ln))
    return out

def chunk_units(lines):
    # Group each block (a line ending ':' plus its deeper-indented body) so we never
    # split an 'if' from the code it runs when paginating.
    units, i = [], 0
    while i < len(lines):
        line = lines[i]
        indent = len(line) - len(line.lstrip())
        unit = [line]; i += 1
        if line.rstrip().endswith(":"):
            while i < len(lines) and (len(lines[i]) - len(lines[i].lstrip())) > indent:
                unit.append(lines[i]); i += 1
        units.append(unit)
    return units

def paginate(lines, maxn=6):
    # Pack whole units into pages of at most maxn lines (a single big block can exceed it).
    pages, cur = [], []
    for u in chunk_units(lines):
        if cur and len(cur) + len(u) > maxn:
            pages.append(cur); cur = []
        cur.extend(u)
    if cur:
        pages.append(cur)
    return pages

def S(asset, tab, instr, lines, play=False):
    return {"asset": asset, "tab": tab, "instr": instr, "lines": lines, "play": play}

# A GameOver.start step that shows the final score under the big message.
# expr is the Python text to display; defaults to the plain score.
def SCORELINE(expr="'Final Score: ' + str(Game.score)",
              instr="Under the message, show your final score so you can see how you did."):
    return S("GameOver","start", instr,
        ["s = text()","s.color = \"white\"","s.fontSize = 28","s.halign = \"center\"","s.y = -60","s.text = " + expr])

GAMES = []

# --- 1) CATCH THE FRUIT ----------------------------------------------------
GAMES.append({
 "title":"Catch the Fruit","slug":"catch",
 "classes":["Game","Basket","Fruit"], "rooms":["Play","GameOver"],
 "textures": tex({"basket.png":"blue","apple.png":"red"}),
 "steps":[
  S("Game","start","Set up the game: a score, 3 lives, a falling speed, then go to the Play room.",
    ["self.score = 0","self.lives = 3","self.fallSpeed = 4","self.dead = False","self.restart = False","set_room('Play')"]),
  S("Basket","start","Add a Class called Basket: a picture, a size, near the bottom.",
    ["self.image = sprite('basket.png')","self.scaleX = 100","self.scaleY = 26","self.y = -210"]),
  S("Play","start","In the Play room, make your basket. Press Play - it appears!",
    ["Game.basket = Basket()"], play=True),
  S("Basket","loop","Make the basket follow your mouse, but stay on screen. Press Play and move it.",
    ["self.x = mouse_x()","if self.x > 320:","    self.x = 320","if self.x < -320:","    self.x = -320"], play=True),
  S("Fruit","start","Add a Class called Fruit: a picture, a size, up high at a random spot.",
    ["import random","self.image = sprite('apple.png')","self.scaleX = 30","self.scaleY = 30",
     "self.x = random.randint(-300, 300)","self.y = 250"]),
  S("Play","start","Make three pieces of fruit. Press Play - fruit at the top!",
    ["Game.fruitA = Fruit()","Game.fruitB = Fruit()","Game.fruitC = Fruit()"], play=True),
  S("Fruit","loop","Make the fruit fall. Press Play and watch it drop.",
    ["import random","self.y = self.y - Game.fallSpeed"], play=True),
  S("Fruit","loop","Catch it! Add a point, speed up, drop a new one. Press Play and catch.",
    ["if get_collision(self, 'Basket'):","    Game.score = Game.score + 1","    Game.fallSpeed = Game.fallSpeed + 0.2",
     "    self.y = 250","    self.x = random.randint(-300, 300)"], play=True),
  S("Fruit","loop","Miss it = lose a life. At 0 lives, go to the GameOver room. Press Play - don't miss!",
    ["if self.y < -260:","    Game.lives = Game.lives - 1","    self.y = 250","    self.x = random.randint(-300, 300)",
     "    if Game.lives < 1:","        Game.dead = True"], play=True),
  S("Play","start","Add a white label for score and lives.",
    ["Game.label = text()","Game.label.color = \"white\"","Game.label.y = 235","Game.label.text = 'Score: 0'"], play=True),
  S("Play","loop","Keep the label updated. Press Play.",
    ["Game.label.text = 'Score: ' + str(Game.score) + '   Lives: ' + str(Game.lives)"], play=True),
  S("Game","loop","When you lose, switch to the GameOver room. Press Play - lose to see it!",
    ["if self.dead:","    self.dead = False","    set_room('GameOver')"], play=True),
  S("GameOver","start","In the GameOver room, show a big white message in the middle.",
    ["t = text()","t.color = \"white\"","t.fontSize = 40","t.halign = \"center\"","t.text = 'GAME OVER - tap to play again'"]),
  SCORELINE(),
  S("GameOver","loop","Tap to start over: reset and go back to Play. Press Play - lose, then retry!",
    ["if key_was_pressed(' ') or mouse_was_pressed('left'):","    Game.score = 0","    Game.lives = 3","    set_room('Play')"], play=True),
 ]})

# --- 2) WHACK-A-MOLE -------------------------------------------------------
GAMES.append({
 "title":"Whack-a-Mole","slug":"whack",
 "classes":["Game","Board","Mole"], "rooms":["Play","GameOver"],
 "textures": tex({"mole.png":"brown","board.png":"dgreen"}),
 "steps":[
  S("Game","start","Set up: score, a spawn timer, a countdown timer, no mole yet, then go to Play.",
    ["self.score = 0","self.spawnTimer = 0","self.timeLeft = 1800","self.mole = False","self.dead = False","self.restart = False","set_room('Play')"]),
  S("Board","start","Add a Class called Board - the green play area.",
    ["self.image = sprite('board.png')","self.scaleX = 720","self.scaleY = 500","self.z = -10"]),
  S("Play","start","In the Play room, make the board. Press Play - the play area appears.",
    ["Game.board = Board()"], play=True),
  S("Mole","start","Add a Class called Mole: a picture and size, at a random spot.",
    ["import random","self.image = sprite('mole.png')","self.scaleX = 64","self.scaleY = 64",
     "self.x = random.randint(-2, 2) * 150","self.y = random.randint(-1, 1) * 130"]),
  S("Mole","start","Give the mole its own timer.",
    ["self.aliveTime = 0"]),
  S("Play","loop","Pop up a mole every little while. Press Play - moles appear!",
    ["if not Game.mole:","    Game.spawnTimer = Game.spawnTimer + 1","    if Game.spawnTimer > 22:",
     "        Game.spawnTimer = 0","        Game.mole = Mole()"], play=True),
  S("Mole","loop","Make the mole hide after a moment. Press Play - moles pop up and vanish!",
    ["self.aliveTime = self.aliveTime + 1","if self.aliveTime > 70:","    Game.mole = False","    destroy(self)"], play=True),
  S("Mole","loop","Whack it! Click the mole to score. Press Play and whack them.",
    ["clickX = mouse_x() > self.x - 36 and mouse_x() < self.x + 36","clickY = mouse_y() > self.y - 36 and mouse_y() < self.y + 36",
     "if mouse_was_pressed('left') and clickX and clickY:","    Game.score = Game.score + 1","    Game.mole = False","    destroy(self)"], play=True),
  S("Play","start","Add a white label for the score.",
    ["Game.label = text()","Game.label.color = \"white\"","Game.label.y = 220","Game.label.text = 'Score: 0'"], play=True),
  S("Play","loop","Show the score. Press Play.",
    ["Game.label.text = 'Score: ' + str(Game.score)"], play=True),
  S("Play","loop","Count the timer down. When it runs out, go to the GameOver room. Press Play.",
    ["Game.timeLeft = Game.timeLeft - 1","if Game.timeLeft < 1:","    Game.dead = True"], play=True),
  S("Game","loop","When you lose, switch to the GameOver room. Press Play - lose to see it!",
    ["if self.dead:","    self.dead = False","    set_room('GameOver')"], play=True),
  S("GameOver","start","In the GameOver room, show a big white message.",
    ["t = text()","t.color = \"white\"","t.fontSize = 40","t.halign = \"center\"","t.text = 'TIME UP - tap to play again'"]),
  SCORELINE(),
  S("GameOver","loop","Tap to play again: reset and go back to Play. Press Play!",
    ["if key_was_pressed(' ') or mouse_was_pressed('left'):","    Game.score = 0","    Game.timeLeft = 1800","    set_room('Play')"], play=True),
 ]})

# --- 3) FLAPPY BIRD --------------------------------------------------------
GAMES.append({
 "title":"Flappy Bird","slug":"flappy",
 "classes":["Game","Sky","Bird","Block","Pipe"], "rooms":["Play","GameOver"],
 "textures": tex({"bird.png":"yellow","pipe.png":"green","sky.png":"cyan"}),
 "steps":[
  S("Game","start","Set up: a score, 3 lives, then go to the Play room.",
    ["self.score = 0","self.lives = 3","self.dead = False","self.restart = False","set_room('Play')"]),
  S("Sky","start","Add a Class called Sky - the blue background.",
    ["self.image = sprite('sky.png')","self.scaleX = 760","self.scaleY = 560","self.z = -10"]),
  S("Play","start","In the Play room, make the sky. Press Play - blue sky!",
    ["Game.sky = Sky()"], play=True),
  S("Bird","start","Add a Class called Bird: gravity, a flap strength, a picture, a size, a speed.",
    ["self.gravity = 0.7","self.flapStrength = 9","self.image = sprite('bird.png')",
     "self.scaleX = 30","self.scaleY = 30","self.speedY = 0"]),
  S("Play","start","Make your bird. Press Play - it appears.",
    ["Game.bird = Bird()"], play=True),
  S("Bird","loop","Gravity pulls it down; a tap flaps it up. Press Play, press Space!",
    ["self.speedY = self.speedY - self.gravity","if key_was_pressed(' ') or mouse_was_pressed('left'):",
     "    self.speedY = self.flapStrength","self.y = self.y + self.speedY"], play=True),
  S("Block","start","Add a Class called Block - one green pipe.",
    ["self.image = sprite('pipe.png')","self.scaleX = 64","self.scaleY = 280","self.z = 2"]),
  S("Pipe","start","Add a Class called Pipe: a top and bottom pipe with a gap.",
    ["import random","self.x = 380","self.gapY = random.randint(-110, 110)","self.passed = False",
     "self.topPipe = Block()","self.bottomPipe = Block()"]),
  S("Play","start","Make a pipe. Press Play - two pipes appear.",
    ["Game.pipe = Pipe()"], play=True),
  S("Pipe","loop","Slide the pipes left and line up the gap. Press Play!",
    ["self.x = self.x - 4","self.topPipe.x = self.x","self.topPipe.y = self.gapY + 210",
     "self.bottomPipe.x = self.x","self.bottomPipe.y = self.gapY - 210"], play=True),
  S("Pipe","loop","Send a pipe back to the right with a new gap when it leaves.",
    ["import random","if self.x < -380:","    self.x = 380","    self.gapY = random.randint(-110, 110)","    self.passed = False"], play=True),
  S("Pipe","loop","Score ONE point each time a pipe passes (the 'passed' flag stops double-counting).",
    ["if not self.passed and self.x < -150:","    self.passed = True","    Game.score = Game.score + 1"], play=True),
  S("Bird","loop","Hit a pipe or fall too low = lose a life. At 0 lives, go to GameOver.",
    ["if self.y < -250 or get_collision(self, 'Block'):","    Game.lives = Game.lives - 1","    self.y = 0",
     "    self.speedY = 0","    if Game.lives < 1:","        Game.dead = True"], play=True),
  S("Play","start","Add a white label for score and lives.",
    ["Game.label = text()","Game.label.color = \"white\"","Game.label.y = 220","Game.label.text = '0'"], play=True),
  S("Play","loop","Keep the label updated. Press Play.",
    ["Game.label.text = 'Score: ' + str(Game.score) + '   Lives: ' + str(Game.lives)"], play=True),
  S("Game","loop","When you lose, switch to the GameOver room. Press Play - lose to see it!",
    ["if self.dead:","    self.dead = False","    set_room('GameOver')"], play=True),
  S("GameOver","start","In the GameOver room, show a big white message.",
    ["t = text()","t.color = \"white\"","t.fontSize = 40","t.halign = \"center\"","t.text = 'GAME OVER - tap to retry'"]),
  SCORELINE(),
  S("GameOver","loop","Tap to retry: reset and go back to Play. Press Play - fly far!",
    ["if key_was_pressed(' ') or mouse_was_pressed('left'):","    Game.score = 0","    Game.lives = 3","    set_room('Play')"], play=True),
 ]})

# --- 4) SUBWAY SURFERS -----------------------------------------------------
GAMES.append({
 "title":"Subway Surfers","slug":"subway",
 "classes":["Game","Bg","Player","Rock"], "rooms":["Play","GameOver"],
 "textures": tex({"player.png":"orange","rock.png":"red","road.png":"gray"}),
 "steps":[
  S("Game","start","Set up: a score, 3 lives, a speed, then go to the Play room.",
    ["self.score = 0","self.lives = 3","self.gameSpeed = 4","self.dead = False","self.restart = False","set_room('Play')"]),
  S("Bg","start","Add a Class called Bg - the road.",
    ["self.image = sprite('road.png')","self.scaleX = 420","self.scaleY = 560","self.z = -10"]),
  S("Play","start","In the Play room, make the road. Press Play - the track appears.",
    ["Game.bg = Bg()"], play=True),
  S("Player","start","Add a Class called Player in the middle lane, with a picture and size.",
    ["self.currentLane = 1","self.image = sprite('player.png')","self.scaleX = 46","self.scaleY = 46","self.y = -180"]),
  S("Play","start","Make your player. Press Play - it appears at the bottom.",
    ["Game.player = Player()"], play=True),
  S("Player","loop","Use the arrows to pick a lane (0, 1, or 2).",
    ["if key_was_pressed('arrowLeft') or key_was_pressed('a'):","    if self.currentLane > 0:",
     "        self.currentLane = self.currentLane - 1","if key_was_pressed('arrowRight') or key_was_pressed('d'):",
     "    if self.currentLane < 2:","        self.currentLane = self.currentLane + 1"]),
  S("Player","loop","Move the player to that lane. Press Play - hop between 3 lanes!",
    ["if self.currentLane == 0:","    self.x = -130","if self.currentLane == 1:","    self.x = 0",
     "if self.currentLane == 2:","    self.x = 130"], play=True),
  S("Rock","start","Add a Class called Rock in a random lane up at the top.",
    ["import random","self.image = sprite('rock.png')","self.scaleX = 46","self.scaleY = 46",
     "self.y = 280","self.x = random.randint(-1, 1) * 130"]),
  S("Play","start","Make three rocks. Press Play - rocks at the top!",
    ["Game.rockA = Rock()","Game.rockB = Rock()","Game.rockC = Rock()"], play=True),
  S("Rock","loop","Make the rocks fall toward you. Press Play - here they come!",
    ["self.y = self.y - Game.gameSpeed"], play=True),
  S("Rock","loop","When a rock passes you, score a point, speed up, and send it back up.",
    ["import random","if self.y < -280:","    Game.score = Game.score + 1","    Game.gameSpeed = Game.gameSpeed + 0.15",
     "    self.y = 280","    self.x = random.randint(-1, 1) * 130"], play=True),
  S("Rock","loop","If a rock hits you = lose a life. At 0 lives, go to GameOver. Press Play - dodge!",
    ["if get_collision(self, 'Player'):","    Game.lives = Game.lives - 1","    self.y = 280","    if Game.lives < 1:","        Game.dead = True"], play=True),
  S("Play","start","Add a white label for score and lives.",
    ["Game.label = text()","Game.label.color = \"white\"","Game.label.y = 220","Game.label.text = 'Score: 0'"], play=True),
  S("Play","loop","Keep the label updated. Press Play.",
    ["Game.label.text = 'Score: ' + str(Game.score) + '   Lives: ' + str(Game.lives)"], play=True),
  S("Game","loop","When you lose, switch to the GameOver room. Press Play - lose to see it!",
    ["if self.dead:","    self.dead = False","    set_room('GameOver')"], play=True),
  S("GameOver","start","In the GameOver room, show a big white message.",
    ["t = text()","t.color = \"white\"","t.fontSize = 40","t.halign = \"center\"","t.text = 'GAME OVER - tap to play again'"]),
  SCORELINE(),
  S("GameOver","loop","Tap to play again: reset and go back to Play. Press Play!",
    ["if key_was_pressed(' ') or mouse_was_pressed('left'):","    Game.score = 0","    Game.lives = 3","    Game.gameSpeed = 4","    set_room('Play')"], play=True),
 ]})

# --- 5) GEOMETRY DASH ------------------------------------------------------
GAMES.append({
 "title":"Geometry Dash","slug":"geo",
 "classes":["Game","Bg","Ground","Player","Spike"], "rooms":["Play","GameOver"],
 "textures": tex({"player.png":"orange","ground.png":"dgreen","spike.png":"gray","sky.png":"dark"}),
 "steps":[
  S("Game","start","Set up: a score, 3 lives, a speed, where the next spike spawns, then go to Play.",
    ["self.score = 0","self.lives = 3","self.gameSpeed = 6","self.nextSpawnX = 440","self.dead = False","set_room('Play')"]),
  S("Bg","start","Add a Class called Bg - the dark background.",
    ["self.image = sprite('sky.png')","self.scaleX = 760","self.scaleY = 560","self.z = -10"]),
  S("Play","start","In the Play room, make the background. Press Play.",
    ["Game.bg = Bg()"], play=True),
  S("Ground","start","Add a Class called Ground - the strip along the bottom.",
    ["self.image = sprite('ground.png')","self.scaleX = 760","self.scaleY = 120","self.y = -230"]),
  S("Play","start","Make the ground. Press Play - the floor appears.",
    ["Game.ground = Ground()"], play=True),
  S("Player","start","Add a Class called Player: gravity, jump strength, a picture and size.",
    ["self.gravity = 0.8","self.jumpStrength = 14","self.image = sprite('player.png')",
     "self.scaleX = 38","self.scaleY = 38","self.speedY = 0"]),
  S("Player","start","Place the player on the ground.",
    ["self.x = -160","self.y = -150","self.onGround = True"]),
  S("Play","start","Make your player. Press Play - it stands on the ground.",
    ["Game.player = Player()"], play=True),
  S("Player","loop","Gravity pulls down; a tap jumps when on the ground.",
    ["self.speedY = self.speedY - self.gravity","if (key_was_pressed(' ') or mouse_was_pressed('left')) and self.onGround:",
     "    self.speedY = self.jumpStrength","self.y = self.y + self.speedY"]),
  S("Player","loop","Stop falling when you land. Press Play - press Space to jump!",
    ["if self.y <= -150:","    self.y = -150","    self.speedY = 0","    self.onGround = True","else:","    self.onGround = False"], play=True),
  S("Player","loop","Spin in the air like real Geometry Dash, and land flat. Press Play - watch it flip!",
    ["if self.onGround:","    self.angle = 0","else:","    self.angle = self.angle - 12"], play=True),
  S("Spike","start","Add a Class called Spike. Each one spawns 420 apart so they are spaced out fairly.",
    ["self.image = sprite('spike.png')","self.scaleX = 36","self.scaleY = 36","self.y = -150",
     "self.x = Game.nextSpawnX","Game.nextSpawnX = Game.nextSpawnX + 420"]),
  S("Play","start","Make two spikes. Press Play - two evenly-spaced spikes on the right!",
    ["Game.spikeA = Spike()","Game.spikeB = Spike()"], play=True),
  S("Spike","loop","Move the spikes toward you. Press Play - jump over them!",
    ["self.x = self.x - Game.gameSpeed"], play=True),
  S("Spike","loop","When a spike goes off the left, score, speed up, and loop it back keeping the same gap. Press Play.",
    ["if self.x < -400:","    Game.score = Game.score + 1","    Game.gameSpeed = Game.gameSpeed + 0.2","    self.x = self.x + 840"], play=True),
  S("Spike","loop","If a spike hits you = lose a life, then loop it ahead. At 0 lives, go to GameOver. Press Play!",
    ["if get_collision(self, 'Player'):","    Game.lives = Game.lives - 1","    self.x = self.x + 840","    if Game.lives < 1:","        Game.dead = True"], play=True),
  S("Play","start","Add a white label for score and lives.",
    ["Game.label = text()","Game.label.color = \"white\"","Game.label.y = 220","Game.label.text = 'Score: 0'"], play=True),
  S("Play","loop","Keep the label updated. Press Play.",
    ["Game.label.text = 'Score: ' + str(Game.score) + '   Lives: ' + str(Game.lives)"], play=True),
  S("Game","loop","When you lose, switch to the GameOver room. Press Play - lose to see it!",
    ["if self.dead:","    self.dead = False","    set_room('GameOver')"], play=True),
  S("GameOver","start","In the GameOver room, show a big white message.",
    ["t = text()","t.color = \"white\"","t.fontSize = 40","t.halign = \"center\"","t.text = 'GAME OVER - tap to play again'"]),
  SCORELINE(),
  S("GameOver","loop","Tap to play again: reset everything and go back to Play. Press Play!",
    ["if key_was_pressed(' ') or mouse_was_pressed('left'):","    Game.score = 0","    Game.lives = 3","    Game.gameSpeed = 6","    Game.nextSpawnX = 440","    set_room('Play')"], play=True),
 ]})

# --- 6) CROSSY ROAD --------------------------------------------------------
GAMES.append({
 "title":"Crossy Road","slug":"crossy",
 "classes":["Game","Road","Player","Car"], "rooms":["Play","GameOver"],
 "textures": tex({"player.png":"green","car.png":"red","road.png":"gray"}),
 "steps":[
  S("Game","start","Set up: a score, 3 lives, a spawn timer, then go to the Play room.",
    ["self.score = 0","self.lives = 3","self.spawnTimer = 0","self.dead = False","self.restart = False","set_room('Play')"]),
  S("Road","start","Add a Class called Road - a wide gray strip in the middle.",
    ["self.image = sprite('road.png')","self.scaleX = 760","self.scaleY = 300","self.z = -10"]),
  S("Play","start","In the Play room, make the road. Press Play - the road appears.",
    ["Game.road = Road()"], play=True),
  S("Player","start","Add a Class called Player at the bottom, with a picture and size.",
    ["self.image = sprite('player.png')","self.scaleX = 38","self.scaleY = 38","self.x = 0","self.y = -200"]),
  S("Play","start","Make your player. Press Play - it appears at the bottom.",
    ["Game.player = Player()"], play=True),
  S("Player","loop","Hop with the arrow keys. Press Play - move around!",
    ["if key_was_pressed('arrowUp') or key_was_pressed('w'): self.y = self.y + 56",
     "if key_was_pressed('arrowDown') or key_was_pressed('s'): self.y = self.y - 56",
     "if key_was_pressed('arrowLeft') or key_was_pressed('a'): self.x = self.x - 56",
     "if key_was_pressed('arrowRight') or key_was_pressed('d'): self.x = self.x + 56"], play=True),
  S("Car","start","Add a Class called Car: a picture and size.",
    ["import random","self.image = sprite('car.png')","self.scaleX = 64","self.scaleY = 34"]),
  S("Car","start","Half start on the left going right, half on the right going left.",
    ["if random.randint(0, 1) == 0:","    self.x = -420","    self.speedX = 4","else:","    self.x = 420","    self.speedX = -4"]),
  S("Play","loop","Make a new car in a random lane every little while. Press Play - traffic!",
    ["import random","Game.spawnTimer = Game.spawnTimer + 1","if Game.spawnTimer > 26:",
     "    Game.spawnTimer = 0","    car = Car()","    car.y = random.randint(-2, 2) * 60"], play=True),
  S("Car","loop","Drive each car across and remove it at the far edge. Press Play - cars both ways!",
    ["self.x = self.x + self.speedX","if self.x > 430 or self.x < -430:","    destroy(self)"], play=True),
  S("Player","loop","A car hits you = lose a life and go back to start. At 0 lives, go to GameOver.",
    ["if get_collision(self, 'Car'):","    Game.lives = Game.lives - 1","    self.x = 0","    self.y = -200","    if Game.lives < 1:","        Game.dead = True"], play=True),
  S("Player","loop","Reach the top to score, then start again. Press Play - cross safely!",
    ["if self.y > 210:","    Game.score = Game.score + 1","    self.x = 0","    self.y = -200"], play=True),
  S("Play","start","Add a white label for score and lives.",
    ["Game.label = text()","Game.label.color = \"white\"","Game.label.y = 230","Game.label.text = 'Score: 0'"], play=True),
  S("Play","loop","Keep the label updated. Press Play.",
    ["Game.label.text = 'Score: ' + str(Game.score) + '   Lives: ' + str(Game.lives)"], play=True),
  S("Game","loop","When you lose, switch to the GameOver room. Press Play - lose to see it!",
    ["if self.dead:","    self.dead = False","    set_room('GameOver')"], play=True),
  S("GameOver","start","In the GameOver room, show a big white message.",
    ["t = text()","t.color = \"white\"","t.fontSize = 40","t.halign = \"center\"","t.text = 'GAME OVER - tap to play again'"]),
  SCORELINE(),
  S("GameOver","loop","Tap to play again: reset and go back to Play. Press Play!",
    ["if key_was_pressed(' ') or mouse_was_pressed('left'):","    Game.score = 0","    Game.lives = 3","    set_room('Play')"], play=True),
 ]})

# --- 7) PONG ---------------------------------------------------------------
GAMES.append({
 "title":"Pong","slug":"pong",
 "classes":["Game","Paddle","Cpu","Ball"], "rooms":["Play","GameOver"],
 "textures": tex({"paddle.png":"white","ball.png":"white"}),
 "steps":[
  S("Game","start","Set up: your score, the computer's score, then go to the Play room.",
    ["self.you = 0","self.cpu = 0","self.dead = False","self.restart = False","set_room('Play')"]),
  S("Paddle","start","Add a Class called Paddle - tall and thin, on the left.",
    ["self.image = sprite('paddle.png')","self.scaleX = 18","self.scaleY = 100","self.x = -340"]),
  S("Play","start","In the Play room, make your paddle. Press Play.",
    ["Game.paddle = Paddle()"], play=True),
  S("Paddle","loop","Make the paddle follow your mouse. Press Play and move it.",
    ["self.y = mouse_y()","if self.y > 220:","    self.y = 220","if self.y < -220:","    self.y = -220"], play=True),
  S("Ball","start","Add a Class called Ball with a size and a speed in X and Y.",
    ["self.image = sprite('ball.png')","self.scaleX = 18","self.scaleY = 18","self.speedX = 5","self.speedY = 3"]),
  S("Play","start","Make the ball. Press Play - it appears in the middle.",
    ["Game.ball = Ball()"], play=True),
  S("Ball","loop","Make the ball move. Press Play - it flies!",
    ["self.x = self.x + self.speedX","self.y = self.y + self.speedY"], play=True),
  S("Ball","loop","Bounce off the top and bottom. Press Play.",
    ["if self.y > 250 or self.y < -250:","    self.speedY = -self.speedY"], play=True),
  S("Ball","loop","Bounce off your paddle. Press Play - keep it in!",
    ["if get_collision(self, 'Paddle'):","    self.speedX = 5"], play=True),
  S("Cpu","start","Add a Class called Cpu - the computer's paddle, on the right.",
    ["self.image = sprite('paddle.png')","self.scaleX = 18","self.scaleY = 100","self.x = 340","self.followSpeed = 5"]),
  S("Play","start","Make the computer paddle. Press Play - it appears on the right.",
    ["Game.cpuPaddle = Cpu()"], play=True),
  S("Cpu","loop","Make the computer chase the ball. Press Play - it plays you!",
    ["ball = Game.ball","if self.y < ball.y - self.followSpeed:","    self.y = self.y + self.followSpeed",
     "if self.y > ball.y + self.followSpeed:","    self.y = self.y - self.followSpeed"], play=True),
  S("Ball","loop","Bounce off the computer paddle too. Press Play - rally!",
    ["if get_collision(self, 'Cpu'):","    self.speedX = -5"], play=True),
  S("Ball","loop","Score when the ball gets past a paddle, then reset it.",
    ["if self.x < -380:","    Game.cpu = Game.cpu + 1","    self.x = 0","if self.x > 380:","    Game.you = Game.you + 1","    self.x = 0"], play=True),
  S("Play","start","Add a white score label.",
    ["Game.label = text()","Game.label.color = \"white\"","Game.label.y = 230","Game.label.text = '0 : 0'"], play=True),
  S("Play","loop","Show the score, and when someone reaches 5, go to GameOver. Press Play.",
    ["Game.label.text = str(Game.you) + ' : ' + str(Game.cpu)","if Game.you > 4 or Game.cpu > 4:","    Game.dead = True"], play=True),
  S("Game","loop","When you lose, switch to the GameOver room. Press Play - lose to see it!",
    ["if self.dead:","    self.dead = False","    set_room('GameOver')"], play=True),
  S("GameOver","start","In the GameOver room, show a big white message.",
    ["t = text()","t.color = \"white\"","t.fontSize = 40","t.halign = \"center\"","t.text = 'GAME OVER - tap to play again'"]),
  SCORELINE("'You ' + str(Game.you) + '   Cpu ' + str(Game.cpu)"),
  S("GameOver","loop","Tap to play a new match. Press Play - first to 5 wins!",
    ["if key_was_pressed(' ') or mouse_was_pressed('left'):","    Game.you = 0","    Game.cpu = 0","    set_room('Play')"], play=True),
 ]})

# --- 8) BRICK BREAKER ------------------------------------------------------
GAMES.append({
 "title":"Brick Breaker","slug":"brick",
 "classes":["Game","Paddle","Ball","Brick"], "rooms":["Play","GameOver"],
 "textures": tex({"paddle.png":"blue","ball.png":"white","brick.png":"red"}),
 "steps":[
  S("Game","start","Set up: a score, 3 lives, then go to the Play room.",
    ["self.score = 0","self.lives = 3","self.dead = False","self.restart = False","set_room('Play')"]),
  S("Paddle","start","Add a Class called Paddle - wide and flat, near the bottom.",
    ["self.image = sprite('paddle.png')","self.scaleX = 120","self.scaleY = 18","self.y = -230"]),
  S("Play","start","In the Play room, make your paddle. Press Play.",
    ["Game.paddle = Paddle()"], play=True),
  S("Paddle","loop","Make the paddle follow your mouse, but stay on screen. Press Play.",
    ["self.x = mouse_x()","if self.x > 300:","    self.x = 300","if self.x < -300:","    self.x = -300"], play=True),
  S("Ball","start","Add a Class called Ball with a size and a speed in X and Y.",
    ["self.image = sprite('ball.png')","self.scaleX = 16","self.scaleY = 16","self.y = -120","self.speedX = 4","self.speedY = 5"]),
  S("Play","start","Make the ball. Press Play - it appears.",
    ["Game.ball = Ball()"], play=True),
  S("Ball","loop","Make the ball move. Press Play - it flies!",
    ["self.x = self.x + self.speedX","self.y = self.y + self.speedY"], play=True),
  S("Ball","loop","Bounce off the walls and the top. Press Play.",
    ["if self.x > 360 or self.x < -360:","    self.speedX = -self.speedX","if self.y > 260:","    self.speedY = -self.speedY"], play=True),
  S("Ball","loop","Bounce off the paddle. Press Play - keep it up!",
    ["if get_collision(self, 'Paddle'):","    self.speedY = 5"], play=True),
  S("Ball","loop","Miss = lose a life. At 0 lives, go to GameOver. Press Play - don't miss!",
    ["if self.y < -280:","    Game.lives = Game.lives - 1","    self.x = 0","    self.y = -120","    if Game.lives < 1:","        Game.dead = True"], play=True),
  S("Brick","start","Add a Class called Brick. It lines itself up with a row and column counter.",
    ["self.image = sprite('brick.png')","self.scaleX = 56","self.scaleY = 20",
     "self.x = -250 + Game.brickCol * 92","self.y = 200 - Game.brickRow * 40"]),
  S("Brick","start","Move to the next column, and start a new row after six.",
    ["Game.brickCol = Game.brickCol + 1","if Game.brickCol > 5:","    Game.brickCol = 0","    Game.brickRow = Game.brickRow + 1"]),
  S("Play","start","Start the counters and how many bricks are left.",
    ["Game.brickCol = 0","Game.brickRow = 0","Game.bricksLeft = 12"]),
  S("Play","start","Make the first row of six bricks. Press Play - one row appears!",
    ["b1 = Brick()","b2 = Brick()","b3 = Brick()","b4 = Brick()","b5 = Brick()","b6 = Brick()"], play=True),
  S("Play","start","Make the second row of six bricks. Press Play - a wall of bricks!",
    ["b7 = Brick()","b8 = Brick()","b9 = Brick()","b10 = Brick()","b11 = Brick()","b12 = Brick()"], play=True),
  S("Ball","loop","Break a brick when the ball hits it, score, and count it down. Press Play!",
    ["hitBrick = get_collision(self, 'Brick')","if hitBrick:","    self.speedY = -self.speedY","    destroy(hitBrick)",
     "    Game.score = Game.score + 1","    Game.bricksLeft = Game.bricksLeft - 1"], play=True),
  S("Play","start","Add a white label for score and lives.",
    ["Game.label = text()","Game.label.color = \"white\"","Game.label.y = 235","Game.label.text = 'Score: 0'"], play=True),
  S("Play","loop","Update the label, and if all bricks are gone, go to GameOver. Press Play!",
    ["Game.label.text = 'Score: ' + str(Game.score) + '   Lives: ' + str(Game.lives)","if Game.bricksLeft == 0:","    Game.dead = True"], play=True),
  S("Game","loop","When you lose, switch to the GameOver room. Press Play - lose to see it!",
    ["if self.dead:","    self.dead = False","    set_room('GameOver')"], play=True),
  S("GameOver","start","In the GameOver room, show WIN if you cleared every brick, otherwise GAME OVER.",
    ["t = text()","t.color = \"white\"","t.fontSize = 40","t.halign = \"center\"",
     "if Game.bricksLeft == 0:","    t.text = 'YOU WIN! - tap to play again'",
     "if Game.bricksLeft > 0:","    t.text = 'GAME OVER - tap to play again'"]),
  SCORELINE(),
  S("GameOver","loop","Tap to play again: reset and go back to Play. Press Play - clear them all!",
    ["if key_was_pressed(' ') or mouse_was_pressed('left'):","    Game.score = 0","    Game.lives = 3","    set_room('Play')"], play=True),
 ]})

# --- 9) DOODLE JUMP --------------------------------------------------------
GAMES.append({
 "title":"Doodle Jump","slug":"doodle",
 "classes":["Game","Bg","Platform","Player"], "rooms":["Play","GameOver"],
 "textures": tex({"player.png":"green","platform.png":"gray","sky.png":"dark"}),
 "steps":[
  S("Game","start","Set up: a score, 3 lives, then go to the Play room.",
    ["self.score = 0","self.lives = 3","self.dead = False","self.restart = False","set_room('Play')"]),
  S("Bg","start","Add a Class called Bg - the dark background.",
    ["self.image = sprite('sky.png')","self.scaleX = 760","self.scaleY = 560","self.z = -10"]),
  S("Play","start","In the Play room, make the background. Press Play.",
    ["Game.bg = Bg()"], play=True),
  S("Player","start","Add a Class called Player: gravity, a bounce strength, a move speed, a picture and size.",
    ["self.gravity = 0.5","self.bounceStrength = 13","self.moveSpeed = 6","self.image = sprite('player.png')","self.scaleX = 34","self.scaleY = 34"]),
  S("Player","start","Start the player in the middle, not moving yet.",
    ["self.y = -150","self.speedY = 0"]),
  S("Play","start","Make your player. Press Play - it falls (we'll catch it next!).",
    ["Game.player = Player()"], play=True),
  S("Player","loop","Gravity pulls down, and the arrows move you. Press Play - move left and right.",
    ["self.speedY = self.speedY - self.gravity",
     "if key_is_pressed('arrowLeft') or key_is_pressed('a'): self.x = self.x - self.moveSpeed",
     "if key_is_pressed('arrowRight') or key_is_pressed('d'): self.x = self.x + self.moveSpeed",
     "self.y = self.y + self.speedY"], play=True),
  S("Platform","start","Add a Class called Platform: a size, stacked using a counter.",
    ["import random","self.image = sprite('platform.png')","self.scaleX = 80","self.scaleY = 16","self.y = -240 + Game.platformCount * 70"]),
  S("Platform","start","Put the first platform under the player, the rest in random spots.",
    ["if Game.platformCount == 0:","    self.x = 0","else:","    self.x = random.randint(-320, 320)","Game.platformCount = Game.platformCount + 1"]),
  S("Play","start","Start the counter, then make six platforms. Press Play - platforms appear!",
    ["Game.platformCount = 0","p1 = Platform()","p2 = Platform()","p3 = Platform()","p4 = Platform()","p5 = Platform()"], play=True),
  S("Play","start","Add one more platform up high.",
    ["p6 = Platform()"], play=True),
  S("Platform","loop","Make the platforms slide down and come back to the top. Press Play.",
    ["import random","self.y = self.y - 2","if self.y < -280:","    self.y = self.y + 420","    self.x = random.randint(-320, 320)"], play=True),
  S("Player","loop","Bounce when you land on a platform, and score. Press Play - boing!",
    ["if self.speedY < 0 and get_collision(self, 'Platform'):","    self.speedY = self.bounceStrength","    Game.score = Game.score + 1"], play=True),
  S("Player","loop","Wrap around the sides.",
    ["if self.x < -360: self.x = 360","if self.x > 360: self.x = -360"]),
  S("Player","loop","Fall off the bottom = lose a life. At 0 lives, go to GameOver. Press Play!",
    ["if self.y < -270:","    Game.lives = Game.lives - 1","    self.y = -150","    self.speedY = self.bounceStrength","    if Game.lives < 1:","        Game.dead = True"], play=True),
  S("Play","start","Add a white label for score and lives.",
    ["Game.label = text()","Game.label.color = \"white\"","Game.label.y = 250","Game.label.text = 'Score: 0'"], play=True),
  S("Play","loop","Keep the label updated. Press Play.",
    ["Game.label.text = 'Score: ' + str(Game.score) + '   Lives: ' + str(Game.lives)"], play=True),
  S("Game","loop","When you lose, switch to the GameOver room. Press Play - lose to see it!",
    ["if self.dead:","    self.dead = False","    set_room('GameOver')"], play=True),
  S("GameOver","start","In the GameOver room, show a big white message.",
    ["t = text()","t.color = \"white\"","t.fontSize = 40","t.halign = \"center\"","t.text = 'GAME OVER - tap to play again'"]),
  SCORELINE(),
  S("GameOver","loop","Tap to play again: reset and go back to Play. Press Play - climb high!",
    ["if key_was_pressed(' ') or mouse_was_pressed('left'):","    Game.score = 0","    Game.lives = 3","    set_room('Play')"], play=True),
 ]})

# ===========================================================================
# 11 MORE GAMES (share the same room-based game-over via GO())
# ===========================================================================
def GO():
    return [
      S("Game","loop","When you lose, the game switches to the GameOver room. Press Play - lose to see it!",
        ["if self.dead:","    self.dead = False","    set_room('GameOver')"], play=True),
      S("GameOver","start","In the GameOver room, show a big white message in the middle.",
        ["t = text()","t.color = \"white\"","t.fontSize = 40","t.halign = \"center\"","t.text = 'GAME OVER - tap to play again'"]),
      SCORELINE(),
      S("GameOver","loop","Tap to play again: reset and go back to Play. Press Play - lose, then retry!",
        ["if key_was_pressed(' ') or mouse_was_pressed('left'):","    Game.score = 0","    Game.lives = 3","    set_room('Play')"], play=True),
    ]

# 10) SPACE SHOOTER
GAMES.append({
 "title":"Space Shooter","slug":"shooter","classes":["Game","Bg","Player","Bullet","Alien"],"rooms":["Play","GameOver"],
 "textures": tex({"ship.png":"blue","bullet.png":"white","alien.png":"red","space.png":"dark"}),
 "steps":[
  S("Game","start","Set up: a score, 3 lives, then go to the Play room.",
    ["self.score = 0","self.lives = 3","self.dead = False","set_room('Play')"]),
  S("Bg","start","Add a Class called Bg - the dark space background.",
    ["self.image = sprite('space.png')","self.scaleX = 760","self.scaleY = 560","self.z = -10"]),
  S("Play","start","In the Play room, make the background. Press Play.",["Game.bg = Bg()"], play=True),
  S("Player","start","Add a Class called Player - your ship at the bottom.",
    ["self.image = sprite('ship.png')","self.scaleX = 46","self.scaleY = 24","self.x = 0","self.y = -210"]),
  S("Play","start","Make your ship. Press Play - it appears.",["Game.player = Player()"], play=True),
  S("Player","loop","Move left and right with the arrows. Press Play - fly around!",
    ["if key_is_pressed('arrowLeft') or key_is_pressed('a'): self.x = self.x - 6",
     "if key_is_pressed('arrowRight') or key_is_pressed('d'): self.x = self.x + 6",
     "if self.x < -340: self.x = -340","if self.x > 340: self.x = 340"], play=True),
  S("Bullet","start","Add a Class called Bullet - a little laser.",
    ["self.image = sprite('bullet.png')","self.scaleX = 6","self.scaleY = 16"]),
  S("Player","loop","Press Space to shoot a bullet. Press Play - pew pew!",
    ["if key_was_pressed(' ') or mouse_was_pressed('left'):","    b = Bullet()","    b.x = self.x","    b.y = self.y + 20"], play=True),
  S("Bullet","loop","Make the bullet fly up and disappear at the top. Press Play.",
    ["self.y = self.y + 10","if self.y > 280:","    destroy(self)"], play=True),
  S("Alien","start","Add a Class called Alien up at the top, at a random spot.",
    ["import random","self.image = sprite('alien.png')","self.scaleX = 38","self.scaleY = 28",
     "self.x = random.randint(-300, 300)","self.y = 280"]),
  S("Play","start","Make two aliens. Press Play - invaders!",["Game.alienA = Alien()","Game.alienB = Alien()"], play=True),
  S("Bullet","loop","Hit an alien: score a point and send it back to the top. Press Play - shoot them!",
    ["import random","hitAlien = get_collision(self, 'Alien')","if hitAlien:","    Game.score = Game.score + 1",
     "    hitAlien.y = 280","    destroy(self)"], play=True),
  S("Alien","loop","Aliens drift down. If one reaches the bottom, lose a life. Press Play - defend!",
    ["import random","self.y = self.y - 2","if self.y < -240:","    Game.lives = Game.lives - 1","    self.y = 280",
     "    if Game.lives < 1:","        Game.dead = True"], play=True),
  S("Play","start","Add a white label for score and lives.",
    ["Game.label = text()","Game.label.color = \"white\"","Game.label.y = 230","Game.label.text = 'Score: 0'"], play=True),
  S("Play","loop","Keep the label updated. Press Play.",
    ["Game.label.text = 'Score: ' + str(Game.score) + '   Lives: ' + str(Game.lives)"], play=True),
 ] + GO()})

# 11) HELICOPTER
GAMES.append({
 "title":"Helicopter","slug":"heli","classes":["Game","Bg","Heli","Wall"],"rooms":["Play","GameOver"],
 "textures": tex({"heli.png":"yellow","wall.png":"green","sky.png":"cyan"}),
 "steps":[
  S("Game","start","Set up: a score, 3 lives, then go to the Play room.",
    ["self.score = 0","self.lives = 3","self.dead = False","set_room('Play')"]),
  S("Bg","start","Add a Class called Bg - the sky.",
    ["self.image = sprite('sky.png')","self.scaleX = 760","self.scaleY = 560","self.z = -10"]),
  S("Play","start","In the Play room, make the sky. Press Play.",["Game.bg = Bg()"], play=True),
  S("Heli","start","Add a Class called Heli: a picture, a size, a speed, and gravity.",
    ["self.image = sprite('heli.png')","self.scaleX = 44","self.scaleY = 24","self.x = -120","self.speedY = 0","self.gravity = 0.5"]),
  S("Play","start","Make your helicopter. Press Play - it falls.",["Game.heli = Heli()"], play=True),
  S("Heli","loop","Gravity pulls down; HOLD Space to rise. Press Play - hold to fly!",
    ["self.speedY = self.speedY - self.gravity","if key_is_pressed(' ') or mouse_is_pressed('left'):","    self.speedY = self.speedY + 1",
     "self.y = self.y + self.speedY"], play=True),
  S("Heli","loop","If you hit the top or bottom, lose a life and recenter. Press Play - stay in the air!",
    ["if self.y < -250 or self.y > 250:","    Game.lives = Game.lives - 1","    self.y = 0","    self.speedY = 0",
     "    if Game.lives < 1:","        Game.dead = True"], play=True),
  S("Wall","start","Add a Class called Wall - a green block to dodge, starting at the right.",
    ["import random","self.image = sprite('wall.png')","self.scaleX = 50","self.scaleY = 120",
     "self.x = 400","self.y = random.randint(-180, 180)"]),
  S("Play","start","Make two walls. Press Play - obstacles!",["Game.wallA = Wall()","Game.wallB = Wall()"], play=True),
  S("Wall","loop","Move the walls left, then send them back with a new height.",
    ["import random","self.x = self.x - 5","if self.x < -400:","    self.x = 400","    self.y = random.randint(-180, 180)"], play=True),
  S("Wall","loop","If a wall hits the helicopter, lose a life. Press Play - dodge!",
    ["if get_collision(self, 'Heli'):","    Game.lives = Game.lives - 1","    self.x = 400","    if Game.lives < 1:","        Game.dead = True"], play=True),
  S("Wall","loop","Score a point each time a wall passes you.",
    ["if self.x < -160 and self.x > -170:","    Game.score = Game.score + 1"], play=True),
  S("Play","start","Add a white label for score and lives.",
    ["Game.label = text()","Game.label.color = \"white\"","Game.label.y = 240","Game.label.text = 'Score: 0'"], play=True),
  S("Play","loop","Keep the label updated. Press Play.",
    ["Game.label.text = 'Score: ' + str(Game.score) + '   Lives: ' + str(Game.lives)"], play=True),
 ] + GO()})

# 12) FRUIT SLICE
GAMES.append({
 "title":"Fruit Slice","slug":"slice","classes":["Game","Bg","Fruit"],"rooms":["Play","GameOver"],
 "textures": tex({"fruit.png":"red","bg.png":"dgreen"}),
 "steps":[
  S("Game","start","Set up: a score, 3 lives, then go to the Play room.",
    ["self.score = 0","self.lives = 3","self.dead = False","set_room('Play')"]),
  S("Bg","start","Add a Class called Bg - the background.",
    ["self.image = sprite('bg.png')","self.scaleX = 760","self.scaleY = 560","self.z = -10"]),
  S("Play","start","In the Play room, make the background. Press Play.",["Game.bg = Bg()"], play=True),
  S("Fruit","start","Add a Class called Fruit that shoots up from the bottom with a random toss.",
    ["import random","self.image = sprite('fruit.png')","self.scaleX = 34","self.scaleY = 34",
     "self.x = random.randint(-260, 260)","self.y = -240","self.speedY = random.randint(13, 19)"]),
  S("Play","start","Make three fruits. Press Play - they fly up!",
    ["Game.fruitA = Fruit()","Game.fruitB = Fruit()","Game.fruitC = Fruit()"], play=True),
  S("Fruit","loop","Gravity slows the fruit and pulls it back down. Press Play - watch the arc!",
    ["self.speedY = self.speedY - 0.4","self.y = self.y + self.speedY"], play=True),
  S("Fruit","loop","Slice it! Click on the fruit to score and toss a new one. Press Play - slice!",
    ["import random","near = mouse_x() > self.x - 38 and mouse_x() < self.x + 38","close = mouse_y() > self.y - 38 and mouse_y() < self.y + 38",
     "if mouse_was_pressed('left') and near and close:","    Game.score = Game.score + 1","    self.y = -240","    self.x = random.randint(-260, 260)","    self.speedY = random.randint(13, 19)"], play=True),
  S("Fruit","loop","Miss a fruit and it falls off the bottom = lose a life. Press Play - don't miss!",
    ["import random","if self.y < -260:","    Game.lives = Game.lives - 1","    self.y = -240","    self.speedY = random.randint(13, 19)",
     "    if Game.lives < 1:","        Game.dead = True"], play=True),
  S("Play","start","Add a white label for score and lives.",
    ["Game.label = text()","Game.label.color = \"white\"","Game.label.y = 240","Game.label.text = 'Score: 0'"], play=True),
  S("Play","loop","Keep the label updated. Press Play.",
    ["Game.label.text = 'Score: ' + str(Game.score) + '   Lives: ' + str(Game.lives)"], play=True),
 ] + GO()})


# 14) ASTEROID DODGE
GAMES.append({
 "title":"Asteroid Dodge","slug":"dodge","classes":["Game","Bg","Ship","Rock"],"rooms":["Play","GameOver"],
 "textures": tex({"ship.png":"blue","rock.png":"gray","space.png":"dark"}),
 "steps":[
  S("Game","start","Set up: a score, 3 lives, then go to the Play room.",
    ["self.score = 0","self.lives = 3","self.dead = False","set_room('Play')"]),
  S("Bg","start","Add a Class called Bg - dark space.",
    ["self.image = sprite('space.png')","self.scaleX = 760","self.scaleY = 560","self.z = -10"]),
  S("Play","start","In the Play room, make space. Press Play.",["Game.bg = Bg()"], play=True),
  S("Ship","start","Add a Class called Ship - a picture and size.",
    ["self.image = sprite('ship.png')","self.scaleX = 40","self.scaleY = 40"]),
  S("Play","start","Make your ship. Press Play - it appears.",["Game.ship = Ship()"], play=True),
  S("Ship","loop","Make the ship follow your mouse anywhere. Press Play - fly with your mouse!",
    ["self.x = mouse_x()","self.y = mouse_y()"], play=True),
  S("Rock","start","Add a Class called Rock that flies in from the right at a random height.",
    ["import random","self.image = sprite('rock.png')","self.scaleX = 44","self.scaleY = 44",
     "self.x = 400","self.y = random.randint(-240, 240)"]),
  S("Play","start","Make three rocks. Press Play - here they come!",
    ["Game.rockA = Rock()","Game.rockB = Rock()","Game.rockC = Rock()"], play=True),
  S("Rock","loop","Fly the rocks left; send them back with a new height, and score. Press Play - dodge!",
    ["import random","self.x = self.x - 6","if self.x < -400:","    Game.score = Game.score + 1","    self.x = 400","    self.y = random.randint(-240, 240)"], play=True),
  S("Rock","loop","If a rock hits your ship = lose a life. Press Play - don't get hit!",
    ["if get_collision(self, 'Ship'):","    Game.lives = Game.lives - 1","    self.x = 400","    if Game.lives < 1:","        Game.dead = True"], play=True),
  S("Play","start","Add a white label for score and lives.",
    ["Game.label = text()","Game.label.color = \"white\"","Game.label.y = 250","Game.label.text = 'Score: 0'"], play=True),
  S("Play","loop","Keep the label updated. Press Play.",
    ["Game.label.text = 'Score: ' + str(Game.score) + '   Lives: ' + str(Game.lives)"], play=True),
 ] + GO()})





# 19) STACK TOWER
GAMES.append({
 "title":"Stack Tower","slug":"stack","classes":["Game","Mover","Slab"],"rooms":["Play","GameOver"],
 "textures": tex({"block.png":"orange","slab.png":"blue"}),
 "steps":[
  S("Game","start","Set up: a score, 3 lives, then go to Play.",
    ["self.score = 0","self.lives = 3","self.dead = False","set_room('Play')"]),
  S("Mover","start","Add a Class called Mover - a block that slides at the top.",
    ["self.image = sprite('block.png')","self.scaleX = 90","self.scaleY = 24","self.x = -250","self.y = 200","self.moveSpeed = 5"]),
  S("Play","start","In the Play room, set where the last block landed, the pile height, the block width (1 = full), and make the slider. Press Play!",
    ["Game.lastX = 0","Game.pileY = -200","Game.blockW = 1.0","Game.mover = Mover()"], play=True),
  S("Mover","loop","Slide left and right, and shrink to the current block width. Press Play - back and forth!",
    ["self.x = self.x + self.moveSpeed","self.scaleX = Game.blockW","if self.x > 250:","    self.moveSpeed = -5","if self.x < -250:","    self.moveSpeed = 5"], play=True),
  S("Slab","start","Add a Class called Slab. It takes the current width, then makes the NEXT block a bit smaller.",
    ["self.image = sprite('slab.png')","self.scaleX = 90","self.scaleY = 24","self.scaleX = Game.blockW","Game.blockW = Game.blockW - 0.06"]),
  S("Mover","loop","Tap to drop! If it lines up with the last block, stack it and score. Press Play - tap!",
    ["if mouse_was_pressed('left') or key_was_pressed(' '):","    near = self.x - Game.lastX < 60 and self.x - Game.lastX > -60",
     "    if near:","        s = Slab()","        s.x = self.x","        s.y = Game.pileY"], play=True),
  S("Mover","loop","When you stack well, remember it, raise the pile, and add a point.",
    ["if mouse_was_pressed('left') or key_was_pressed(' '):","    near2 = self.x - Game.lastX < 60 and self.x - Game.lastX > -60",
     "    if near2:","        Game.lastX = self.x","        Game.pileY = Game.pileY + 24","        Game.score = Game.score + 1"], play=True),
  S("Mover","loop","If you tap and miss the line-up = lose a life. Press Play - stack carefully!",
    ["if mouse_was_pressed('left') or key_was_pressed(' '):","    far = self.x - Game.lastX > 60 or self.x - Game.lastX < -60",
     "    if far:","        Game.lives = Game.lives - 1","        if Game.lives < 1:","            Game.dead = True"], play=True),
  S("Play","start","Add a white label for score and lives.",
    ["Game.label = text()","Game.label.color = \"white\"","Game.label.y = 250","Game.label.text = 'Score: 0'"], play=True),
  S("Play","loop","Keep the label updated. Press Play.",
    ["Game.label.text = 'Score: ' + str(Game.score) + '   Lives: ' + str(Game.lives)"], play=True),
 ] + GO()})



# 16) FISHING
GAMES.append({
 "title":"Fishing","slug":"fishing","classes":["Game","Sea","Boat","Hook","Fish","Boot"],"rooms":["Play","GameOver"],
 "textures": tex({"boat.png":"brown","hook.png":"gray","fish.png":"orange","boot.png":"dark","sea.png":"cyan"}),
 "steps":[
  S("Game","start","Set up: a score, 3 lives, then go to Play.",["self.score = 0","self.lives = 3","self.dead = False","set_room('Play')"]),
  S("Sea","start","Add a Class called Sea - the water.",["self.image = sprite('sea.png')","self.scaleX = 760","self.scaleY = 560","self.z = -10"]),
  S("Play","start","In the Play room, make the sea. Press Play.",["Game.sea = Sea()"], play=True),
  S("Boat","start","Add a Class called Boat at the top.",["self.image = sprite('boat.png')","self.scaleX = 110","self.scaleY = 34","self.y = 240"]),
  S("Play","start","Make the boat. Press Play.",["Game.boat = Boat()"], play=True),
  S("Hook","start","Add a Class called Hook hanging in the water.",["self.image = sprite('hook.png')","self.scaleX = 16","self.scaleY = 22","self.x = 0","self.y = 180"]),
  S("Play","start","Make the hook. Press Play.",["Game.hook = Hook()"], play=True),
  S("Hook","loop","HOLD Space to lower the hook; let go to raise it. Press Play - go fishing!",
    ["if key_is_pressed(' ') or mouse_is_pressed('left'):","    self.y = self.y - 4","else:","    self.y = self.y + 4","if self.y > 180: self.y = 180","if self.y < -240: self.y = -240"], play=True),
  S("Fish","start","Add a Class called Fish swimming in from the left at a random depth.",
    ["import random","self.image = sprite('fish.png')","self.scaleX = 44","self.scaleY = 24",
     "self.x = -380","self.y = random.randint(-220, 130)","self.speed = random.randint(2, 5)"]),
  S("Play","start","Make two fish. Press Play - fish swim by!",["Game.fishA = Fish()","Game.fishB = Fish()"], play=True),
  S("Fish","loop","Swim the fish across; catch one on your hook to score. Press Play - reel them in!",
    ["self.x = self.x + self.speed","if self.x > 380: self.x = -380","if get_collision(self, 'Hook'):","    Game.score = Game.score + 1","    self.x = -380"], play=True),
  S("Boot","start","Add a Class called Boot - junk swimming the other way.",
    ["import random","self.image = sprite('boot.png')","self.scaleX = 34","self.scaleY = 40","self.x = 380","self.y = random.randint(-220, 60)"]),
  S("Play","start","Make one boot. Press Play - watch out for junk!",["Game.boot = Boot()"], play=True),
  S("Boot","loop","Move the boot the other way.",["self.x = self.x - 3","if self.x < -380: self.x = 380"], play=True),
  S("Boot","loop","Hook a boot by mistake = lose a life. Press Play - only catch fish!",
    ["if get_collision(self, 'Hook'):","    Game.lives = Game.lives - 1","    self.x = 380","    if Game.lives < 1:","        Game.dead = True"], play=True),
  S("Play","start","Add a white label.",["Game.label = text()","Game.label.color = \"white\"","Game.label.y = 250","Game.label.text = 'Score: 0'"], play=True),
  S("Play","loop","Keep the label updated. Press Play.",["Game.label.text = 'Score: ' + str(Game.score) + '   Lives: ' + str(Game.lives)"], play=True),
 ] + GO()})

# 17) RHYTHM TAP
GAMES.append({
 "title":"Rhythm Tap","slug":"rhythm","classes":["Game","Bg","Line","Note"],"rooms":["Play","GameOver"],
 "textures": tex({"line.png":"white","note.png":"purple","bg.png":"dark"}),
 "steps":[
  S("Game","start","Set up: a score, 3 lives, then go to Play.",["self.score = 0","self.lives = 3","self.dead = False","set_room('Play')"]),
  S("Bg","start","Add a Class called Bg.",["self.image = sprite('bg.png')","self.scaleX = 760","self.scaleY = 560","self.z = -10"]),
  S("Play","start","In the Play room, make the background. Press Play.",["Game.bg = Bg()"], play=True),
  S("Line","start","Add a Class called Line - the white hit-line near the bottom.",["self.image = sprite('line.png')","self.scaleX = 700","self.scaleY = 6","self.y = -175"]),
  S("Play","start","Make the hit-line. Press Play.",["Game.line = Line()"], play=True),
  S("Note","start","Add a Class called Note that starts up high (spread them out).",
    ["import random","self.image = sprite('note.png')","self.scaleX = 70","self.scaleY = 24","self.x = 0","self.y = random.randint(280, 560)"]),
  S("Play","start","Make three notes. Press Play - notes appear!",["Game.noteA = Note()","Game.noteB = Note()","Game.noteC = Note()"], play=True),
  S("Note","loop","Make the notes fall toward the line. Press Play - here they come!",["self.y = self.y - 5"], play=True),
  S("Note","loop","Tap Space when a note is on the line to score. Press Play - tap to the beat!",
    ["atLine = self.y < -150 and self.y > -200","if atLine and (key_was_pressed(' ') or mouse_was_pressed('left')):","    Game.score = Game.score + 1","    self.y = 300"], play=True),
  S("Note","loop","Miss a note (it falls past) = lose a life. Press Play - don't miss the beat!",
    ["if self.y < -250:","    Game.lives = Game.lives - 1","    self.y = 300","    if Game.lives < 1:","        Game.dead = True"], play=True),
  S("Play","start","Add a white label.",["Game.label = text()","Game.label.color = \"white\"","Game.label.y = 240","Game.label.text = 'Score: 0'"], play=True),
  S("Play","loop","Keep the label updated. Press Play.",["Game.label.text = 'Score: ' + str(Game.score) + '   Lives: ' + str(Game.lives)"], play=True),
 ] + GO()})

# 18) LANDER
GAMES.append({
 "title":"Lander","slug":"lander","classes":["Game","Bg","Pad","Rocket"],"rooms":["Play","GameOver"],
 "textures": tex({"rocket.png":"orange","pad.png":"green","bg.png":"dark"}),
 "steps":[
  S("Game","start","Set up: a score, 3 lives, then go to Play.",["self.score = 0","self.lives = 3","self.dead = False","set_room('Play')"]),
  S("Bg","start","Add a Class called Bg - dark space.",["self.image = sprite('bg.png')","self.scaleX = 760","self.scaleY = 560","self.z = -10"]),
  S("Play","start","In the Play room, make space. Press Play.",["Game.bg = Bg()"], play=True),
  S("Pad","start","Add a Class called Pad - the landing pad at the bottom.",["self.image = sprite('pad.png')","self.scaleX = 170","self.scaleY = 20","self.y = -190"]),
  S("Play","start","Make the pad. Press Play.",["Game.pad = Pad()"], play=True),
  S("Rocket","start","Add a Class called Rocket up high, with gravity.",
    ["self.gravity = 0.15","self.image = sprite('rocket.png')","self.scaleX = 30","self.scaleY = 46","self.x = 0","self.y = 200","self.speedY = 0"]),
  S("Play","start","Make your rocket. Press Play - it falls.",["Game.rocket = Rocket()"], play=True),
  S("Rocket","loop","Gravity pulls down; HOLD Space to fire the thruster up. Press Play - slow your fall!",
    ["self.speedY = self.speedY - self.gravity","if key_is_pressed(' ') or mouse_is_pressed('left'):","    self.speedY = self.speedY + 0.4","self.y = self.y + self.speedY"], play=True),
  S("Play","start","Add a speed meter - a label that warns you when you fall too fast.",
    ["Game.meter = text()","Game.meter.y = 150","Game.meter.color = \"lime\"","Game.meter.text = 'Speed OK'"], play=True),
  S("Rocket","loop","Turn the meter RED when you drop too fast (faster than -3). Press Play - watch the warning!",
    ["if self.speedY < -3:","    Game.meter.text = 'TOO FAST!'","    Game.meter.color = \"red\"","if self.speedY > -3:","    Game.meter.text = 'Speed OK'","    Game.meter.color = \"lime\""], play=True),
  S("Rocket","loop","Land slow and gentle to score a point. Press Play - touch down softly!",
    ["if self.y < -170 and self.speedY > -3:","    Game.score = Game.score + 1","    self.y = 200","    self.speedY = 0"], play=True),
  S("Rocket","loop","Come down too fast and you CRASH = lose a life. Press Play - easy does it!",
    ["if self.y < -170 and self.speedY < -3:","    Game.lives = Game.lives - 1","    self.y = 200","    self.speedY = 0","    if Game.lives < 1:","        Game.dead = True"], play=True),
  S("Play","start","Add a white label.",["Game.label = text()","Game.label.color = \"white\"","Game.label.y = 250","Game.label.text = 'Score: 0'"], play=True),
  S("Play","loop","Keep the label updated. Press Play.",["Game.label.text = 'Score: ' + str(Game.score) + '   Lives: ' + str(Game.lives)"], play=True),
 ] + GO()})



# 18) PLATFORMER (Jump Quest) - two levels, each level is its own room
GAMES.append({
 "title":"Platformer","slug":"platformer","classes":["Game","Sky","Hero","Platform","Goal"],"rooms":["Level1","Level2","GameOver"],
 "textures": tex({"hero.png":"green","platform.png":"brown","goal.png":"yellow","sky.png":"cyan"}),
 "steps":[
  S("Game","start","Set up: a score, 3 lives, then go to the first level.",
    ["self.score = 0","self.lives = 3","self.dead = False","set_room('Level1')"]),
  S("Sky","start","Add a Class called Sky.",["self.image = sprite('sky.png')","self.scaleX = 760","self.scaleY = 560","self.z = -10"]),
  S("Level1","start","Level1 is a room - your first level! Make the sky. Press Play.",["Game.sky = Sky()"], play=True),
  S("Hero","start","Add a Class called Hero with gravity, a jump strength, a picture and size.",
    ["self.gravity = 0.7","self.jumpStrength = 15","self.image = sprite('hero.png')","self.scaleX = 34","self.scaleY = 40"]),
  S("Hero","start","Start the hero on the left, not moving yet.",["self.x = -280","self.y = 0","self.speedY = 0","self.onGround = False"]),
  S("Level1","start","Make your hero. Press Play - it falls (platforms are next!).",["Game.hero = Hero()"], play=True),
  S("Hero","loop","Gravity pulls down; tap Space to jump when on a platform. Press Play.",
    ["self.speedY = self.speedY - self.gravity","if key_was_pressed(' ') and self.onGround:","    self.speedY = self.jumpStrength","self.y = self.y + self.speedY","self.onGround = False"], play=True),
  S("Hero","loop","Move left and right with the arrows. Press Play - run!",
    ["if key_is_pressed('arrowLeft') or key_is_pressed('a'): self.x = self.x - 5","if key_is_pressed('arrowRight') or key_is_pressed('d'): self.x = self.x + 5"], play=True),
  S("Hero","loop","Land on top of a platform. 'hitPlat' is the platform you touched - snap onto it so you don't sink through. Press Play.",
    ["hitPlat = get_collision(self, 'Platform')","if self.speedY < 0 and hitPlat:","    self.y = hitPlat.y + 28","    self.speedY = 0","    self.onGround = True"], play=True),
  S("Platform","start","Add a Class called Platform - just the picture and size. We place each one in the level.",
    ["self.image = sprite('platform.png')","self.scaleX = 120","self.scaleY = 20"]),
  S("Level1","start","Place two platforms - give each one its own x and y. Press Play - stand on them!",
    ["Game.p1 = Platform()","Game.p1.x = -280","Game.p1.y = -150","Game.p2 = Platform()","Game.p2.x = -100","Game.p2.y = -90"], play=True),
  S("Goal","start","Add a Class called Goal - the flag you run to.",["self.image = sprite('goal.png')","self.scaleX = 30","self.scaleY = 60"]),
  S("Level1","start","Place the last platform and the goal flag on top of it. Press Play.",
    ["Game.p3 = Platform()","Game.p3.x = 90","Game.p3.y = -30","Game.goal = Goal()","Game.goal.x = 90","Game.goal.y = 10"], play=True),
  S("Hero","loop","Fall off the bottom = lose a life and go back to the start. Press Play - careful!",
    ["if self.y < -260:","    Game.lives = Game.lives - 1","    self.x = -280","    self.y = 0","    if Game.lives < 1: Game.dead = True"], play=True),
  S("Level1","start","Say which room comes next, and add a white label. Press Play.",
    ["Game.nextLevel = 'Level2'","Game.label = text()","Game.label.color = \"white\"","Game.label.y = 250","Game.label.text = 'Level 1'"], play=True),
  S("Hero","loop","Touch the flag to score and go to the next level. Press Play - reach the flag!",
    ["if get_collision(self, 'Goal'):","    Game.score = Game.score + 1","    set_room(Game.nextLevel)"], play=True),
  S("Level1","loop","Keep the Level 1 label updated. Press Play.",
    ["Game.label.text = 'Level 1   Score: ' + str(Game.score) + '   Lives: ' + str(Game.lives)"], play=True),
  S("Level2","start","Level2 is ANOTHER room - that is how you add a level! Make the sky and hero. Press Play - finish Level 1 to see it!",
    ["Game.sky = Sky()","Game.hero = Hero()"], play=True),
  S("Level2","start","Place different platforms - a flat jump across a gap this time. Press Play.",
    ["Game.p1 = Platform()","Game.p1.x = -280","Game.p1.y = -120","Game.p2 = Platform()","Game.p2.x = -90","Game.p2.y = -120"], play=True),
  S("Level2","start","Place the last platform up high, with the goal on it. Press Play.",
    ["Game.p3 = Platform()","Game.p3.x = 110","Game.p3.y = -50","Game.goal = Goal()","Game.goal.x = 110","Game.goal.y = -10"], play=True),
  S("Level2","start","After Level 2, loop back to Level 1. Add the label. Press Play.",
    ["Game.nextLevel = 'Level1'","Game.label = text()","Game.label.color = \"white\"","Game.label.y = 250","Game.label.text = 'Level 2'"], play=True),
  S("Level2","loop","Keep the Level 2 label updated. Press Play.",
    ["Game.label.text = 'Level 2   Score: ' + str(Game.score) + '   Lives: ' + str(Game.lives)"], play=True),
  S("Game","loop","When you run out of lives, switch to the GameOver room. Press Play.",
    ["if self.dead:","    self.dead = False","    set_room('GameOver')"], play=True),
  S("GameOver","start","In the GameOver room, show a big white message.",
    ["t = text()","t.color = \"white\"","t.fontSize = 40","t.halign = \"center\"","t.text = 'GAME OVER - tap to play again'"]),
  SCORELINE(),
  S("GameOver","loop","Tap to play again: reset and start back at Level 1. Press Play!",
    ["if key_was_pressed(' ') or mouse_was_pressed('left'):","    Game.score = 0","    Game.lives = 3","    set_room('Level1')"], play=True),
 ]})

# 19) COOKIE CLICKER (click-pop feedback + 2 stackable powerups; timer game-over)
GAMES.append({
 "title":"Cookie Clicker","slug":"cookie","classes":["Game","Bg","Cookie","ClickUp","AutoUp"],"rooms":["Play","GameOver"],
 "textures": tex({"cookie.png":"brown","clickbtn.png":"blue","autobtn.png":"green","bg.png":"dark"}),
 "steps":[
  S("Game","start","Set up: cookies, a timer, click power, auto power, a bake timer, then go to Play.",
    ["self.score = 0","self.timeLeft = 1800","self.clickPower = 1","self.autoRate = 0","self.bakeTimer = 0","self.dead = False","set_room('Play')"]),
  S("Bg","start","Add a Class called Bg.",["self.image = sprite('bg.png')","self.scaleX = 760","self.scaleY = 560","self.z = -10"]),
  S("Play","start","In the Play room, make the background. Press Play.",["Game.bg = Bg()"], play=True),
  S("Cookie","start","Add a Class called Cookie - a big cookie. 'pop' is for the click bounce.",
    ["self.image = sprite('cookie.png')","self.scaleX = 160","self.scaleY = 160","self.x = 0","self.y = 40","self.pop = 0"]),
  S("Play","start","Make the cookie. Press Play - yum!",["Game.cookie = Cookie()"], play=True),
  S("Cookie","loop","Click the cookie to bake cookies, and make it POP bigger. Press Play - click it!",
    ["near = mouse_x() > self.x - 90 and mouse_x() < self.x + 90","close = mouse_y() > self.y - 90 and mouse_y() < self.y + 90",
     "if mouse_was_pressed('left') and near and close:","    Game.score = Game.score + Game.clickPower","    self.pop = 0.4"], play=True),
  S("Cookie","loop","Shrink the cookie back down so each click gives a little bounce. Press Play - squishy!",
    ["if self.pop > 0:","    self.pop = self.pop - 0.05","    self.scaleX = 1 + self.pop","    self.scaleY = 1 + self.pop"], play=True),
  S("Play","start","Add a white label.",["Game.label = text()","Game.label.color = \"white\"","Game.label.y = 250","Game.label.text = 'Cookies: 0'"], play=True),
  S("Play","loop","Show cookies, click power, and auto power. Press Play.",
    ["Game.label.text = 'Cookies: ' + str(Game.score) + '   Click: ' + str(Game.clickPower) + '   Auto: ' + str(Game.autoRate)"], play=True),
  S("Play","loop","Count the timer down. When it hits 0, the round is over. Press Play.",
    ["Game.timeLeft = Game.timeLeft - 1","if Game.timeLeft < 1:","    Game.dead = True"], play=True),
  S("ClickUp","start","Add a Class called ClickUp - a blue upgrade button at the bottom-left.",
    ["self.image = sprite('clickbtn.png')","self.scaleX = 150","self.scaleY = 46","self.x = -180","self.y = -210"]),
  S("Play","start","Make the blue button, with a label saying what it does. Press Play.",
    ["Game.clickUp = ClickUp()","Game.tip1 = text()","Game.tip1.color = \"white\"","Game.tip1.x = -180","Game.tip1.y = -210","Game.tip1.text = '+1 Click (10)'"], play=True),
  S("ClickUp","loop","Click the blue button to spend 10 cookies for +1 click power. Buy it again to STACK it! Press Play.",
    ["near = mouse_x() > self.x - 75 and mouse_x() < self.x + 75","close = mouse_y() > self.y - 23 and mouse_y() < self.y + 23",
     "if mouse_was_pressed('left') and near and close and Game.score > 9:","    Game.score = Game.score - 10","    Game.clickPower = Game.clickPower + 1"], play=True),
  S("AutoUp","start","Add a Class called AutoUp - a green upgrade button at the bottom-right.",
    ["self.image = sprite('autobtn.png')","self.scaleX = 150","self.scaleY = 46","self.x = 180","self.y = -210"]),
  S("Play","start","Make the green button, with a label. Press Play.",
    ["Game.autoUp = AutoUp()","Game.tip2 = text()","Game.tip2.color = \"white\"","Game.tip2.x = 180","Game.tip2.y = -210","Game.tip2.text = '+1 Auto (15)'"], play=True),
  S("AutoUp","loop","Click the green button to spend 15 cookies for an auto-baker. Stack it for more! Press Play.",
    ["near = mouse_x() > self.x - 75 and mouse_x() < self.x + 75","close = mouse_y() > self.y - 23 and mouse_y() < self.y + 23",
     "if mouse_was_pressed('left') and near and close and Game.score > 14:","    Game.score = Game.score - 15","    Game.autoRate = Game.autoRate + 1"], play=True),
  S("Play","loop","Every second, the auto-bakers add cookies for you. Press Play - watch it climb by itself!",
    ["Game.bakeTimer = Game.bakeTimer + 1","if Game.bakeTimer > 60:","    Game.bakeTimer = 0","    Game.score = Game.score + Game.autoRate"], play=True),
  S("Game","loop","When time runs out, switch to the GameOver room. Press Play.",
    ["if self.dead:","    self.dead = False","    set_room('GameOver')"], play=True),
  S("GameOver","start","In the GameOver room, show a big white message.",
    ["t = text()","t.color = \"white\"","t.fontSize = 40","t.halign = \"center\"","t.text = 'TIME UP - tap to play again'"]),
  SCORELINE("'Cookies: ' + str(Game.score)"),
  S("GameOver","loop","Tap to play again: reset everything. Press Play!",
    ["if key_was_pressed(' ') or mouse_was_pressed('left'):","    Game.score = 0","    Game.timeLeft = 1800","    Game.clickPower = 1","    Game.autoRate = 0","    set_room('Play')"], play=True),
 ]})

# 20) PAC-MAN
GAMES.append({
 "title":"Pac-Man","slug":"pacman","classes":["Game","Bg","Pac","Dot","Ghost"],"rooms":["Play","GameOver"],
 "textures": tex({"pac.png":"yellow","dot.png":"white","ghost.png":"red","bg.png":"dark"}),
 "steps":[
  S("Game","start","Set up: a score, 3 lives, then go to Play.",["self.score = 0","self.lives = 3","self.dead = False","set_room('Play')"]),
  S("Bg","start","Add a Class called Bg.",["self.image = sprite('bg.png')","self.scaleX = 760","self.scaleY = 560","self.z = -10"]),
  S("Play","start","In the Play room, make the background. Press Play.",["Game.bg = Bg()"], play=True),
  S("Pac","start","Add a Class called Pac - that's you!",["self.image = sprite('pac.png')","self.scaleX = 40","self.scaleY = 40","self.x = 0","self.y = 0"]),
  S("Play","start","Make Pac. Press Play.",["Game.pac = Pac()"], play=True),
  S("Pac","loop","Move Pac with the arrow keys. Press Play - chomp around!",
    ["if key_is_pressed('arrowLeft') or key_is_pressed('a'): self.x = self.x - 5","if key_is_pressed('arrowRight') or key_is_pressed('d'): self.x = self.x + 5",
     "if key_is_pressed('arrowUp') or key_is_pressed('w'): self.y = self.y + 5","if key_is_pressed('arrowDown') or key_is_pressed('s'): self.y = self.y - 5"], play=True),
  S("Dot","start","Add a Class called Dot at a random spot.",
    ["import random","self.image = sprite('dot.png')","self.scaleX = 20","self.scaleY = 20","self.x = random.randint(-340, 340)","self.y = random.randint(-240, 240)"]),
  S("Play","start","Make three dots. Press Play - snacks!",["Game.dotA = Dot()","Game.dotB = Dot()","Game.dotC = Dot()"], play=True),
  S("Dot","loop","Eat a dot with Pac to score; it pops up somewhere new. Press Play - gobble them!",
    ["import random","if get_collision(self, 'Pac'):","    Game.score = Game.score + 1","    self.x = random.randint(-340, 340)","    self.y = random.randint(-240, 240)"], play=True),
  S("Ghost","start","Add a Class called Ghost - it chases you!",["self.image = sprite('ghost.png')","self.scaleX = 44","self.scaleY = 44","self.x = 250","self.y = 200"]),
  S("Play","start","Make the ghost. Press Play - run!",["Game.ghost = Ghost()"], play=True),
  S("Ghost","loop","Make the ghost chase Pac. Press Play - don't get caught!",
    ["pac = Game.pac","if self.x < pac.x: self.x = self.x + 3","if self.x > pac.x: self.x = self.x - 3","if self.y < pac.y: self.y = self.y + 3","if self.y > pac.y: self.y = self.y - 3"], play=True),
  S("Ghost","loop","If the ghost catches Pac = lose a life. Press Play - keep away!",
    ["import random","if get_collision(self, 'Pac'):","    Game.lives = Game.lives - 1","    self.x = random.randint(-300, 300)","    self.y = 240","    if Game.lives < 1: Game.dead = True"], play=True),
  S("Play","start","Add a white label.",["Game.label = text()","Game.label.color = \"white\"","Game.label.y = 250","Game.label.text = 'Score: 0'"], play=True),
  S("Play","loop","Keep the label updated. Press Play.",["Game.label.text = 'Score: ' + str(Game.score) + '   Lives: ' + str(Game.lives)"], play=True),
 ] + GO()})

# 21) DRIFT RUSH - top-down car drifting.
#  The car's NOSE is a little arrow (hx, hy). Pressing Up pushes the car the way
#  the nose points. The car also has its own speed (vx, vy) that keeps its
#  momentum, so when you turn hard the car keeps sliding the old way while the
#  nose points the new way = a drift. "Grip" pulls the slide back toward the
#  nose; the handbrake (Space) drops the grip so you slide more.
#  Kept to + - * and < > only: the nose is turned with a tiny area-preserving
#  spin (the 0.07), and the sideways slide is found with a dot product.
GAMES.append({
 "title":"Drift Rush","slug":"drift","classes":["Game","Track","Car","Cone"],"rooms":["Play","GameOver"],
 "textures": tex({"car.png":"red","cone.png":"orange","track.png":"dark"}),
 "steps":[
  S("Game","start","Set up: a drift score, 3 lives, then go to Play.",
    ["self.score = 0","self.lives = 3","self.dead = False","set_room('Play')"]),
  S("Track","start","Add a Class called Track - the dark road.",
    ["self.image = sprite('track.png')","self.scaleX = 760","self.scaleY = 560","self.z = -10"]),
  S("Play","start","In the Play room, make the road. Press Play.",["Game.track = Track()"], play=True),
  S("Car","start","Add a Class called Car. hx and hy are the nose - it starts pointing right.",
    ["self.image = sprite('car.png')","self.scaleX = 44","self.scaleY = 24","self.hx = 1","self.hy = 0"]),
  S("Car","start","Give the car a speed across (vx) and up-down (vy). It starts still.",
    ["self.vx = 0","self.vy = 0"]),
  S("Play","start","Make your car in the middle. Press Play.",["Game.car = Car()"], play=True),
  S("Car","loop","Press Up to push the car the way the nose points, then move. Press Play - drive!",
    ["if key_is_pressed('arrowUp') or key_is_pressed('w'):","    self.vx = self.vx + self.hx * 0.3","    self.vy = self.vy + self.hy * 0.3",
     "self.x = self.x + self.vx","self.y = self.y + self.vy"], play=True),
  S("Car","loop","Steer LEFT: spin the nose a little and turn the picture too. Press Play - hold Left!",
    ["if key_is_pressed('arrowLeft') or key_is_pressed('a'):","    self.hx = self.hx - self.hy * 0.07","    self.hy = self.hy + self.hx * 0.07","    self.angle = self.angle + 4"], play=True),
  S("Car","loop","Steer RIGHT the same way, the other direction. Press Play - turn both ways!",
    ["if key_is_pressed('arrowRight') or key_is_pressed('d'):","    self.hx = self.hx + self.hy * 0.07","    self.hy = self.hy - self.hx * 0.07","    self.angle = self.angle - 4"], play=True),
  S("Car","loop","Slow down a tiny bit each frame so you don't fly forever. Press Play.",
    ["self.vx = self.vx * 0.985","self.vy = self.vy * 0.985"], play=True),
  S("Car","loop","Set the grip, but hold SPACE for the handbrake - less grip means more sliding! Press Play.",
    ["Game.grip = 0.12","if key_is_pressed(' '):","    Game.grip = 0.03"], play=True),
  S("Car","loop","Find the sideways slide, then pull some of it back toward the nose. Press Play - the car grips and follows its nose!",
    ["self.side = self.vy * self.hx - self.vx * self.hy","self.vx = self.vx + self.hy * self.side * Game.grip","self.vy = self.vy - self.hx * self.side * Game.grip"], play=True),
  S("Car","loop","Score while you DRIFT: the bigger the sideways slide, the more you score! Press Play - hold Space and steer!",
    ["if self.side > 3:","    Game.score = Game.score + 1","if self.side < -3:","    Game.score = Game.score + 1"], play=True),
  S("Car","loop","Keep the car on the road (left and right edges). Press Play.",
    ["if self.x > 360:","    self.x = 360","if self.x < -360:","    self.x = -360"], play=True),
  S("Car","loop","Keep the car on the road (top and bottom edges). Press Play.",
    ["if self.y > 260:","    self.y = 260","if self.y < -260:","    self.y = -260"], play=True),
  S("Cone","start","Add a Class called Cone to dodge.",
    ["self.image = sprite('cone.png')","self.scaleX = 22","self.scaleY = 26"]),
  S("Play","start","Place three cones around the road. Press Play.",
    ["Game.coneA = Cone()","Game.coneA.x = 180","Game.coneA.y = 120","Game.coneB = Cone()","Game.coneB.x = -200","Game.coneB.y = -80","Game.coneC = Cone()","Game.coneC.x = 60","Game.coneC.y = -180"], play=True),
  S("Car","loop","Hit a cone = lose a life and restart in the middle. Press Play - dodge them!",
    ["if get_collision(self, 'Cone'):","    Game.lives = Game.lives - 1","    self.x = 0","    self.y = 0","    self.vx = 0","    self.vy = 0","    if Game.lives < 1:","        Game.dead = True"], play=True),
  S("Play","start","Add a white label for your drift score and lives.",
    ["Game.label = text()","Game.label.color = \"white\"","Game.label.y = 250","Game.label.text = 'Drift Score: 0'"], play=True),
  S("Play","loop","Keep the label updated. Press Play.",
    ["Game.label.text = 'Drift Score: ' + str(Game.score) + '   Lives: ' + str(Game.lives)"], play=True),
 ] + GO()})

# ===========================================================================
# GENERATOR
# ===========================================================================
def assemble(game):
    dims = sprite_dims(game)
    textures = {name: solid_png(RGB[color], dims.get(name, (40, 40))[0], dims.get(name, (40, 40))[1])
                for name, color in game["textures"].items()}
    code = {}
    for s in game["steps"]:
        code.setdefault((s["asset"], s["tab"]), []).extend(prep(game, s))
    def body(asset, tab):
        return "\n".join(code.get((asset, tab), []))
    classes = {}
    for a in game["classes"]:
        if a == "Game":
            continue
        classes[a] = {"start": body(a, "start"), "loop": body(a, "loop")}
    rooms = {}
    for r in game["rooms"]:
        rooms[r] = {"start": body(r, "start"), "loop": body(r, "loop")}
    cfg = {"autoplay": True, "theme": "dark", "layout": "vertical", "canEdit": True,
           "textures": textures, "start": body("Game", "start"), "loop": body("Game", "loop"),
           "classes": classes, "rooms": rooms}
    tmpl = ('<!DOCTYPE html><html><head><meta charset="utf-8"><title>%s</title>'
            '<style>html,body{margin:0;height:100%%;background:#0f1320}#game{height:100vh}'
            '#game #pp-block0,#game #pp-block1{display:none!important}#game #pp-block2{width:100%%!important}'
            '</style></head><body><div id="game"></div><script src="%s"></script><script>\n'
            'PixelPad.game("#game", %s);\n'
            '(function(){var n=0;var iv=setInterval(function(){n++;window.dispatchEvent(new Event("resize"));'
            'var b=document.querySelector("#game #pp-start");'
            'if(!window.ppApp&&b&&b.textContent.trim()==="PLAY")b.click();'
            'if(window.ppApp||n>80){window.dispatchEvent(new Event("resize"));clearInterval(iv);}},200);})();'
            '</script></body></html>')
    with open(game["slug"] + "-final.html", "w", encoding="utf-8") as f:
        f.write(tmpl % (game["title"], CDN, json.dumps(cfg)))

def esc(s):
    return html.escape(s).replace(" ", "&nbsp;")

def sidebar(game, current):
    rows = ['<div class="sb-head">Classes</div>']
    for a in game["classes"]:
        rows.append('<div class="%s">%s</div>' % ("sb-item cur" if a == current else "sb-item", a))
    if game["rooms"]:
        rows.append('<div class="sb-head">Rooms</div>')
        for r in game["rooms"]:
            rows.append('<div class="%s">%s</div>' % ("sb-item cur" if r == current else "sb-item", r))
    return '<div class="sidebar">' + "".join(rows) + '</div>'

def code_panel(asset, tab, all_lines, new_count):
    tabname = "Start" if tab == "start" else "Loop"
    header = '<div class="tabbar"><div class="tab active">%s %s</div></div>' % (asset, tabname)
    rows, total = [], len(all_lines)
    first_new = total - new_count
    # Show ONLY the new lines, numbered at their real position in the editor.
    for i in range(first_new, total):
        rows.append('<div class="ln new"><span class="num">%d</span><span class="src">%s</span></div>' % (
            i + 1, esc(all_lines[i]) or "&nbsp;"))
    return '<div class="codecol">' + header + '<div class="code">' + "".join(rows) + '</div></div>'

CSS = """
    @page { size: letter; margin: 14mm; }
    * { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    body { margin:0; font-family: 'Rubik', 'Segoe UI', system-ui, sans-serif; color:#15202b; background:#fff;
           -webkit-user-select:none; -moz-user-select:none; -ms-user-select:none; user-select:none;
           -webkit-touch-callout:none; }
    .printbtn { position:fixed; top:14px; right:18px; z-index:50; background:#01aefd; color:#fff;
                border:0; border-radius:10px; padding:11px 18px; font-size:15px; font-weight:600;
                cursor:pointer; box-shadow:0 6px 18px rgba(1,174,253,.4); text-decoration:none; }
    .printbtn:hover { background:#0294d8; }
    @media print { .printbtn { display:none !important; } }
    .page { page-break-inside: avoid; break-inside: avoid; padding: 4px 2px 8px; margin-bottom: 7mm; }
    .intro { page-break-inside: avoid; break-inside: avoid; }
    .intro h1 { font-size: 32px; margin: 0 0 8px; }
    .lead { font-size: 16px; color:#33414f; margin: 0 0 14px; }
    .setup { font-size: 15px; line-height: 1.7; background:#f1f6ff; border:1px solid #d6e4ff;
             border-radius:12px; padding:12px 16px; }
    .step-head { display:flex; align-items:center; gap:12px; margin-bottom:6px; }
    .stepno { font-size: 22px; font-weight: 700; color:#0a6299; }
    .play { font-size: 12px; font-weight:700; color:#0a7d33; background:#d8f5e1;
            border:1px solid #9fe0b5; border-radius:20px; padding:3px 11px; letter-spacing:.3px; }
    .instr { font-size: 18px; line-height:1.4; margin: 2px 0 9px; max-width: 720px; }
    .hint { font-size: 13px; color:#516170; margin-bottom:9px; }
    .hint .g, .lead .g, .setup .g { color:#0a7d33; font-weight:700; }
    .editor { display:flex; border-radius:10px; overflow:hidden; border:1px solid #c4ccd6;
              box-shadow:0 3px 12px rgba(0,0,0,.12); max-width: 100%; }
    .sidebar { width:152px; background:#e7e9eb; color:#343a40; padding:10px 0; font-size:13px;
               font-family:'Segoe UI', system-ui, sans-serif; }
    .sb-head { color:#7a828c; font-weight:700; text-transform:uppercase; font-size:11px;
               padding:8px 12px 4px; letter-spacing:.5px; }
    .sb-item { padding:5px 12px; }
    .sb-item.cur { background:#01aefd; color:#fff; font-weight:600; }
    .codecol { flex:1; min-width:0; background:#ffffff; }
    .tabbar { display:flex; border-bottom:1px solid #e0e0e0; }
    .tab { flex:1; text-align:center; font-weight:700; font-size:16px; padding:8px; color:#000; background:#e7e9eb; }
    .tab.active { background:#f3f5f7; }
    .code { padding:8px 0; font-family: 'Consolas','Courier New',monospace; font-size:14px; line-height:1.55; }
    .ln { display:flex; padding:0 10px; color:#000; }
    .ln .num { flex:0 0 26px; width:26px; text-align:right; margin-right:14px; color:#237893; user-select:none; }
    .ln.new { background:#d6f5de; }
    .ln.new .num { color:#0a7d33; font-weight:700; }
    .src { color:inherit; flex:1; min-width:0; white-space:pre-wrap; overflow-wrap:anywhere; }
    @media screen { body { background:#e9edf3; } .page, .intro { background:#fff; max-width: 820px;
        margin: 16px auto; border-radius:10px; box-shadow:0 6px 24px rgba(0,0,0,.12); padding:18px 22px; } }
    .sprite-link { display:inline-block; text-decoration:none; color:#0a6299; background:#e7f7ff;
                   border:1px solid #b6e2fb; border-radius:7px; padding:1px 8px; margin:2px 0; font-weight:600; }
    .sprite-link:hover { background:#d3eefb; border-color:#01aefd; }
    .sprite-link b { color:#0a6299; }
    .sprite-tip { color:#0a6299; font-weight:600; font-size:13px; }
    @media print { .sprite-link { background:transparent; border:none; color:#15202b; padding:0; }
                   .sprite-tip { display:none; } }
"""

def setup_block(game):
    dims = sprite_dims(game)
    rows = []
    for n in game["textures"].keys():
        w, h = dims.get(n, (40, 40))
        # Each sprite links to the Pixel Art Maker with its canvas size pre-filled.
        # px=1 makes the drawing grid match the sprite's native pixel size; the saved
        # PNG comes out at exactly w*h, which is the size PixelPad expects.
        href = '../pixel-art-maker/?cw=%d&ch=%d&px=1&editor=1' % (w, h)
        rows.append('<a class="sprite-link" target="_blank" href="%s">'
                    '<b>%s</b> &mdash; draw it %d&times;%d, %s &#8599;</a>'
                    % (href, n, w, h, game["textures"][n]))
    sprites = "<br>&nbsp;&nbsp;&nbsp;&bull; " + "<br>&nbsp;&nbsp;&nbsp;&bull; ".join(rows)
    classes = ", ".join("<b>%s</b>" % c for c in game["classes"] if c != "Game")
    rooms = ", ".join("<b>%s</b>" % r for r in game["rooms"])
    return ('<div class="setup"><b>Before you start:</b><br>'
            '1. Open a new PixelPad project.<br>'
            '2. Add these pictures (Sprites). Draw each on a pixel canvas of the size shown '
            '(width&times;height): <span class="sprite-tip">Tap a sprite to open the '
            'drawing app at the right size.</span>%s<br>'
            '3. Add these Classes: %s.<br>'
            '4. Add these Rooms: %s.<br>'
            'Now follow the steps. Type only the <span class="g">green</span> lines each time.</div>'
            % (sprites, classes, rooms))

def render(game):
    pages, cum = [], {}
    for idx, s in enumerate(game["steps"], 1):
        slines = prep(game, s)
        if not slines:
            continue
        key = (s["asset"], s["tab"]); cum.setdefault(key, [])
        chunks = paginate(slines)
        for ci, chunk in enumerate(chunks):
            cum[key].extend(chunk)
            cont = ci > 0
            play = '<span class="play">&#9654; PLAY</span>' if (s["play"] and ci == len(chunks) - 1) else ''
            stepno = "Step %d%s" % (idx, " (keep going)" if cont else "")
            instr = ("...keep typing these lines into the same place." if cont else html.escape(s["instr"]))
            head = ('<div class="step-head"><span class="stepno">%s</span>%s</div>'
                    '<div class="instr">%s</div>' % (stepno, play, instr))
            hint = '<div class="hint">Type the <span class="g">green</span> line%s into <b>%s &#9656; %s</b>.</div>' % (
                "s" if len(chunk) > 1 else "", s["asset"], "Start" if s["tab"]=="start" else "Loop")
            editor = '<div class="editor">' + sidebar(game, s["asset"]) + code_panel(s["asset"], s["tab"], list(cum[key]), len(chunk)) + '</div>'
            pages.append('<section class="page">' + head + hint + editor + '</section>')
    intro = ('<section class="intro">'
             '<h1>%s</h1>'
             '<p class="lead">Build this game in PixelPad one step at a time. After each step, press '
             '<b>&#9654; Play</b> to run your code and see what changed.</p>'
             '<p class="lead" style="font-size:13px">Tip: tap <b>Print to PDF</b> (top-right) for a printable copy.</p>'
             '%s</section>' % (html.escape(game["title"]), setup_block(game)))
    doc = ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
           '<meta name="viewport" content="width=device-width, initial-scale=1">'
           '<title>%s - Workbook</title>%s<style>%s</style></head><body>'
           '<button class="printbtn" onclick="window.print()">&#128424;&nbsp; Print to PDF</button>'
           '%s%s%s</body></html>' % (html.escape(game["title"]), FONT_LINK, CSS, intro, "".join(pages), NOCOPY))
    with open(game["slug"] + "-workbook.html", "w", encoding="utf-8") as f:
        f.write(doc)

# Kid-friendly emoji per game (used by the hub).
EMOJI = {"catch":"\U0001F34E","whack":"\U0001F528","flappy":"\U0001F424","subway":"\U0001F3C3",
         "geo":"\U0001F53A","crossy":"\U0001F414","pong":"\U0001F3D3","brick":"\U0001F9F1",
         "doodle":"\U0001F998","shooter":"\U0001F680","heli":"\U0001F681","slice":"\U0001F349",
         "dodge":"☄️","stack":"\U0001F5FC","fishing":"\U0001F3A3","rhythm":"\U0001F3B5",
         "lander":"\U0001F6F8","platformer":"\U0001F3C3‍♂️","cookie":"\U0001F36A",
         "pacman":"\U0001F60B","drift":"\U0001F3CE"}

HUB_CSS = """
    :root { --brand:#01aefd; --brand-dark:#0294d8; --brand-ink:#0a6299; --brand-tint:#e7f7ff;
            --gold:#ffd633; --ink:#1f2a37; --muted:#6b7787; --bg:#eef2f7; --surface:#fff; --border:#dbe3ec; }
    * { box-sizing: border-box; }
    body { margin:0; min-height:100vh; color:var(--ink);
           font-family:"Rubik",system-ui,-apple-system,"Segoe UI",sans-serif;
           background:radial-gradient(1000px 520px at 50% -8%, rgba(1,174,253,.16), transparent 70%), var(--bg);
           padding:56px 22px 80px; }
    .wrap { max-width:980px; margin:0 auto; }
    .logo-link { display:inline-block; margin-bottom:18px; }
    .logo-img { height:38px; width:auto; display:block; }
    h1 { font-size:clamp(28px,5vw,40px); font-weight:700; letter-spacing:-.02em; margin:0 0 8px; }
    .sub { color:var(--muted); font-size:17px; margin:0 0 22px; max-width:620px; line-height:1.5; }
    .banner { background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:14px 18px;
              margin:0 0 30px; max-width:760px; font-size:14px; color:#43505f; box-shadow:0 1px 3px rgba(31,42,55,.05); }
    .banner a { color:var(--brand-ink); font-weight:600; text-decoration:none; }
    .grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(220px,1fr)); gap:16px; }
    .card { background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:18px 18px 16px;
            display:flex; flex-direction:column; gap:9px; box-shadow:0 1px 3px rgba(31,42,55,.05);
            transition:border-color .15s, transform .1s, box-shadow .15s; }
    .card:hover { border-color:var(--brand); transform:translateY(-3px); box-shadow:0 12px 28px rgba(1,174,253,.13); }
    .card .emoji { width:42px; height:42px; border-radius:11px; display:grid; place-items:center;
                   font-size:23px; background:var(--brand-tint); }
    .card .title { font-size:18px; font-weight:600; }
    .card .meta { font-size:12px; color:var(--muted); margin-top:-4px; }
    .btns { display:flex; gap:8px; margin-top:auto; padding-top:4px; }
    .btns a { flex:1; text-align:center; text-decoration:none; font-weight:600; border-radius:9px;
              padding:9px 6px; font-size:14px; border:1px solid; }
    .wb { color:#fff; background:var(--brand); border-color:var(--brand); }
    .wb:hover { background:var(--brand-dark); }
    .play { color:var(--brand-ink); background:var(--surface); border-color:var(--border); }
    .play:hover { background:var(--brand-tint); border-color:var(--brand); }
    footer { color:var(--muted); font-size:13px; margin-top:36px; }
    footer a { color:var(--brand-ink); text-decoration:none; }
"""

FONT_LINK = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
             '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
             '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
             'family=Rubik:wght@400;500;600;700&display=swap">')

LOGO_URL = "https://s3.us-west-1.amazonaws.com/utg.pictures.videos/UTGWeb/utglogoh.svg"

# No copy/paste: the whole point is that kids TYPE each line. Block selection,
# copy/cut/paste, right-click and drag (clicks, links and printing still work).
NOCOPY = ('<script>["copy","cut","paste","contextmenu","selectstart","dragstart"]'
          '.forEach(function(t){document.addEventListener(t,function(e){e.preventDefault();},'
          '{capture:true});});</script>')

def index():
    cards = []
    for g in GAMES:
        emoji = EMOJI.get(g["slug"], "\U0001F3AE")
        cards.append(
            '<div class="card"><div class="emoji">%s</div>'
            '<div class="title">%s</div><div class="meta">%d steps</div>'
            '<div class="btns"><a class="wb" href="%s-workbook.html">Guide</a>'
            '<a class="play" href="%s-final.html" target="_blank">Play</a></div></div>'
            % (emoji, html.escape(g["title"]), len(g["steps"]), g["slug"], g["slug"]))
    doc = ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
           '<meta name="viewport" content="width=device-width, initial-scale=1">'
           '<title>Camp Coding Projects · UTG Academy</title>%s<style>%s</style></head><body>'
           '<div class="wrap"><a class="logo-link" href="../"><img class="logo-img" src="%s" alt="UTG Academy"></a>'
           '<h1>Camp Coding Projects</h1>'
           '<p class="sub">Learn to code real games in Python. Each project takes you from a blank file to a '
           'finished, playable game — one step at a time.</p>'
           '<div class="banner">Every project is a hands-on Python coding challenge: type each line yourself, '
           'run your code, and watch your game come to life. Start with any project below.</div>'
           '<div class="grid">%s</div>'
           '<footer>&copy; 2026 UTG Academy</footer>'
           '</div></body></html>' % (FONT_LINK, HUB_CSS, LOGO_URL, "".join(cards)))
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(doc)

for g in GAMES:
    assemble(g); render(g)
    print("built", g["slug"], "(%d steps)" % len(g["steps"]))
index()
print("built index.html")
