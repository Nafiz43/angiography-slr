"""Build the submission graphical abstract: python3 analysis/11_graphical_abstract.py.

Left: included studies and how many use temporal information. Right: the four research-gap
clusters, each with its gaps (bar = included studies documenting the gap) and the mitigation
strategies (S codes) that address it; S1 spans all clusters. Counts are read from the committed
data (screening CSV, extraction/out) and the cluster/strategy mapping in 09_venn_diagram.py.
Output: graphical_abstract.{pdf,png}, 13 x 5 in (3900 x 1500 px).
"""
import ast
import csv
import glob
import json
import re
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

ROOT = Path(__file__).resolve().parents[1]

ns = {}
for node in ast.parse((ROOT / 'analysis/09_venn_diagram.py').read_text()).body:
    if isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', '') in {'CLUSTERS', 'COLOURS', 'INTERSECTIONS', 'UNIQUE'}:
        name = node.targets[0].id
        if name == 'INTERSECTIONS':
            ns[name] = {frozenset(ast.literal_eval(k.args[0])): ast.literal_eval(v)
                        for k, v in zip(node.value.keys, node.value.values)}
        elif name == 'COLOURS':
            ns[name] = {ast.literal_eval(k): {kw.arg: ast.literal_eval(kw.value) for kw in v.keywords}
                        for k, v in zip(node.value.keys, node.value.values)}
        else:
            ns[name] = ast.literal_eval(node.value)
clusters, colours, inter, unique = ns['CLUSTERS'], ns['COLOURS'], ns['INTERSECTIONS'], ns['UNIQUE']

screened = sum(1 for _ in csv.DictReader(open(ROOT / 'screening/stage1_llm_decisions.csv')))
cats = [json.load(open(f))['method'].get('temporal_category') for f in glob.glob(str(ROOT / 'extraction/out/R*.json'))]
studies = len(cats)
learned = sum(c in {'recurrent', 'cnn3d_video', 'transformer_ssm'} for c in cats)
fixed = sum(c in {'frame_aggregation', 'optical_flow_registration', 'hemodynamic_physics'} for c in cats)
rest = studies - learned - fixed
gap_total = sum(len(c['gaps']) for c in clusters.values())
evidence = {}  # included studies whose full text documents each gap (Table 7 evidence count)
for f in glob.glob(str(ROOT / 'extraction/out/R*.json')):
    for g, v in json.load(open(f))['gaps'].items():
        evidence[g] = evidence.get(g, 0) + (v['status'] in {'documents', 'both'})

INK, MUTED, GREY = '#1E2A38', '#6B7785', '#9AA5B1'
GAP_SHORT = {'G1': 'Public benchmarks', 'G2': 'Domain shift', 'G5': 'Annotation scarcity',
             'G10': 'Privacy & multi-site learning', 'G3': 'Temporal modeling', 'G4': '2D limits & 3D reconstruction',
             'G9': 'Rare pathology & imbalance', 'G6': 'Prospective validation', 'G7': 'Explainability',
             'G8': 'Multi-modal integration', 'G11': 'Outcome prediction', 'G12': 'LLMs & structured reporting'}
STRAT_SHORT = {'S1': 'Large multi-institutional annotated datasets', 'S2': 'Challenge benchmarks',
               'S3': 'Self-supervised pretraining', 'S4': 'Federated learning', 'S5': 'Domain adaptation',
               'S6': 'Video Transformers & SSMs', 'S7': 'Physics-informed 3D models',
               'S8': 'Label-efficient learning', 'S9': 'Uncertainty & OOD detection',
               'S10': 'Prospective multi-center RCTs', 'S11': 'Outcome-supervised training',
               'S12': 'Longitudinal outcome cohorts', 'S13': 'Vision-language report models',
               'S14': 'Generative augmentation'}
names = {'C1': 'Data infrastructure', 'C2': 'Modeling & learning', 'C3': 'Clinical deployment', 'C4': 'Outcome & reporting'}
codes = lambda txt: re.findall(r'S\d+', txt)
strat = {k: set(codes(unique.get(k, ''))) for k in clusters}
for keys, txt in inter.items():
    for k in keys:
        strat[k] |= set(codes(txt))
everywhere = set.intersection(*strat.values())  # S1, drawn once as a band under all clusters
n_strat = len(set.union(*strat.values()))

plt.rcParams.update({'font.family': 'DejaVu Sans', 'pdf.fonttype': 42})
fig = plt.figure(figsize=(13, 5))
ax = fig.add_axes([0, 0, 1, 1])
ax.set(xlim=(0, 13), ylim=(0, 5))
ax.axis('off')
ax.text(6.5, 4.68, 'AI for angiographic sequence analysis: research gaps and mitigation strategies',
        ha='center', va='center', fontsize=16, weight='bold', color=INK)

# Left: the evidence base.
ax.text(1.3, 3.35, f'{studies}', ha='center', va='center', fontsize=34, weight='bold', color=INK)
ax.text(1.3, 2.82, 'included studies', ha='center', va='center', fontsize=11, color=MUTED)
ax.text(1.3, 2.55, f'of {screened:,} screened', ha='center', va='center', fontsize=9.5, color=MUTED)
ax.text(1.3, 1.85, f'{(learned + fixed) / studies:.1%}', ha='center', va='center', fontsize=20, weight='bold', color=INK)
ax.text(1.3, 1.45, 'use temporal information,\nmostly shallowly', ha='center', va='center', fontsize=9.5,
        color=MUTED, linespacing=1.2)
ax.text(1.3, .82, f'{gap_total} gaps \u00b7 {n_strat} strategies', ha='center', va='center', fontsize=10, weight='bold', color=INK)
ax.add_patch(FancyArrowPatch((2.45, 2.55), (2.85, 2.55), arrowstyle='-|>', mutation_scale=16, color=GREY, lw=1.4))

# Right: one card per gap cluster.
W, PAD, X0, TOP, BOT = 2.33, .12, 2.95, 4.32, 1.0
emax = max(evidence.values())
for i, k in enumerate(clusters):
    c, x = colours[k], X0 + i * (W + PAD)
    ax.add_patch(FancyBboxPatch((x, BOT), W, TOP - BOT, boxstyle='round,pad=0,rounding_size=.06',
                                facecolor='white', edgecolor=c['edge'], lw=1.2))
    ax.add_patch(FancyBboxPatch((x, TOP - .34), W, .34, boxstyle='round,pad=0,rounding_size=.06',
                                facecolor=c['fill'], edgecolor=c['edge'], lw=1.2))
    ax.text(x + W / 2, TOP - .17, f'{k}  {names[k]}', ha='center', va='center', fontsize=10, weight='bold', color=c['txt'])
    ax.text(x + .1, TOP - .52, 'Research gaps', fontsize=7.5, color=MUTED, va='center', style='italic')
    ax.text(x + W - .1, TOP - .52, 'studies', fontsize=7.5, color=MUTED, va='center', ha='right', style='italic')
    for j, (g, _) in enumerate(clusters[k]['gaps']):
        y = TOP - .78 - j * .27
        ax.text(x + .1, y + .04, g, fontsize=8.5, weight='bold', color=c['txt'], va='center')
        ax.text(x + .5, y + .04, GAP_SHORT[g], fontsize=8, color=INK, va='center')
        ax.add_patch(Rectangle((x + .5, y - .13), (W - 1.0) * evidence[g] / emax, .06, facecolor=c['edge'], lw=0))
        ax.text(x + W - .1, y - .1, str(evidence[g]), fontsize=7.5, color=c['txt'], va='center', ha='right')
    ysep = TOP - .78 - 4 * .27 + .1
    ax.plot([x + .1, x + W - .1], [ysep, ysep], color=c['fill'], lw=1)
    ax.text(x + .1, ysep - .16, 'Mitigation strategies', fontsize=7.5, color=MUTED, va='center', style='italic')
    for j, sc in enumerate(sorted(strat[k] - everywhere, key=lambda t: int(t[1:]))):
        y = ysep - .36 - j * .2
        ax.text(x + .1, y, sc, fontsize=8, weight='bold', color=c['txt'], va='center')
        ax.text(x + .5, y, STRAT_SHORT[sc], fontsize=7.8, color=INK, va='center')

# Strategies shared by every cluster.
xr = X0 + 4 * W + 3 * PAD
ax.add_patch(FancyBboxPatch((X0, .45), xr - X0, .38, boxstyle='round,pad=0,rounding_size=.06',
                            facecolor='#EEF2F6', edgecolor=GREY, lw=1))
ax.text((X0 + xr) / 2, .64, '   '.join(f'{sc}  {STRAT_SHORT[sc]}' for sc in sorted(everywhere)) + '  (all clusters)',
        ha='center', va='center', fontsize=9, weight='bold', color=INK)
ax.text(6.5, .2, 'Bars: included studies whose full text documents each gap. Shared strategies appear under every cluster they address.',
        ha='center', va='center', fontsize=8, color=MUTED)

for ext in ('pdf', 'png'):
    fig.savefig(ROOT / f'graphical_abstract.{ext}', dpi=300, facecolor='white')
plt.close(fig)
print(f'{screened} screened, {studies} studies; learned {learned}, fixed {fixed}, none/not stated {rest}; '
      f'{gap_total} gaps, {n_strat} strategies; evidence {dict(sorted(evidence.items(), key=lambda t: int(t[0][1:])))}')
