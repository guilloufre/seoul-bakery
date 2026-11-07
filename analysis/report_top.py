import json, os
R = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(R, "results.json"), encoding="utf-8"))
L = ["eligible " + str(d["meta"]["n_eligible"])]
for c in d["top10"]:
    L.append(f'{c["score"]} {c["gu"]} {c["dong"]} {c["name"]} [{c["type"]}] CAGR {c["cagr"]:.1%} flp {c["flp_g"]:+.1%} 2030 {c["age2030"]:.0%} F {c["female"]:.0%} WE {c["weekend"]:.0%} stores {c["stores0"]}->{c["stores"]} sales {c["sales0"]/1e8:.1f}->{c["sales1"]/1e8:.1f}억 {c["chg_nm"]} cls {c["clsrt"]} per {c["per_store"]/1e6:.0f}M')
L.append(str([(c["name"], c["score"]) for c in d["seongsu_ref"]]))
L.append(json.dumps(d["pick_detail"], ensure_ascii=False))
L.append(json.dumps(d["seoul"], ensure_ascii=False))
open(os.path.join(R, "top10.txt"), "w", encoding="utf-8").write("\n".join(L))
