# Store stock dashboard

Shows which products are stocked in which stores, how many units each store holds, and (once two days are loaded) an estimate of what is selling. It covers two retailers, chosen with the switch at the top of the page: Kika (Lithuania) and Fressnapf (Germany).

## Run it on your computer

```
python3 server.py
```

Open http://localhost:8765. No packages to install. In this mode the **Add data** tab can upload a CSV; files are saved in `uploads/kika/` or `uploads/fressnapf/`, depending on the retailer selected.

## Add a day of data to the hosted site

The hosted copy (Vercel) is read-only. To add a day:

1. Put the day's CSV in `uploads/kika/` or `uploads/fressnapf/`.
2. Run `python3 build_static.py` (it rewrites the files in `data/`).
3. Commit and push. Vercel redeploys by itself.

## CSV format

One row per variation per store. The **Add data** tab lists every column with an example, and `sample.csv` is a small example file.

Required columns: `date` (YYYY-MM-DD), `product`, `variant_id`, `store`, `units_in_stock`.
Optional columns: `pet`, `variation`, `brand`, `category`, `sku`, `price`, `buyable_online`, `url`, `store_address`.

A blank `store` with `units_in_stock` 0 means the variation is in no store. A blank `units_in_stock` means it was not collected.

## Files

- `index.html` – the dashboard page
- `echarts.min.js` – charting library (Apache ECharts 5.5.0)
- `server.py` – local server with upload
- `build_static.py` – prepares `data/` for the hosted site
- `uploads/<retailer>/` – the CSV files
- `data/<retailer>/` – files the hosted site reads
