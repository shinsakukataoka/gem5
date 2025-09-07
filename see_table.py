import json, pandas as pd
files = ["256k_sram.json","256k_nvm.json","2M_sram.json","2M_nvm.json","8M_sram.json","8M_nvm.json"]
rows=[]
for f in files:
    d=json.load(open(f))
    p=d["parts"][0]["features"]
    rows.append({
        "file":f,
        "tech":"sram" if "sram" in f else "nvm",
        "E_total_J":d["E_total_J_total"],
        "unique_write_lines":p.get("unique_write_lines",0.0),
        "p90_write_lines":p.get("p90_write_lines",0.0),
        "unique_read_lines":p.get("unique_read_lines",0.0),
        "p90_read_lines":p.get("p90_read_lines",0.0),
    })
df=pd.DataFrame(rows)
print("\nALL RUNS:\n", df, "\n")
for tech, g in df.groupby("tech"):
    corr = g[["E_total_J","unique_write_lines","p90_write_lines","unique_read_lines","p90_read_lines"]].corr(numeric_only=True)["E_total_J"].drop("E_total_J")
    print(f"=== Pearson correlations vs Energy ({tech.upper()}) ===\n{corr.sort_values(ascending=False).round(3)}\n")
