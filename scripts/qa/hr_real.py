import json
import sys

import pymannkendall as mk

data = json.load(open(sys.argv[1], encoding="utf-8-sig"))
for site in data["sites"]:
    for var in site["variables"]:
        values = [p["value"] for p in var["annual_series"]]
        classic = mk.original_test(values)
        hr = mk.hamed_rao_modification_test(values)
        print(f"{site['location']['label']:9} {var['variable']:18} p_clasico={classic.p:.4f} p_HR={hr.p:.4f} varS_ratio={hr.var_s / classic.var_s:.3f} sen={hr.slope:+.5f}")
