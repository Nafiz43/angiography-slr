"""Inter-rater agreement for the 491-record screening validation sample and the
Appendix C table. Usage: python3 validation/screening_agreement.py"""
import csv, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
rows = list(csv.DictReader(open(os.path.join(HERE, "screening_double_annotation.csv"))))


def kappa(x, y):
    n = len(x)
    po = sum(a == b for a, b in zip(x, y)) / n
    px, py = x.count("include") / n, y.count("include") / n
    pe = px * py + (1 - px) * (1 - py)
    k = (po - pe) / (1 - pe)
    se = math.sqrt(po * (1 - po) / (n * (1 - pe) ** 2))
    return n, po, k, k - 1.96 * se, min(1.0, k + 1.96 * se)


def col(c):
    return [r[c] for r in rows]


for a, b in [("rater_REG", "rater_NIK"), ("pipeline", "final")]:
    n, po, k, lo, hi = kappa(col(a), col(b))
    print(f"{a} vs {b}: n={n} agree={po * n:.0f} ({100 * po:.1f}%) kappa={k:.3f} (95% CI {lo:.3f}-{hi:.3f})")
print("disagreements:", [r["record_id"] for r in rows if r["rater_REG"] != r["rater_NIK"]])

esc = lambda s: s.translate(str.maketrans({c: "\\" + c for c in "&%$#_{}"})).replace("~", r"\textasciitilde{}").replace("^", r"\^{}")
ab = lambda s: s[0].upper()
out = [r"""\renewcommand{\arraystretch}{1.05}
\footnotesize
\onecolumn
\begin{longtable}{@{}l p{8.6cm} c c c c@{}}
\caption{Title/abstract screening validation sample: all 134 records the pipeline labelled INCLUDE (census) and 357 randomly sampled records it labelled EXCLUDE (Section~\ref{sec:validation}). \textbf{R1} and \textbf{R2}: independent decisions of the two human reviewers (I = include, E = exclude). \textbf{Final}: consensus label after discussion ($^{\dagger}$ marks the four records on which the reviewers initially disagreed). \textbf{Pipeline}: stage-1 LLM screening decision.}
\label{tab:screening_validation_full} \\
\toprule
\textbf{Record} & \textbf{Title} & \textbf{R1} & \textbf{R2} & \textbf{Final} & \textbf{Pipeline} \\
\midrule
\endfirsthead
\multicolumn{6}{c}{\tablename~\thetable{} -- \textit{continued from previous page}} \\
\toprule
\textbf{Record} & \textbf{Title} & \textbf{R1} & \textbf{R2} & \textbf{Final} & \textbf{Pipeline} \\
\midrule
\endhead
\midrule
\multicolumn{6}{r}{\textit{Continued on next page}} \\
\endfoot
\bottomrule
\endlastfoot"""]
for r in rows:
    dag = r"$^{\dagger}$" if r["rater_REG"] != r["rater_NIK"] else ""
    out.append(f"{r['record_id']} & {esc(r['title'].strip())} & {ab(r['rater_REG'])} & {ab(r['rater_NIK'])} & {ab(r['final'])}{dag} & {ab(r['pipeline'])} \\\\")
out += [r"\end{longtable}"]
open(os.path.join(HERE, "screening_validation_table.tex"), "w").write("\n".join(out) + "\n")
