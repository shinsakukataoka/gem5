#!/usr/bin/env python3
import argparse, json, pathlib, re

# Example energy profiles (nJ per access; W for leakage). Adjust if you wish.
SRAM = dict(Edyn_hit=0.565, Edyn_miss=0.011, Edyn_write=0.537, Pleak=3.438)
NVM  = dict(Edyn_hit=0.173, Edyn_miss=0.058, Edyn_write=1.644, Pleak=0.295)

def parse_stats(path):
    kv = {}
    for ln in pathlib.Path(path).read_text().splitlines():
        ln = ln.split('#',1)[0].rstrip()
        if not ln: continue
        parts = re.split(r'\s{2,}', ln)
        if len(parts) >= 2:
            k = parts[0].strip()
            try: v = float(parts[1].strip())
            except: continue
            kv[k] = v
    return kv

def has_prefix(d, pref): return any(k.startswith(pref + ".") for k in d)

def pick(d, keys):
    for k in keys:
        if k in d: return d[k]
    return None

def get_acc_miss_wb(d, pref):
    acc  = pick(d, [f"{pref}.demandAccesses::total", f"{pref}.overallAccesses::total"])
    miss = pick(d, [f"{pref}.demandMisses::total",   f"{pref}.overallMisses::total"])
    if acc is None:
        ai = pick(d, [f"{pref}.demandAccesses::cpu.inst", f"{pref}.overallAccesses::cpu.inst"]) or 0.0
        ad = pick(d, [f"{pref}.demandAccesses::cpu.data", f"{pref}.overallAccesses::cpu.data"]) or 0.0
        acc = ai + ad
    if miss is None:
        mi = pick(d, [f"{pref}.demandMisses::cpu.inst", f"{pref}.overallMisses::cpu.inst"]) or 0.0
        md = pick(d, [f"{pref}.demandMisses::cpu.data", f"{pref}.overallMisses::cpu.data"]) or 0.0
        miss = mi + md
    hits = max(0.0, acc - miss)
    wbs  = pick(d, [f"{pref}.writebacks::total", f"{pref}.writebacks::writebacks"]) or 0.0
    return hits, miss, wbs

def energy_for_cache(d, pref, prof, sim_s):
    hits, miss, wbs = get_acc_miss_wb(d, pref)
    e_dyn_nJ = hits*prof["Edyn_hit"] + miss*prof["Edyn_miss"] + wbs*prof["Edyn_write"]
    e_leak_J = prof["Pleak"] * sim_s
    return {
        "name": pref,
        "hits": hits, "misses": miss, "writebacks": wbs,
        "profile": prof,
        "E_dyn_nJ": e_dyn_nJ,
        "E_leak_J": e_leak_J,
        "E_total_J": e_leak_J + e_dyn_nJ*1e-9,
    }

def features_stream_like(d, pref, line_size=64.0):
    # STREAM proxies
    # Unique writes ~ number of dirty evictions
    wbacks = pick(d, [f"{pref}.writebacks::total", f"{pref}.writebacks::writebacks"]) or 0.0
    # Unique reads: prefer explicit ReadSharedReq misses, else data misses
    rmiss  = pick(d, [f"{pref}.ReadSharedReq.misses::total"]) \
             or pick(d, [f"{pref}.demandMisses::cpu.data"]) or 0.0
    feats = {
        "unique_write_lines": wbacks,
        "unique_read_lines":  rmiss,
        "unique_write_bytes": wbacks * line_size,
        "unique_read_bytes":  rmiss  * line_size,
        "p90_write_lines":    0.9 * wbacks,
        "p90_read_lines":     0.9 * rmiss,
    }
    # Optional totals if present
    racc = pick(d, [f"{pref}.ReadSharedReq.accesses::total", f"{pref}.demandAccesses::cpu.data"])
    if racc is not None: feats["total_read_accesses"] = racc
    wex  = pick(d, [f"{pref}.ReadExReq.accesses::total"])  # write-get-exclusive at LLC
    if wex is not None: feats["total_write_exclusive"] = wex
    return feats

def auto_find_llc_names(d):
    # Prefer L3, then L2; support hybrid
    for group in (["system.l3_sram","system.l3_nvm","system.l3"],
                  ["system.l2_sram","system.l2_nvm","system.l2"]):
        found = [n for n in group if has_prefix(d, n)]
        if found: return found
    # Heuristic fallback: any system.* that has demand/overallAccesses and writebacks/tags, excluding system.cpu.*
    prefixes = set()
    for k in d.keys():
        m = re.match(r"^(system\.[^.]+)\.(demandAccesses|overallAccesses)::", k)
        if not m: continue
        pref = m.group(1)
        if pref.startswith("system.cpu."): continue
        if pick(d, [f"{pref}.writebacks::total", f"{pref}.writebacks::writebacks"]) is not None \
           or pick(d, [f"{pref}.tags.totalRefs"]) is not None:
            prefixes.add(pref)
    return list(prefixes)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stats")
    ap.add_argument("out_json")
    ap.add_argument("--tech", choices=["auto","sram","nvm"], default="auto",
                    help="Force energy tech profile for all llc parts (auto infers by name suffix)")
    ap.add_argument("--names", help="Comma list of cache prefixes (e.g., system.l3 or system.l3_sram,system.l3_nvm)")
    ap.add_argument("--line-size", type=float, default=64.0, help="Bytes per cache line for footprint bytes")
    args = ap.parse_args()

    d = parse_stats(args.stats)
    sim_s = d.get("simSeconds", d.get("simseconds", 0.0))

    if args.names:
        names = [n.strip() for n in args.names.split(",") if n.strip()]
    else:
        names = auto_find_llc_names(d)

    # Dedup to avoid double counting
    names = list(dict.fromkeys(names))

    if not names:
        tops = sorted({ ".".join(k.split(".",2)[:2]) for k in d if k.startswith("system.") })
        raise SystemExit(f"[error] No LLC-like caches found in {args.stats}.\n"
                         f"Try --names with one of: {', '.join(tops[:20])} ...")

    parts = []
    for n in names:
        if args.tech == "sram":
            prof = SRAM
        elif args.tech == "nvm":
            prof = NVM
        else:
            prof = NVM if n.endswith("_nvm") else SRAM
        e = energy_for_cache(d, n, prof, sim_s)
        f = features_stream_like(d, n, args.line_size)
        e["features"] = f
        parts.append(e)

    E_dyn_nJ = sum(p["E_dyn_nJ"] for p in parts)
    E_leak_J = sum(p["E_leak_J"] for p in parts)
    E_total_J = sum(p["E_total_J"] for p in parts)

    out = {
        "file": args.stats,
        "llc_parts": [p["name"] for p in parts],
        "sim_seconds": sim_s,
        "parts": parts,
        "E_dyn_nJ_total": E_dyn_nJ,
        "E_leak_J_total": E_leak_J,
        "E_total_J_total": E_total_J,
        "ED2P": E_total_J * (sim_s**2),
    }
    pathlib.Path(args.out_json).write_text(json.dumps(out, indent=2))
    print(f"[ok] wrote {args.out_json}")

if __name__ == "__main__":
    main()
