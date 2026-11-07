"""Reproducible pipeline: Seoul Open Data (서울시 상권분석서비스) -> bakery growth-district scoring.

Usage: python analysis/fetch_and_score.py [API_KEY]
Fixed period: 2023Q2 (base) vs 2026Q2 (latest) — same season, 3 years apart.
Industry: CS100005 제과점. Outputs data/*.json and analysis/results.json.
"""
import json, os, sys, math, urllib.request
from concurrent.futures import ThreadPoolExecutor

KEY = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SEOUL_KEY", "")
BASE_Q, LAST_Q = "20232", "20262"
IND = "CS100005"  # 제과점
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data"); os.makedirs(DATA, exist_ok=True)


def get(svc, a, b, q=""):
    url = f"http://openapi.seoul.go.kr:8088/{KEY}/json/{svc}/{a}/{b}/{q}"
    for _ in range(3):
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                return json.loads(r.read().decode("utf-8"))[svc]
        except Exception:
            pass
    raise RuntimeError(url)


def fetch_all(svc, q=""):
    cache = os.path.join(DATA, f"{svc}_{q or 'all'}.json")
    if os.path.exists(cache):
        return json.load(open(cache, encoding="utf-8"))
    total = get(svc, 1, 1, q)["list_total_count"]
    pages = [(i, min(i + 999, total)) for i in range(1, total + 1, 1000)]
    with ThreadPoolExecutor(12) as ex:
        rows = [r for res in ex.map(lambda p: get(svc, p[0], p[1], q).get("row", []), pages) for r in res]
    json.dump(rows, open(cache, "w", encoding="utf-8"), ensure_ascii=False)
    return rows


def pct_rank(vals):
    s = sorted(vals); n = len(s)
    return [sum(1 for x in s if x <= v) / n for v in vals]


def main():
    relm = {r["TRDAR_CD"]: r for r in fetch_all("TbgisTrdarRelm")}
    sel = {q: {r["TRDAR_CD"]: r for r in fetch_all("VwsmTrdarSelngQq", q) if r["SVC_INDUTY_CD"] == IND} for q in (BASE_Q, LAST_Q)}
    sto = {q: {r["TRDAR_CD"]: r for r in fetch_all("VwsmTrdarStorQq", q) if r["SVC_INDUTY_CD"] == IND} for q in (BASE_Q, LAST_Q)}
    flp = {q: {r["TRDAR_CD"]: r for r in fetch_all("VwsmTrdarFlpopQq", q)} for q in (BASE_Q, LAST_Q)}
    ix = {r["TRDAR_CD"]: r for r in fetch_all("VwsmTrdarIxQq", LAST_Q)}

    cands = []
    for cd, s1 in sel[LAST_Q].items():
        s0 = sel[BASE_Q].get(cd); st1 = sto[LAST_Q].get(cd); st0 = sto[BASE_Q].get(cd)
        f0 = flp[BASE_Q].get(cd); f1 = flp[LAST_Q].get(cd); rl = relm.get(cd, {})
        if not (s0 and st1 and f0 and f1):
            continue
        a0, a1 = s0["THSMON_SELNG_AMT"], s1["THSMON_SELNG_AMT"]
        stores = st1["SIMILR_INDUTY_STOR_CO"] or st1["STOR_CO"]
        # eligibility: meaningful base & scale (avoid tiny-base CAGR noise)
        if s1["TRDAR_SE_CD_NM"] not in ("골목상권", "발달상권"):  # street retail only (mall/tourist zone, market excluded)
            continue
        if a0 < 1.5e8 or a1 < 3e8 or stores < 3:
            continue
        name = s1["TRDAR_CD_NM"]; dong = rl.get("ADSTRD_CD_NM", "")
        tot = a1 or 1
        age2030 = (s1["AGRDE_20_SELNG_AMT"] + s1["AGRDE_30_SELNG_AMT"]) / tot
        female = s1["FML_SELNG_AMT"] / tot
        weekend = s1["WKEND_SELNG_AMT"] / tot
        morning = (s1["TMZON_06_11_SELNG_AMT"]) / tot
        cagr = (a1 / a0) ** (1 / 3) - 1
        flp_g = f1["TOT_FLPOP_CO"] / f0["TOT_FLPOP_CO"] - 1
        per_store = a1 / stores
        clsrt = st1["CLSBIZ_RT"]
        stores0 = (st0["SIMILR_INDUTY_STOR_CO"] or st0["STOR_CO"]) if st0 else stores
        chg = ix.get(cd, {}).get("TRDAR_CHNGE_IX", "")
        mom = {"LH": 1.0, "LL": 0.8, "HH": 0.4, "HL": 0.0}.get(chg, 0.4)  # LH=상권확장, LL=다이나믹, HH=정체, HL=상권축소
        cands.append(dict(cd=cd, name=name, gu=rl.get("SIGNGU_CD_NM", ""), dong=dong, type=s1["TRDAR_SE_CD_NM"],
                          sales0=a0, sales1=a1, cnt1=s1["THSMON_SELNG_CO"], cagr=cagr, flp0=f0["TOT_FLPOP_CO"], flp1=f1["TOT_FLPOP_CO"], flp_g=flp_g,
                          age2030=age2030, female=female, weekend=weekend, morning=morning,
                          stores=stores, stores0=stores0, per_store=per_store, clsrt=clsrt, opbiz=st1["OPBIZ_RT"],
                          chg=chg, chg_nm=ix.get(cd, {}).get("TRDAR_CHNGE_IX_NM", ""), mom=mom,
                          excluded_seongsu=("성수" in name or "성수" in dong or "뚝섬" in name)))

    # MECE 4-axis scoring (percentile ranks within eligible set)
    def col(k): return [c[k] for c in cands]
    r = {k: pct_rank(col(k)) for k in ("cagr", "flp_g", "age2030", "female", "weekend", "per_store")}
    r_cls = pct_rank([-c["clsrt"] for c in cands])
    W = dict(demand=0.35, fit=0.25, room=0.25, momentum=0.15)
    for i, c in enumerate(cands):
        c["s_demand"] = 0.7 * r["cagr"][i] + 0.3 * r["flp_g"][i]
        c["s_fit"] = 0.5 * r["age2030"][i] + 0.25 * r["female"][i] + 0.25 * r["weekend"][i]
        c["s_room"] = 0.6 * r["per_store"][i] + 0.4 * r_cls[i]
        c["s_momentum"] = c["mom"]
        c["score"] = round(100 * (W["demand"] * c["s_demand"] + W["fit"] * c["s_fit"] + W["room"] * c["s_room"] + W["momentum"] * c["s_momentum"]), 1)
    cands.sort(key=lambda c: -c["score"])
    eligible = [c for c in cands if not c["excluded_seongsu"]]

    pick = eligible[0]
    s1 = sel[LAST_Q][pick["cd"]]; f1 = flp[LAST_Q][pick["cd"]]
    detail = dict(
        hours={k: s1[f"TMZON_{k}_SELNG_AMT"] for k in ("00_06", "06_11", "11_14", "14_17", "17_21", "21_24")},
        days={k: s1[f"{k}_SELNG_AMT"] for k in ("MON", "TUES", "WED", "THUR", "FRI", "SAT", "SUN")},
        ages={k: s1[f"AGRDE_{k}_SELNG_AMT"] for k in ("10", "20", "30", "40", "50", "60_ABOVE")},
        flpop_ages={k: f1[f"AGRDE_{k}_FLPOP_CO"] for k in ("10", "20", "30", "40", "50", "60_ABOVE")},
        avg_ticket=s1["THSMON_SELNG_AMT"] / max(s1["THSMON_SELNG_CO"], 1),
    )
    # Seoul-wide bakery benchmark
    seoul = dict(
        sales0=sum(x["THSMON_SELNG_AMT"] for x in sel[BASE_Q].values()),
        sales1=sum(x["THSMON_SELNG_AMT"] for x in sel[LAST_Q].values()),
        stores1=sum((x["SIMILR_INDUTY_STOR_CO"] or x["STOR_CO"]) for x in sto[LAST_Q].values()),
    )
    seoul["cagr"] = (seoul["sales1"] / seoul["sales0"]) ** (1 / 3) - 1
    out = dict(meta=dict(source="서울 열린데이터광장 · 서울시 상권분석서비스 (VwsmTrdarSelngQq 추정매출, VwsmTrdarStorQq 점포, VwsmTrdarFlpopQq 길단위인구, VwsmTrdarIxQq 상권변화지표, TbgisTrdarRelm 영역)",
                         period=f"{BASE_Q}(2023 2Q) vs {LAST_Q}(2026 2Q), 분기", industry="CS100005 제과점", unit="원(KRW), 명, 개",
                         weights=W, eligibility="골목·발달상권, 2023Q2 제과 매출 ≥1.5억, 2026Q2 ≥3억, 제과점 ≥3개", n_eligible=len(cands), reference="성수/뚝섬 상권 (같은 기준 참고 채점, 149개에 포함)"),
               seoul=seoul, pick=pick, pick_detail=detail, top10=eligible[:10],
               seongsu_ref=[c for c in cands if c["excluded_seongsu"]][:3])
    json.dump(out, open(os.path.join(ROOT, "analysis", "results.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for c in eligible[:10]:
        print(f'{c["score"]:5} {c["gu"]} {c["name"]} [{c["type"]}] CAGR {c["cagr"]:.1%} flp {c["flp_g"]:+.1%} 2030 {c["age2030"]:.0%} stores {c["stores"]:.0f} per {c["per_store"]/1e6:.0f}M cls {c["clsrt"]} {c["chg_nm"]}')
    print("eligible:", len(cands), "seoul bakery CAGR", f'{seoul["cagr"]:.1%}')


if __name__ == "__main__":
    main()
