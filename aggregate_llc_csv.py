#!/usr/bin/env python3
import argparse, json, pathlib, csv

def load(path):
    d = json.loads(pathlib.Path(path).read_text())
    row = {
        "file": str(path),
        "sim_seconds": d.get("sim_seconds", 0.0),
        "E_total_J": d.get("E_total_J_total", 0.0),
        "ED2P": d.get("ED2P", 0.0),
        "llc_parts": "|".join(d.get("llc_parts", [])),
    }
    # roll up features across parts
    uniq_w = uniq_r = p90_w = p90_r = 0.0
    uniq_w_b = uniq_r_b = 0.0
    for p in d.get("parts", []):
        ft = p.get("features", {})
        uniq_w   += ft.get("unique_write_lines", 0.0)
        uniq_r   += ft.get("unique_read_lines",  0.0)
        uniq_w_b += ft.get("unique_write_bytes", 0.0)
        uniq_r_b += ft.get("unique_read_bytes",  0.0)
        p90_w    += ft.get("p90_write_lines",    0.0)
        p90_r    += ft.get("p90_read_lines",     0.0)
    row.update(dict(
        unique_write_lines=uniq_w, unique_read_lines=uniq_r,
        unique_write_bytes=uniq_w_b, unique_read_bytes=uniq_r_b,
        p90_write_lines=p90_w, p90_read_lines=p90_r
    ))
    return row

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsons", nargs="+", help="one or more JSONs from sum_llc_energy.py")
    ap.add_argument("--baseline", help="JSON to normalize against (e.g., SRAM of same WS)")
    args = ap.parse_args()

    rows = [load(p) for p in args.jsons]
    if args.baseline:
        b = load(args.baseline)
        bE = b["E_total_J"] or 1.0
        bT = b["sim_seconds"] or 1.0
        bD = b["ED2P"] or (bE * bT * bT)
        for r in rows:
            r["energy_norm"] = (r["E_total_J"]/bE) if bE else 0.0
            r["ed2p_norm"]   = (r["ED2P"]/bD) if bD else 0.0
            r["speedup_vs_baseline"] = (bT / r["sim_seconds"]) if r["sim_seconds"] else 0.0

    w = csv.DictWriter(sys.stdout, fieldnames=list(rows[0].keys()))
    w.writeheader()
    for r in rows: w.writerow(r)

if __name__ == "__main__":
    import sys
    main()

