"""Prepare the files a static host (Vercel, GitHub Pages) needs. Run after adding a CSV to uploads/:
    python3 build_static.py
Writes data/snapshots.json, data/<day>.json and sample.csv."""
import json, os
import server

out = os.path.join(server.HERE, "data")
os.makedirs(out, exist_ok=True)
info = server.summary()
info["folder"] = "uploads/"
dump = lambda name, obj: json.dump(obj, open(os.path.join(out, name), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
dump("snapshots.json", info)
for s in info["snapshots"]:
    dump(s["date"] + ".json", server.dataset(s["date"]))
    print("wrote data/%s.json" % s["date"])
open(os.path.join(server.HERE, "sample.csv"), "w", encoding="utf-8").write(server.SAMPLE)
print("done:", len(info["snapshots"]), "day(s)")
