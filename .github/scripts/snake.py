"""Render a snake that eats the contribution grid and grows with every block.

usage: GITHUB_TOKEN=... python snake.py <user> <out.svg>
"""
import os
import sys
from collections import deque
from datetime import date

from contrib3d import TOPS, fetch, level

PITCH, CELL = 15, 11
COLS, ROWS = 53, 7
OX, OY = (900 - COLS * PITCH) // 2, 64
H = OY + ROWS * PITCH + 30
DT = 0.05  # seconds per step
START_LEN = 3
MAX_LEN = 64  # past this the grid gets too crowded to read
EMPTY = TOPS[0]


def grid_from(cal):
    peak = max(d["contributionCount"] for w in cal["weeks"] for d in w["contributionDays"]) or 1
    food = {}
    for x, w in enumerate(cal["weeks"]):
        for d in w["contributionDays"]:
            y = date.fromisoformat(d["date"]).isoweekday() % 7
            food[(x, y)] = level(d["contributionCount"], peak)
    return food


def bfs(start, targets, blocked):
    prev = {start: None}
    q = deque([start])
    while q:
        cur = q.popleft()
        if cur in targets:
            path = []
            while cur != start:
                path.append(cur)
                cur = prev[cur]
            return path[::-1]
        x, y = cur
        for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if nxt in prev or nxt in blocked:
                continue
            if -2 <= nxt[0] <= COLS and -1 <= nxt[1] <= ROWS:
                prev[nxt] = cur
                q.append(nxt)
    return None


def simulate(food):
    remaining = {c for c, lv in food.items() if lv}
    history = [(-2, 3)]
    body = deque([(-2, 3)] * START_LEN)
    eaten_at, grown_at = {}, []
    while remaining:
        path = bfs(body[0], remaining, set(list(body)[:-1])) or bfs(body[0], remaining, set())
        for cell in path:
            history.append(cell)
            body.appendleft(cell)
            if cell in remaining:
                remaining.discard(cell)
                eaten_at[cell] = len(history) - 1
                if len(body) <= MAX_LEN:
                    grown_at.append(len(history) - 1)
                    continue
            body.pop()
    # slither off to the right so the loop restarts on a clean grid
    x, y = history[-1]
    for ny in range(y - 1, -2, -1):
        history.append((x, ny))
    x, y = history[-1]
    while x < COLS + len(body) + 4:
        x += 1
        history.append((x, y))
    return history, eaten_at, grown_at, len(body)


def px(cell):
    return OX + cell[0] * PITCH, OY + cell[1] * PITCH


def lerp(a, b, t):
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(u + (v - u) * t) for u, v in zip(ca, cb))


def render(food, history, eaten_at, grown_at, length):
    n = len(history)
    dur = n * DT
    pct = lambda step: 100 * step / n

    move = "".join(f"{pct(i):.3f}%{{transform:translate({px(c)[0]}px,{px(c)[1]}px)}}" for i, c in enumerate(history))
    css = [f"@keyframes m{{{move}}}"]

    cells = []
    for i, ((x, y), lv) in enumerate(sorted(food.items())):
        cx, cy = px((x, y))
        cls = ""
        if (x, y) in eaten_at:
            p = pct(eaten_at[(x, y)])
            css.append(f"@keyframes e{i}{{0%,{p:.3f}%{{fill:{TOPS[lv]}}}{p + .001:.3f}%{{fill:{EMPTY}}}}}")
            cls = f' style="animation:e{i} {dur:.2f}s step-end infinite"'
        cells.append(f'<rect x="{cx}" y="{cy}" width="{CELL}" height="{CELL}" rx="2.5" fill="{TOPS[lv]}"{cls}/>')

    segs = []
    for i in range(length - 1, -1, -1):
        t = i / max(length - 1, 1)
        color = lerp("#ffb454", "#6b4a22", t)
        size = CELL - 1 - 3 * t
        off = (CELL - size) / 2
        anim = f"m {dur:.2f}s linear {i * DT:.2f}s infinite backwards"
        if i >= START_LEN:
            css.append(f"@keyframes v{i}{{0%{{opacity:0}}{pct(grown_at[i - START_LEN]):.3f}%{{opacity:1}}}}")
            anim += f", v{i} {dur:.2f}s step-end infinite"
        segs.append(
            f'<rect x="{off:.1f}" y="{off:.1f}" width="{size:.1f}" height="{size:.1f}" rx="{size / 2.6:.1f}" '
            f'fill="{color}" style="animation:{anim}"/>'
        )

    eaten = len(eaten_at)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 {H}" width="900" height="{H}" role="img" aria-labelledby="t">
  <title id="t">snake eating {eaten} days of contributions and growing to {length} segments</title>
  <defs>
    <clipPath id="card"><rect x="1" y="1" width="898" height="{H - 2}" rx="14"/></clipPath>
    <pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#fff" opacity=".035"/></pattern>
  </defs>
  <style>
    text {{ font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, "Cascadia Mono", Consolas, "Liberation Mono", monospace; font-size: 14px; fill: #c8d0c9; white-space: pre; }}
    .dim {{ fill: #5f6f66; }} .amb {{ fill: #ffb454; }} .ok {{ fill: #3ddc97; }} .s {{ font-size: 12px; }}
    {"".join(css)}
    @media (prefers-reduced-motion: reduce) {{ .snake {{ display: none; }} rect {{ animation: none !important; }} }}
  </style>
  <rect x="1" y="1" width="898" height="{H - 2}" rx="14" fill="#0b0f0d" stroke="#243029"/>
  <g clip-path="url(#card)">
    <rect width="900" height="40" fill="#111713"/>
    <line x1="0" y1="40.5" x2="900" y2="40.5" stroke="#1f2a24"/>
    <text x="24" y="25"><tspan class="amb">jonathan@nansen</tspan><tspan class="dim">:~$ </tspan>snake --eat=contributions --grow</text>
    <text x="876" y="25" class="dim s" text-anchor="end"><tspan class="ok">{eaten}</tspan> blocks · length {START_LEN} → <tspan class="amb">{length}</tspan></text>
    {''.join(cells)}
    <g class="snake">{''.join(segs)}</g>
    <rect width="900" height="{H}" fill="url(#scan)"/>
  </g>
</svg>
"""


if __name__ == "__main__":
    user, out = sys.argv[1:3]
    food = grid_from(fetch(user, os.environ["GITHUB_TOKEN"]))
    svg = render(food, *simulate(food))
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as f:
        f.write(svg)
