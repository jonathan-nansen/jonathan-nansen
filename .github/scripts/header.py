"""Fill the boot-log header template with live GitHub data.

usage: GITHUB_TOKEN=... python header.py <user> <profile.json> <template.svg> <out.svg> <validators-status.json>
"""
import json
import os
import sys
import urllib.request
from collections import Counter
from html import escape

from upstream import clip, tidy

QUERY = """query($u:String!, $q:String!){
  user(login:$u){
    createdAt
    repositories(ownerAffiliations:OWNER, isFork:false, first:50){nodes{primaryLanguage{name}}}
    contributionsCollection{contributionCalendar{totalContributions weeks{contributionDays{contributionCount}}}}
  }
  search(query:$q, type:ISSUE, first:50){nodes{... on PullRequest{
    number title createdAt state repository{name primaryLanguage{name}}
  }}}
}"""

LANG_ALIASES = {"Shell": "bash"}
LANG_SKIP = {"HTML", "CSS", "Dockerfile", "Makefile", "Nix", "HCL", "Jsonnet"}
BAR_W = 200


def fetch(user, exclude):
    q = f"is:pr author:{user} -user:{user} -org:{exclude} sort:created-desc"
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"u": user, "q": q}}).encode(),
        headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if "errors" in body:
        sys.exit(f"graphql: {body['errors']}")
    return body["data"]


def dots(items):
    return " · ".join(items)


def fill(data, cfg, healthy):
    user = data["user"]
    prs = [p for p in data["search"]["nodes"] if p]
    cal = user["contributionsCollection"]["contributionCalendar"]
    days = [d["contributionCount"] for w in cal["weeks"] for d in w["contributionDays"]]
    active = sum(1 for c in days if c)

    langs = Counter()
    for lang in [r["primaryLanguage"] for r in user["repositories"]["nodes"]] + [
        p["repository"]["primaryLanguage"] for p in prs
    ]:
        if lang and lang["name"] not in LANG_SKIP:
            langs[LANG_ALIASES.get(lang["name"], lang["name"].lower())] += 1

    upstream = list(dict.fromkeys(p["repository"]["name"] for p in prs if p["state"] == "OPEN"))
    head = "—"
    if prs:
        p = prs[0]
        head = f'{p["repository"]["name"]}#{p["number"]} {tidy(p["title"])}'
        head = f"{clip(head, 52)} · {p['createdAt'][:10]}"

    return {
        "genesis": user["createdAt"][:10],
        "chains": dots(cfg["chains"]),
        "infra": dots(cfg["infra"]),
        "observe": dots(cfg["observe"]),
        "langs": dots(l for l, _ in langs.most_common(4)),
        "upstream": clip(dots(upstream), 62),
        "contributions": str(cal["totalContributions"]),
        "active": str(active),
        "active_pct": str(round(100 * active / len(days))),
        "bar_w": f"{BAR_W * active / len(days):.1f}",
        "head": head,
        "tagline": cfg["tagline"],
        "signal": "signing" if healthy else "degraded",
        "signal_color": "#3ddc97" if healthy else "#ff6b6b",
    }


if __name__ == "__main__":
    user, cfg_path, tpl_path, out, status_path = sys.argv[1:6]
    with open(status_path) as f:
        healthy = json.load(f)["healthy"]
    with open(cfg_path) as f:
        cfg = json.load(f)
    with open(tpl_path) as f:
        svg = f.read()
    for key, val in fill(fetch(user, cfg["exclude_org"]), cfg, healthy).items():
        svg = svg.replace("{{%s}}" % key, escape(val))
    if "{{" in svg:
        sys.exit("unfilled placeholder in header template")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as f:
        f.write(svg)
