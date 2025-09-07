#!/usr/bin/env python3
import argparse, re, sys, math, pathlib, json

PROFILES = {
  # Example per-access energies (nJ) & leakage (W) — adapt as you like.
  # These are just representative; pick the NVM flavor you want.
  "sram":  {"Edyn_hit":0.565, "Edyn_miss":0.011, "Edyn_write":0.537, "Pleak":3.438},
  "stt":   {"Edyn_hit":0.173, "Edyn_miss":0.058, "Edyn_write":1.644, "Pleak":0.295},
  "rram":  {"Edyn_hit":0.263, "Edyn_miss":0.078, "Edyn_write":0.952, "Pleak":0.194}
}

def grab(name, text):
    m = re.search(rf"^{re.escape(name)}\s+([0-9.eE+-]+)\s", text, re.M)
    return float(m.group(1)) if m else 0.0

def collect_for(prefix, text):
    hits   = grab(f"{prefix}.overallHits::total", text)
    misses = grab(f"{prefix}.overallMisses::total", text)
    wbs    = grab(f"{prefix}.writebacks::total", text)
    return hits, misses, wbs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stats", help="path to stats.txt")
    ap.add_argument("--tech", choices=list(PROFILES)+["custom"], default="sram")
    ap.add_argument("--Edyn_hit", type=float)
    ap.add_argument("--Edyn_miss", type=float)
    ap.add_argument("--Edyn_write", type=float)
    ap.add_argument("--Pleak", type=float)
    args = ap.parse_args()

    txt = pathlib.Path(args.stats).read_text()

    sim_s = grab("sim_seconds", txt)

    # single L2 or hybrid (two L2s)
    names = []
    base = "system."
    # try hybrid first
    for n in ("l2_sram","l2_nvm"):
        if re.search(rf"^{re.escape(base+n)}\.", txt, re.M): names.append(base+n)
    if not names:
        names = [base+"l2"]

    hits = misses = wbs = 0.0
    for n in names:
        h,m,w = collect_for(n, txt)
        hits+=h; misses+=m; wbs+=w

    if args.tech == "custom":
        p = dict(Edyn_hit=args.Edyn_hit, Edyn_miss=args.Edyn_miss,
                 Edyn_write=args.Edyn_write, Pleak=args.Pleak)
        if None in p.values():
            sys.exit("custom tech requires --Edyn_hit --Edyn_miss --Edyn_write --Pleak")
    else:
        p = PROFILES[args.tech]

    E_dyn = hits*p["Edyn_hit"] + misses*p["Edyn_miss"] + wbs*p["Edyn_write"]
    E_leak = p["Pleak"] * sim_s
    E_total = E_dyn + E_leak
    ED2P = E_total * (sim_s**2)

    out = {
        "file": args.stats, "l2s": names, "sim_seconds": sim_s,
        "hits": hits, "misses": misses, "writebacks": wbs,
        "profile": p, "E_dyn_nJ": E_dyn, "E_leak_J": E_leak, "E_total_J": E_total, "ED2P": ED2P
    }
    print(json.dumps(out, indent=2))
if __name__ == "__main__":
    main()

