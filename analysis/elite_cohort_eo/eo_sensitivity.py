"""Sensitivity checks around the primary EO finding."""
from eo_panel import build_panel
from eo_model import sp, block_boot

def summarize(df, label):
    fns = {
        "EO":        lambda d: sp(d, "cohort_eo"),
        "own":       lambda d: sp(d, "sample_own"),
        "recent":    lambda d: sp(d, "recent_pts"),
        "EO-recent": lambda d: sp(d, "cohort_eo") - sp(d, "recent_pts"),
        "EO-own":    lambda d: sp(d, "cohort_eo") - sp(d, "sample_own"),
    }
    r = block_boot(df, fns, B=1500)
    def fmt(k):
        b, lo, hi = r[k]; flag = "" if (lo<=0<=hi) else "*"
        return f"{b:+.3f}[{lo:+.3f},{hi:+.3f}]{flag}"
    print(f"{label:38} n={len(df):>5}  EO={fmt('EO')}  own={fmt('own')}  recent={fmt('recent')}")
    print(f"{'':38}          EO-recent={fmt('EO-recent')}   EO-own={fmt('EO-own')}\n")

if __name__ == "__main__":
    print("Legend: value[95% CI]  * = CI excludes 0.  EO-own>0 would mean elite beats generic ownership.\n")
    summarize(build_panel(4), "PRIMARY: N=4 decile cohort")
    summarize(build_panel(8), "N=8 (upper horizon)")
    summarize(build_panel(4, ultra=True), "Ultra-elite: currently top-10K abs")
    summarize(build_panel(4, use_final=True), "FINAL-rank cohort (survivorship PEEK)")
    summarize(build_panel(4, cap_weight=True), "Captain-weighted EO")
    summarize(build_panel(4, cohort_frac=0.03), "Tighter cohort: top 3%")
    summarize(build_panel(4, gate_min_per_gw=60), "Stricter gate >=60 min/GW")
