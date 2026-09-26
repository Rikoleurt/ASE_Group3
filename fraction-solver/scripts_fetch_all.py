"""Fetch every traced sign crop, not just the fractions."""
import time, urllib.request
from pathlib import Path
from la.fetch import load_cached

OUT = Path("data/cache/allcrops"); OUT.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "LinearA-fraction-research/0.1 (Masters student project; non-commercial research)"}

todo = []
for d in load_cached().values():
    for s in d.get("signs") or []:
        if not s.get("image"):
            continue
        sign = s.get("sign") or "UNKNOWN"
        role = s.get("role") or "none"
        name = f"{sign}__{role}__{d['id'].replace(' ', '_')}__{s['position']}.png"
        if not (OUT / name).exists():
            todo.append((name, s["image"]))

print(f"to fetch: {len(todo)}", flush=True)
for i, (name, url) in enumerate(todo, 1):
    try:
        req = urllib.request.Request(url, headers=UA)
        (OUT / name).write_bytes(urllib.request.urlopen(req, timeout=30).read())
    except Exception as exc:
        print("fail", name, exc, flush=True)
    if i % 250 == 0:
        print(f"  {i}/{len(todo)}", flush=True)
    time.sleep(0.3)
print("done:", len(list(OUT.glob('*.png'))), flush=True)
