"""Fisher's exact test (two-sided) per CLAIM 2024 cluster, <=2024 vs >=2025, Holm-adjusted.
Reads ../analysis-results/claim2024_comparison_proportions.csv written by 07_claim_side_by_side_comparison.py."""
import csv
from scipy.stats import fisher_exact

rows = list(csv.DictReader(open("../analysis-results/claim2024_comparison_proportions.csv")))
p = []
for r in rows:
    a, n1, b, n2 = (int(r[k]) for k in ("pre_yes", "pre_n", "post_yes", "post_n"))
    p.append(fisher_exact([[a, n1 - a], [b, n2 - b]])[1])
order, adj, run = sorted(range(len(p)), key=p.__getitem__), [0.0] * len(p), 0.0
for k, i in enumerate(order):
    run = max(run, min(1.0, (len(p) - k) * p[i])); adj[i] = run
print("cluster  pre  post  delta_pp  p  p_holm")
for r, pi, ai in zip(rows, p, adj):
    d = 100 * (int(r["post_yes"]) / int(r["post_n"]) - int(r["pre_yes"]) / int(r["pre_n"]))
    print(f'{r["cluster_id"]}  {r["pre_yes"]}/{r["pre_n"]}  {r["post_yes"]}/{r["post_n"]}  {d:+.0f}  {pi:.3f}  {ai:.3f}')
