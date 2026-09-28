"""Probe validators on public chain APIs and render a status card.

usage: python validators.py <profile.json> <out.svg> <status.json>
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from html import escape

SOLANA_RPC = "https://api.mainnet-beta.solana.com"
ROW, TOP = 40, 84
GOOD, BAD, UNKNOWN = "#3ddc97", "#ff6b6b", "#5f6f66"
UA = {"User-Agent": "jonathan-nansen-profile/1.0 (+https://github.com/jonathan-nansen)"}


def post(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", **UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return json.load(r)


def rpc(method, params):
    body = post(SOLANA_RPC, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    if "error" in body:
        raise RuntimeError(body["error"])
    return body["result"]


def compact(n):
    for unit, div in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if n >= div:
            return f"{n / div:.2f}{unit}"
    return f"{n:.0f}"


def hyperliquid(v):
    vals = post("https://api.hyperliquid.xyz/info", {"type": "validatorSummaries"})
    me = next(x for x in vals if x["validator"].lower() == v["address"].lower())
    week = dict(me["stats"])["week"]["uptimeFraction"]
    ok = me["isActive"] and not me["isJailed"]
    return {
        "ok": ok,
        "status": "jailed" if me["isJailed"] else ("active" if me["isActive"] else "inactive"),
        "m1": f"uptime {100 * float(week):.2f}% 7d",
        "m2": f"commission {100 * float(me['commission']):g}%",
        "stake": me["stake"] / 1e8,
    }


def solana(v):
    accts = rpc("getVoteAccounts", [{"votePubkey": v["vote"]}])
    delinquent = bool(accts["delinquent"])
    me = (accts["current"] or accts["delinquent"])[0]
    prod = rpc("getBlockProduction", [{"identity": v["identity"]}])["value"]["byIdentity"].get(v["identity"])
    skip = "—"
    if prod and prod[0]:
        skip = f"{100 * (1 - prod[1] / prod[0]):.2f}%"
    return {
        "ok": not delinquent,
        "status": "delinquent" if delinquent else "voting",
        "m1": f"skip rate {skip}",
        "m2": f"last vote {me['lastVote']:,}",
        "stake": me["activatedStake"] / 1e9,
    }


def cosmos(v):
    vals = get(f"https://validators.cosmos.directory/chains/{v['registry']}")["validators"]
    me = next(x for x in vals if x["operator_address"] == v["address"])
    ok = me["active"] and not me["jailed"]
    return {
        "ok": ok,
        "status": "jailed" if me["jailed"] else ("bonded" if me["active"] else "unbonded"),
        "m1": f"uptime {100 * float(me.get('uptime') or 0):.2f}%",
        "m2": f"rank #{me['rank']}",
        "stake": int(me["tokens"]) / 10 ** v["decimals"],
    }


PROBES = {"hyperliquid": hyperliquid, "solana": solana, "cosmos": cosmos}


def probe(v):
    try:
        return PROBES[v["kind"]](v)
    except Exception as e:  # one flaky API shouldn't take the card down
        print(f"{v['chain']}: {e}", file=sys.stderr)
        return {"ok": None, "status": "no data", "m1": "", "m2": "", "stake": None}


def render(rows, now):
    n = len(rows)
    h = TOP + n * ROW + 34
    body = []
    for i, (v, r) in enumerate(rows):
        y = TOP + i * ROW
        color = GOOD if r["ok"] else (UNKNOWN if r["ok"] is None else BAD)
        ring = f'<circle cx="190" cy="{y - 5}" r="4" fill="{color}" class="ring"/>' if r["ok"] else ""
        stake = f'{compact(r["stake"])} <tspan class="dim">{v["symbol"]}</tspan>' if r["stake"] is not None else ""
        body.append(
            f'<g class="row" style="animation-delay:{.3 + i * .25:.2f}s">'
            f'<rect x="24" y="{y - 24}" width="852" height="{ROW - 6}" rx="8" fill="#101613"/>'
            f'<text x="44" y="{y}">{escape(v["chain"])}</text>'
            f'{ring}<circle cx="190" cy="{y - 5}" r="4" fill="{color}"/>'
            f'<text x="204" y="{y}" style="fill:{color}">{escape(r["status"])}</text>'
            f'<text x="330" y="{y}" class="m">{escape(r["m1"])}</text>'
            f'<text x="540" y="{y}" class="m">{escape(r["m2"])}</text>'
            f'<text x="856" y="{y}" class="amb" text-anchor="end">{stake}</text></g>'
        )
    up = sum(1 for _, r in rows if r["ok"])
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 {h}" width="900" height="{h}" role="img" aria-labelledby="t">
  <title id="t">{up} of {n} validators healthy</title>
  <defs>
    <clipPath id="card"><rect x="1" y="1" width="898" height="{h - 2}" rx="14"/></clipPath>
    <pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#fff" opacity=".035"/></pattern>
  </defs>
  <style>
    text {{ font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, "Cascadia Mono", Consolas, "Liberation Mono", monospace; font-size: 14px; fill: #c8d0c9; white-space: pre; }}
    .dim {{ fill: #5f6f66; }} .amb {{ fill: #ffb454; }} .ok {{ fill: {GOOD}; }} .s {{ font-size: 12px; }} .m {{ font-size: 13px; fill: #9aa69e; }}
    .row {{ opacity: 0; animation: in .4s ease-out forwards; }}
    @keyframes in {{ from {{ opacity: 0; transform: translateY(4px); }} to {{ opacity: 1; transform: none; }} }}
    .ring {{ transform-box: fill-box; transform-origin: center; animation: ring 2s ease-out infinite; }}
    @keyframes ring {{ 0% {{ transform: scale(1); opacity: .7; }} 80%, 100% {{ transform: scale(3); opacity: 0; }} }}
    @media (prefers-reduced-motion: reduce) {{ .row {{ opacity: 1; animation: none; }} .ring {{ display: none; }} }}
  </style>
  <rect x="1" y="1" width="898" height="{h - 2}" rx="14" fill="#0b0f0d" stroke="#243029"/>
  <g clip-path="url(#card)">
    <rect width="900" height="40" fill="#111713"/>
    <line x1="0" y1="40.5" x2="900" y2="40.5" stroke="#1f2a24"/>
    <text x="24" y="25"><tspan class="amb">jonathan@nansen</tspan><tspan class="dim">:~$ </tspan>validatorctl status --mainnet</text>
    <text x="876" y="25" class="dim s" text-anchor="end">probed {now}</text>
    {''.join(body)}
    <text x="24" y="{h - 14}" class="s"><tspan class="ok">{up}/{n}</tspan><tspan class="dim"> healthy · live from public chain APIs · nansen validators I operate</tspan></text>
    <rect width="900" height="{h}" fill="url(#scan)"/>
  </g>
</svg>
"""


if __name__ == "__main__":
    cfg_path, out, status_path = sys.argv[1:4]
    with open(cfg_path) as f:
        validators = json.load(f)["validators"]
    rows = [(v, probe(v)) for v in validators]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as f:
        f.write(render(rows, now))
    with open(status_path, "w") as f:
        down = [v["chain"] for v, r in rows if r["ok"] is False]
        json.dump({"healthy": not down, "down": down}, f)
