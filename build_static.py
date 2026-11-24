"""Prepare the files a static host (Vercel, GitHub Pages) needs. Run after adding a CSV to uploads/<retailer>/:
    python3 build_static.py
Writes data/<retailer>/snapshots.json, data/<retailer>/<day>.json and sample.csv."""
import json, os
import server

for site in server.SITES:
    out = os.path.join(server.HERE, "data", site)
    os.makedirs(out, exist_ok=True)
    dump = lambda name, obj: json.dump(obj, open(os.path.join(out, name), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    info = server.summary(site)
    info["folder"] = "uploads/%s/" % site
    dump("snapshots.json", info)
    for s in info["snapshots"]:
        dump(s["date"] + ".json", server.dataset(site, s["date"]))
        print("wrote data/%s/%s.json" % (site, s["date"]))
open(os.path.join(server.HERE, "sample.csv"), "w", encoding="utf-8").write(server.SAMPLE)
