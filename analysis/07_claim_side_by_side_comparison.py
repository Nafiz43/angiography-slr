"""
CLAIM-informed Reporting Completeness Forest Plot  —  Temporal Comparison
AngioVision Systematic Review (PRISMA)

Outputs:
  - forest_plot_claim2024_comparison.pdf   (figure)
  - claim2024_comparison_proportions.csv   (data)
  - claim2024_summary_table.tex            (LaTeX table for paper)

Usage:
    python3 claim2024_forest_plot.py
    python3 claim2024_forest_plot.py --input results/claim2024_results.jsonl
    python3 claim2024_forest_plot.py --input results/claim2024_results.jsonl \
                                     --out_dir figures/ --split_year 2024
"""

# Shared helpers — see slrlib/ (was duplicated inline; slrlib/test_slrlib.py proves parity)
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from slrlib import ensure as _ensure, wilson_ci_prop as wilson_ci, load_jsonl

import subprocess, sys

_ensure("matplotlib"); _ensure("numpy"); _ensure("pandas")

import argparse, json, math, os, textwrap
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

# ── Font sizes ────────────────────────────────────────────────────────────────
# Drawn at the manuscript text width (6.84 in): 8 pt here prints at 8 pt.
FS_CLUSTER_LABEL = 8   # Y-axis cluster names
FS_ITEMS_BADGE   = 8   # "Items 1–2" right axis
FS_PCT_LABEL     = 8   # "72%" annotations
FS_SECTION_BAND  = 8   # italic section labels inside bands
FS_X_TICK        = 8
FS_X_LABEL       = 8
FS_REF_LINE      = 8
FS_LEGEND_TITLE  = 8
FS_LEGEND_BODY   = 8

# ── Cluster definitions ───────────────────────────────────────────────────────
CLAIM2024_CLUSTERS = [  # official CLAIM 2024 checklist subsections
    {"cluster_id": "1-2", "cluster_label": "Title & abstract", "section": "Title/Abstract", "items_covered": "1–2"},
    {"cluster_id": "3-4", "cluster_label": "Introduction", "section": "Introduction", "items_covered": "3–4"},
    {"cluster_id": "5-6", "cluster_label": "Study design", "section": "Methods", "items_covered": "5–6"},
    {"cluster_id": "7-13", "cluster_label": "Data", "section": "Methods", "items_covered": "7–13"},
    {"cluster_id": "14-18", "cluster_label": "Reference standard", "section": "Methods", "items_covered": "14–18"},
    {"cluster_id": "19-20", "cluster_label": "Data partitions", "section": "Methods", "items_covered": "19–20"},
    {"cluster_id": "21", "cluster_label": "Testing data", "section": "Methods", "items_covered": "21"},
    {"cluster_id": "22-24", "cluster_label": "Model", "section": "Methods", "items_covered": "22–24"},
    {"cluster_id": "25-27", "cluster_label": "Training", "section": "Methods", "items_covered": "25–27"},
    {"cluster_id": "28-34", "cluster_label": "Evaluation", "section": "Methods", "items_covered": "28–34"},
    {"cluster_id": "35-36", "cluster_label": "Data", "section": "Results", "items_covered": "35–36"},
    {"cluster_id": "37-39", "cluster_label": "Model performance", "section": "Results", "items_covered": "37–39"},
    {"cluster_id": "40-41", "cluster_label": "Discussion", "section": "Discussion", "items_covered": "40–41"},
    {"cluster_id": "42-44", "cluster_label": "Other information", "section": "Other information", "items_covered": "42–44"},
]

SECTION_COLORS = {
    "Title/Abstract":               "#4C72B0",
    "Introduction":                 "#55A868",
    "Methods":                      "#C44E52",
    "Results":                      "#DD8452",
    "Discussion":                   "#8172B2",
    "Other information":            "#937860",
}

DEFAULT_INPUT   = "../results/claim2024_results.jsonl"
DEFAULT_OUT_DIR = "../analysis-results"
DEFAULT_SPLIT   = 2024


# ── Wilson CI ─────────────────────────────────────────────────────────────────
# ── IO ────────────────────────────────────────────────────────────────────────
def split_by_year(records, split_year):
    pre, post, unknown = [], [], []
    for rec in records:
        if "_error" in rec: continue
        try:
            y = int(rec.get("year"))
            (pre if y <= split_year else post).append(rec)
        except (TypeError, ValueError):
            unknown.append(rec)
    return pre, post, unknown


def compute_proportions(records):
    rows = []
    for c in CLAIM2024_CLUSTERS:
        cid = c["cluster_id"]
        yes = no = na = 0
        for rec in records:
            adh  = rec.get("claim2024_adherence", {})
            val  = None
            if isinstance(adh, dict):
                cell = adh.get(cid, {})
                val  = cell.get("adherence") if isinstance(cell, dict) else cell
            if   val == "Yes": yes += 1
            elif val == "No":  no  += 1
            elif val == "NA":  na  += 1
        n_total = yes + no
        prop    = yes / n_total if n_total > 0 else 0.0
        lo, hi  = wilson_ci(prop, n_total)
        rows.append({
            "cluster_id":    cid,
            "cluster_label": c["cluster_label"],
            "section":       c["section"],
            "items_covered": c["items_covered"],
            "n_yes": yes, "n_no": no, "n_na": na,
            "n_total": n_total,
            "proportion": prop,
            "ci_lower": lo, "ci_upper": hi,
        })
    return rows


# ── Section band drawing ──────────────────────────────────────────────────────
def _draw_section_bands(ax, rows_reversed, show_labels=True):
    n = len(rows_reversed)
    i = 0
    while i < n:
        sec   = rows_reversed[i]["section"]
        start = i
        while i < n and rows_reversed[i]["section"] == sec:
            i += 1
        end = i - 1
        ax.axhspan(
            start - 0.5, end + 0.5,
            color=SECTION_COLORS[sec], alpha=0.08, zorder=0, linewidth=0,
        )
        if show_labels:
            mid_y = (start + end) / 2
            ax.text(
                0.01, mid_y,
                sec,
                va="center", ha="left",
                fontsize=FS_SECTION_BAND,
                color=SECTION_COLORS[sec],
                fontstyle="italic",
                fontweight="bold",
                alpha=0.55,
                zorder=1,
                clip_on=True,
            )


# ── Single panel ──────────────────────────────────────────────────────────────
def _draw_panel(ax, prop_rows, n_studies, show_ylabels, show_right_axis, show_section_labels=False):
    rows = list(reversed(prop_rows))   # C01 at top
    n    = len(rows)
    y    = list(range(n))

    _draw_section_bands(ax, rows, show_labels=show_section_labels)

    # Reference lines
    ax.axvline(0.50, color="#aaaaaa", linestyle="--", linewidth=1.0, alpha=0.7, zorder=1)
    ax.axvline(0.75, color="#cccccc", linestyle=":",  linewidth=1.0, alpha=0.6, zorder=1)

    for i, row in enumerate(rows):
        p   = row["proportion"]
        lo  = row["proportion"] - row["ci_lower"]
        hi  = row["ci_upper"]   - row["proportion"]
        col = SECTION_COLORS[row["section"]]

        # CI line
        ax.plot([p - lo, p + hi], [y[i], y[i]],
                color=col, linewidth=2.2, solid_capstyle="round", zorder=3)
        # Caps
        for xpos in [p - lo, p + hi]:
            ax.plot([xpos, xpos], [y[i] - 0.18, y[i] + 0.18],
                    color=col, linewidth=1.8, zorder=3)
        # Diamond
        dx, dy = 0.013, 0.30
        diamond = plt.Polygon(
            [[p, y[i]+dy], [p+dx, y[i]], [p, y[i]-dy], [p-dx, y[i]]],
            closed=True, facecolor=col, edgecolor="white", linewidth=0.9, zorder=4,
        )
        ax.add_patch(diamond)

        # % label
        ax.text(p + hi + 0.016, y[i], f"{p*100:.0f}%",
                va="center", fontsize=FS_PCT_LABEL, color="#222222", zorder=5,
                fontweight="medium")

    # Y-axis cluster labels
    ax.set_yticks(y)
    if show_ylabels:
        ax.set_yticklabels(
            [textwrap.fill(r["cluster_label"], 28) for r in rows],
            fontsize=FS_CLUSTER_LABEL, color="#111111",
        )
    else:
        # Hide only this panel's labels; the formatter is shared with the left.
        ax.tick_params(axis="y", labelleft=False, length=0)

    # Right axis — items badge
    if show_right_axis:
        ax2 = ax.twinx()
        ax2.set_ylim(ax.get_ylim())
        ax2.set_yticks(y)
        ax2.set_yticklabels(
            [f"{r['items_covered']}" for r in rows],
            fontsize=FS_ITEMS_BADGE, color="#777777",
        )
        ax2.tick_params(axis="y", length=0)
        ax2.spines[["top", "left", "bottom"]].set_visible(False)

    # Axis styling
    ax.set_xlim(0.0, 1.3)
    ax.set_ylim(-0.7, n - 0.3)
    ax.set_xlabel("Proportion  (95% Wilson CI)", fontsize=FS_X_LABEL, labelpad=8)
    ax.set_xticks([0, 0.25, 0.50, 0.75, 1.0])
    ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"], fontsize=FS_X_TICK)
    ax.grid(axis="x", linestyle="--", alpha=0.25, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)

    # Ref-line labels at bottom




# ── Main figure ───────────────────────────────────────────────────────────────
def draw_comparison_plot(pre_rows, post_rows, n_pre, n_post, split_year, out_dir):
    n     = len(CLAIM2024_CLUSTERS)
    fig_h = 5.4

    fig, (ax_l, ax_r) = plt.subplots(
        1, 2,
        figsize=(6.84, fig_h),
        sharey=True,
        gridspec_kw=dict(wspace=0.05, left=0.27, right=0.91, top=0.94, bottom=0.21),
    )

    # Section names are already conveyed by the shared legend below, so the
    # in-plot italic band labels are omitted on both panels to avoid
    # overlapping with cluster rows (e.g. "Reproducibility & Transparency").
    _draw_panel(ax_l, pre_rows,  n_studies=n_pre,
                show_ylabels=True, show_right_axis=False, show_section_labels=False)

    _draw_panel(ax_r, post_rows, n_studies=n_post,
                show_ylabels=False, show_right_axis=True, show_section_labels=False)

    ax_l.set_title(f"≤{split_year}", fontsize=FS_X_LABEL, pad=8)
    ax_r.set_title(f">{split_year}", fontsize=FS_X_LABEL, pad=8)

    # Vertical divider
    fig.add_artist(
        plt.Line2D(
            [0.59, 0.59], [0.21, 0.97],  # midway between the panels
            transform=fig.transFigure,
            color="#cccccc", linewidth=1.2, linestyle="--",
        )
    )

    # Legend
    handles = []
    seen    = []
    for c in CLAIM2024_CLUSTERS:
        if c["section"] not in seen:
            seen.append(c["section"])
            handles.append(
                mpatches.Patch(
                    facecolor=SECTION_COLORS[c["section"]],
                    edgecolor="white", linewidth=0.5,
                    label=c["section"],
                )
            )
    fig.legend(
        handles=handles,
        title="Reporting category",
        title_fontsize=FS_LEGEND_TITLE,
        fontsize=FS_LEGEND_BODY,
        loc="lower center",
        ncol=3,
        bbox_to_anchor=(0.5, 0.0),
        framealpha=0.95,
        edgecolor="#cccccc",
        handlelength=1.4,
        handleheight=1.0,
    )


    os.makedirs(out_dir, exist_ok=True)
    pdf = os.path.join(out_dir, "forest_plot_claim2024_comparison.pdf")
    png = os.path.join(out_dir, "forest_plot_claim2024_comparison.png")
    fig.savefig(pdf, dpi=300)
    fig.savefig(png, dpi=300)
    plt.close(fig)
    print(f"Saved: {pdf}")
    print(f"Saved: {png}")


# ── Summary CSV ───────────────────────────────────────────────────────────────
def save_comparison_csv(pre_rows, post_rows, split_year, out_dir):
    rows = []
    for pre, post in zip(pre_rows, post_rows):
        rows.append({
            "cluster_id":    pre["cluster_id"],
            "cluster_label": pre["cluster_label"],
            "section":       pre["section"],
            "items_covered": pre["items_covered"],
            "pre_n":         pre["n_total"],
            "pre_yes":       pre["n_yes"],
            "pre_pct":       round(pre["proportion"]*100, 1),
            "pre_ci_lo":     round(pre["ci_lower"]*100,   1),
            "pre_ci_hi":     round(pre["ci_upper"]*100,   1),
            "post_n":        post["n_total"],
            "post_yes":      post["n_yes"],
            "post_pct":      round(post["proportion"]*100, 1),
            "post_ci_lo":    round(post["ci_lower"]*100,   1),
            "post_ci_hi":    round(post["ci_upper"]*100,   1),
        })
    df = pd.DataFrame(rows)
    os.makedirs(out_dir, exist_ok=True)
    csv = os.path.join(out_dir, "claim2024_comparison_proportions.csv")
    df.to_csv(csv, index=False)
    print(f"Comparison CSV: {csv}")


# ── Console table ─────────────────────────────────────────────────────────────
def print_console_table(pre_rows, post_rows, split_year):
    leq      = "\u2264"
    geq      = "\u2265"
    delta    = "\u0394"
    up       = "\u25b2"
    down     = "\u25bc"
    pre_hdr  = leq + str(split_year)
    post_hdr = geq + str(split_year + 1)
    w = 82
    print("\n" + "="*w)
    print(f"  CLAIM 2024  |  {leq}{split_year}  vs  {geq}{split_year+1}")
    print("="*w)
    print(f"{'ID':<5} {'Cluster':<42}  {pre_hdr:>7}  {post_hdr:>7}  {delta:>7}")
    print("\u2500"*w)
    for pre, post in zip(pre_rows, post_rows):
        d = post["proportion"] - pre["proportion"]
        a = up if d > 0.02 else (down if d < -0.02 else "~")
        print(f"{pre['cluster_id']:<5} {pre['cluster_label'][:41]:<42} "
              f" {pre['proportion']*100:>6.1f}%  {post['proportion']*100:>6.1f}%  "
              f"{a}{abs(d)*100:>5.1f}%")
    print("="*w)


# ── LaTeX table ───────────────────────────────────────────────────────────────
def save_latex_table(pre_rows, post_rows, split_year, out_dir, n_pre, n_post):
    """
    Generates a publication-ready LaTeX longtable with:
      - Section colour grouping via \rowcolor
      - Pre / Post columns with CI
      - Delta column with upward/downward arrows
    """
    SEC_TEX_COLOR = {
        "Title/Abstract":               "claimTA",
        "Introduction":                 "claimIntro",
        "Methods":                      "claimMeth",
        "Results":                      "claimRes",
        "Discussion":                   "claimDisc",
        "Other information":"claimRepro",
    }
    SEC_HEX = {
        "Title/Abstract":               "4C72B0",
        "Introduction":                 "55A868",
        "Methods":                      "C44E52",
        "Results":                      "DD8452",
        "Discussion":                   "8172B2",
        "Other information":"937860",
    }

    lines = []
    lines.append(r"% ─────────────────────────────────────────────────────────────────────")
    lines.append(r"% CLAIM-informed Reporting Completeness — Temporal Comparison Table")
    lines.append(r"% Auto-generated by claim2024_forest_plot.py")
    lines.append(r"% Required packages: booktabs, longtable, xcolor, colortbl, array, multirow")
    lines.append(r"% ─────────────────────────────────────────────────────────────────────")
    lines.append(r"")
    lines.append(r"% Colour definitions (put in preamble once)")
    for sec, hex_ in SEC_HEX.items():
        cname = SEC_TEX_COLOR[sec]
        lines.append(f"\\definecolor{{{cname}}}{{HTML}}{{{hex_}}}")
    lines.append(r"")

    lines.append(r"\begin{longtable}{@{} l l r r r r r r @{}}")
    lines.append(r"  \caption{CLAIM-informed Reporting Completeness by Thematic Cluster: Temporal Comparison"
                 r" ($\leq " + str(split_year) + r"$ vs.\ $\geq " + str(split_year+1) + r"$).}")
    lines.append(r"  \label{tab:claim2024_temporal} \\")
    lines.append(r"  \toprule")
    lines.append(r"  \multicolumn{1}{l}{\textbf{ID}} &")
    lines.append(r"  \multicolumn{1}{l}{\textbf{Cluster}} &")
    lines.append(r"  \multicolumn{3}{c}{$\boldsymbol{\leq " + str(split_year) + r"}$"
                 r"  \textbf{(N\,=\," + str(n_pre) + r")}} &")
    lines.append(r"  \multicolumn{3}{c}{$\boldsymbol{\geq " + str(split_year+1) + r"}$"
                 r"  \textbf{(N\,=\," + str(n_post) + r")}} \\")
    lines.append(r"  \cmidrule(lr){3-5} \cmidrule(lr){6-8}")
    lines.append(r"  & & \textbf{\%} & \textbf{95\% CI} & $\boldsymbol{\Delta}$ &"
                 r" \textbf{\%} & \textbf{95\% CI} & $\boldsymbol{\Delta}$ \\")
    lines.append(r"  \midrule")
    lines.append(r"  \endfirsthead")
    lines.append(r"")
    lines.append(r"  \multicolumn{8}{c}{{\tablename\ \thetable{} --- continued}} \\")
    lines.append(r"  \toprule")
    lines.append(r"  \multicolumn{1}{l}{\textbf{ID}} &")
    lines.append(r"  \multicolumn{1}{l}{\textbf{Cluster}} &")
    lines.append(r"  \multicolumn{3}{c}{$\boldsymbol{\leq " + str(split_year) + r"}$} &")
    lines.append(r"  \multicolumn{3}{c}{$\boldsymbol{\geq " + str(split_year+1) + r"}$} \\")
    lines.append(r"  \cmidrule(lr){3-5} \cmidrule(lr){6-8}")
    lines.append(r"  & & \textbf{\%} & \textbf{95\% CI} & $\boldsymbol{\Delta}$ &"
                 r" \textbf{\%} & \textbf{95\% CI} & $\boldsymbol{\Delta}$ \\")
    lines.append(r"  \midrule")
    lines.append(r"  \endhead")
    lines.append(r"")
    lines.append(r"  \midrule")
    lines.append(r"  \multicolumn{8}{r}{{Continued on next page}} \\")
    lines.append(r"  \endfoot")
    lines.append(r"")
    lines.append(r"  \bottomrule")
    lines.append(r"  \endlastfoot")
    lines.append(r"")

    prev_section = None
    for pre, post in zip(pre_rows, post_rows):
        sec     = pre["section"]
        cname   = SEC_TEX_COLOR[sec]
        d       = post["proportion"] - pre["proportion"]
        arrow   = r"$\uparrow$" if d > 0.02 else (r"$\downarrow$" if d < -0.02 else r"$\sim$")

        if sec != prev_section:
            if prev_section is not None:
                lines.append(r"  \midrule")
            lines.append(f"  \\rowcolor{{{cname}!15}}")
            lines.append(f"  \\multicolumn{{8}}{{l}}"
                         f"{{\\textbf{{\\textcolor{{{cname}}}{{{sec}}}}}}} \\\\")
            prev_section = sec

        pre_ci  = f"[{pre['ci_lower']*100:.0f}, {pre['ci_upper']*100:.0f}]"
        post_ci = f"[{post['ci_lower']*100:.0f}, {post['ci_upper']*100:.0f}]"
        delta_s = f"{'+' if d>=0 else ''}{d*100:.0f}\\%"

        lines.append(
            f"  {pre['cluster_id']} & "
            f"{pre['cluster_label']} & "
            f"{pre['proportion']*100:.0f}\\% & "
            f"{pre_ci} & "
            f"& "
            f"{post['proportion']*100:.0f}\\% & "
            f"{post_ci} & "
            f"{delta_s}~{arrow} \\\\"
        )

    lines.append(r"")
    lines.append(r"  \midrule")
    lines.append(r"  \multicolumn{8}{l}{\textit{Note:} Proportions are the fraction of"
                 r" studies reporting adherence (``Yes'') among those where the item was"
                 r" applicable (NA excluded). 95\% Wilson confidence intervals shown."
                 r" $\Delta$ = post\,--\,pre; arrows indicate $>$2\,pp change.} \\")
    lines.append(r"\end{longtable}")

    os.makedirs(out_dir, exist_ok=True)
    tex_path = os.path.join(out_dir, "claim2024_summary_table.tex")
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"LaTeX table:   {tex_path}")


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="CLAIM 2024 side-by-side temporal forest plot + LaTeX table"
    )
    parser.add_argument("--input",      default=DEFAULT_INPUT)
    parser.add_argument("--out_dir",    default=DEFAULT_OUT_DIR)
    parser.add_argument("--split_year", default=DEFAULT_SPLIT, type=int)
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: '{args.input}' not found."); sys.exit(1)

    records = load_jsonl(args.input)
    valid   = [r for r in records if "_error" not in r]
    pre, post, unknown = split_by_year(valid, args.split_year)

    leq = "\u2264"
    geq = "\u2265"
    print(f"Loaded {len(records)} records ({len(valid)} valid)")
    print(f"  {leq} {args.split_year}: {len(pre)}   {geq} {args.split_year+1}: {len(post)}"
          f"   unknown year: {len(unknown)}")

    if not pre and not post:
        print("No records in either cohort. Aborting."); sys.exit(1)

    pre_rows  = compute_proportions(pre)
    post_rows = compute_proportions(post)

    print_console_table(pre_rows, post_rows, args.split_year)
    save_comparison_csv(pre_rows, post_rows, args.split_year, args.out_dir)
    draw_comparison_plot(pre_rows, post_rows,
                         n_pre=len(pre), n_post=len(post),
                         split_year=args.split_year,
                         out_dir=args.out_dir)
    save_latex_table(pre_rows, post_rows,
                     split_year=args.split_year,
                     out_dir=args.out_dir,
                     n_pre=len(pre), n_post=len(post))

if __name__ == "__main__":
    main()