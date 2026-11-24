"""Local store stock dashboard (Kika, Fressnapf). Run:  python3 server.py   then open http://localhost:8765
Uploaded CSV files are saved in uploads/<retailer>/ next to this file; every CSV in that folder is shown."""
import csv, io, json, os, re, sys
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
SITES = ["kika", "fressnapf"]


def folder(site):
    """Upload folder of one retailer (unknown names fall back to the first)."""
    p = os.path.join(HERE, "uploads", site if site in SITES else SITES[0])
    os.makedirs(p, exist_ok=True)
    return p


PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
MAX = 300 * 1024 * 1024
REQUIRED = ["date", "product", "variant_id", "store", "units_in_stock"]
PETS = {"dog": 1, "dogs": 1, "cat": 2, "cats": 2, "dog+cat": 3, "both": 3, "dogs+cats": 3}
SAMPLE = """date,pet,product,variation,brand,category,sku,variant_id,price,buyable_online,url,store,store_address,units_in_stock
2026-11-20,dog,Tauro Pro Line bowl for water,"grey, 2 l",Tauro Pro Line,Supplies,TPL47216,45257197387945,12.99,yes,https://www.kika.lt/products/tauro-pro-line-bowl-for-water-grey,KIKA Akropolis Vilnius,"Ozo g. 25, Vilnius",4
2026-11-20,dog,Tauro Pro Line bowl for water,"grey, 2 l",Tauro Pro Line,Supplies,TPL47216,45257197387945,12.99,yes,https://www.kika.lt/products/tauro-pro-line-bowl-for-water-grey,KIKA Mega Kaunas,"Islandijos pl. 32, Kaunas",2
2026-11-20,dog+cat,Silicone travel bowl,,Pet Advance,Supplies,PA10021,45257121628329,3.99,yes,,,,0
2026-11-20,cat,Cat scratching post,90 cm,Kika,Supplies,KK55310,45258181968041,39.99,no,,,,
"""


def parse(text, filename):
    """Return ({date: {"v": {variant_id: record}, "s": {store: address}}}, errors, row_count)."""
    rd = csv.reader(io.StringIO(text))
    try:
        head = [h.strip().lower().lstrip("﻿") for h in next(rd)]
    except StopIteration:
        return {}, ["The file is empty."], 0
    miss = [c for c in REQUIRED if c not in head]
    if miss:
        return {}, ["Missing column(s): %s. The first line must be the column names." % ", ".join(miss)], 0
    ix = {h: i for i, h in enumerate(head)}
    low = filename.lower()
    guess = (1 if "dog" in low else 0) | (2 if "cat" in low else 0)
    out, errs, n = {}, [], 0

    def get(row, col):
        i = ix.get(col)
        return row[i].strip() if i is not None and i < len(row) else ""

    for line, row in enumerate(rd, 2):
        if not any(c.strip() for c in row):
            continue
        n += 1
        date, vid, store, units = get(row, "date"), get(row, "variant_id"), get(row, "store"), get(row, "units_in_stock")
        bad = None
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            bad = "date must look like 2026-11-20 (found '%s')" % date[:20]
        elif not vid:
            bad = "variant_id is empty"
        elif units and not re.fullmatch(r"\d+", units):
            bad = "units_in_stock must be a whole number or blank (found '%s')" % units[:20]
        elif store and not units:
            bad = "a row with a store needs units_in_stock"
        if bad:
            if len(errs) < 8:
                errs.append("Line %d: %s" % (line, bad))
            continue
        d = out.setdefault(date, {"v": {}, "s": {}})
        r = d["v"].get(vid)
        if r is None:
            try:
                price = float(get(row, "price").replace(",", ".")) if get(row, "price") else None
            except ValueError:
                price = None
            buy = get(row, "buyable_online").lower()
            r = d["v"][vid] = {"t": get(row, "product"), "vr": get(row, "variation"), "b": get(row, "brand") or "Unknown",
                               "c": get(row, "category") or "Other", "sku": get(row, "sku"), "p": price,
                               "pet": PETS.get(get(row, "pet").lower(), guess), "buy": None if not buy else int(buy in ("yes", "y", "1", "true")),
                               "url": get(row, "url"), "ok": False, "q": {}}
        else:
            r["pet"] |= PETS.get(get(row, "pet").lower(), guess)
        if units:
            r["ok"] = True
            if store and int(units) > 0:
                r["q"][store] = int(units)
        if store:
            d["s"].setdefault(store, get(row, "store_address"))
    if n == 0 and not errs:
        errs.append("The file has column names but no data rows.")
    return out, errs, n


CACHE = {}  # file path -> (mtime, parsed, rows)


def load_all(site):
    up = folder(site)
    files = sorted(f for f in os.listdir(up) if f.lower().endswith(".csv"))
    for p in list(CACHE):
        if os.path.dirname(p) == up and os.path.basename(p) not in files:
            del CACHE[p]
    for f in files:
        p = os.path.join(up, f)
        m = os.path.getmtime(p)
        if p not in CACHE or CACHE[p][0] != m:
            with open(p, encoding="utf-8-sig", newline="") as fh:
                d, _, n = parse(fh.read(), f)
            CACHE[p] = (m, d, n)
    return [os.path.join(up, f) for f in files]


def merged(site, date):
    V, S = {}, {}
    for p in load_all(site):
        d = CACHE[p][1].get(date)
        if not d:
            continue
        S.update(d["s"])
        for vid, r in d["v"].items():
            if vid in V:
                o = V[vid]
                o["pet"] |= r["pet"]
                o["q"].update(r["q"])
                o["ok"] = o["ok"] or r["ok"]
            else:
                V[vid] = dict(r, q=dict(r["q"]))
    return V, S


def summary(site):
    files = load_all(site)
    dates = sorted({d for p in files for d in CACHE[p][1]})
    snaps = []
    for date in dates:
        V, S = merged(site, date)
        ok = [r for r in V.values() if r["ok"]]
        snaps.append({"date": date, "variations": len(V), "collected": len(ok), "stores": len(S),
                      "units": sum(sum(r["q"].values()) for r in ok), "stocked": sum(1 for r in ok if r["q"])})
    return {"snapshots": snaps, "files": [{"name": os.path.basename(p), "size": os.path.getsize(p), "rows": CACHE[p][2],
                                           "dates": sorted(CACHE[p][1])} for p in files], "folder": folder(site)}


def dataset(site, date):
    V, S = merged(site, date)
    names = sorted(S)
    ix = {n: i for i, n in enumerate(names)}
    rows = [[vid, r["t"], r["vr"], r["b"], r["c"], r["sku"], r["p"], r["pet"], r["buy"], r["url"],
             [x for s, u in r["q"].items() for x in (ix[s], u)] if r["ok"] else None] for vid, r in V.items()]
    return {"date": date, "stores": [[n, S[n]] for n in names], "rows": rows}


class H(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if not isinstance(body, bytes):
            body = (body if isinstance(body, str) else json.dumps(body, ensure_ascii=False, separators=(",", ":"))).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        site = q.get("site", [""])[0]
        if u.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                return self.send(200, f.read(), "text/html; charset=utf-8")
        if u.path == "/echarts.min.js":
            with open(os.path.join(HERE, "echarts.min.js"), "rb") as f:
                return self.send(200, f.read(), "application/javascript; charset=utf-8")
        if u.path == "/api/snapshots":
            return self.send(200, summary(site))
        if u.path == "/api/data":
            return self.send(200, dataset(site, q.get("date", [""])[0]))
        if u.path == "/sample.csv":
            return self.send(200, SAMPLE, "text/csv; charset=utf-8")
        if u.path == "/api/sample.csv":
            return self.send(200, SAMPLE, "text/csv; charset=utf-8", {"Content-Disposition": 'attachment; filename="stock_sample.csv"'})
        self.send(404, {"error": "Not found"})

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/api/upload":
            return self.send(404, {"error": "Not found"})
        q = parse_qs(u.query)
        name = os.path.basename(q.get("name", ["upload.csv"])[0])
        name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .") or "upload.csv"
        if not name.lower().endswith(".csv"):
            return self.send(400, {"error": "Only .csv files can be added."})
        size = int(self.headers.get("Content-Length") or 0)
        if size <= 0 or size > MAX:
            return self.send(400, {"error": "The file is empty or larger than 300 MB."})
        raw = self.rfile.read(size)
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            return self.send(400, {"error": "The file is not UTF-8 text. Save it as 'CSV UTF-8' and try again."})
        d, errs, n = parse(text, name)
        if errs:
            return self.send(400, {"error": "The file was not saved because it does not match the format.", "details": errs})
        path = os.path.join(folder(q.get("site", [""])[0]), name)
        replaced = os.path.exists(path)
        with open(path + ".part", "wb") as f:
            f.write(raw)
        os.replace(path + ".part", path)
        self.send(200, {"saved": name, "replaced": replaced, "rows": n, "dates": sorted(d),
                        "variations": sum(len(x["v"]) for x in d.values())})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print("Store stock dashboard: http://localhost:%d   (uploads folder: %s)" % (PORT, os.path.join(HERE, "uploads")), flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
