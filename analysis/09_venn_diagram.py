"""
========================================================
  SLR Venn Diagram – fully self-contained, no file input
  Edit the DATA SECTION below to update any content.
  Run:  python3 venn_diagram.py
  Output: venn_diagram.pdf  +  venn_diagram.png
========================================================
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch

CLUSTERS = {
    'C1': {
        'name'  : 'Data Infrastructure',
        'gaps'  : [
            ('G1',  'Absence of public benchmarks'),
            ('G2',  'Generalizability & domain shift'),
            ('G5',  'Annotation scarcity'),
            ('G10', 'Privacy-preserving &\nmulti-institutional learning'),
        ],
    },
    'C2': {
        'name'  : 'Modeling & Learning',
        'gaps'  : [
            ('G3',  'Temporal modeling & video-level analysis'),
            ('G4',  '2D constraints & 3D reconstruction'),
            ('G9',  'Class imbalance & \n rare pathology coverage'),
        ],
    },
    'C3': {
        'name'  : 'Clinical Deployment',
        'gaps'  : [
            ('G6',  'Clinical validation'),
            ('G7',  'Explainability & \n model transparency'),
            ('G8',  'Multi-modal data integration'),
        ],
    },
    'C4': {
        'name'  : 'Outcome & Reporting',
        'gaps'  : [
            ('G11', 'Clinical outcome prediction'),
            ('G12', 'LLMs & structured reporting'),
        ],
    },
}

STRATEGIES = [
    ('S1',  'Large-scale multi-institutional\nannotated angiographic datasets'),
    ('S2',  'Dedicated challenge benchmarks\nwith standardized evaluation metrics'),
    ('S3',  'Self-supervised / foundation model\npretraining on unlabeled fluoroscopic video'),
    ('S4',  'Federated learning with data-use\nagreements & audit mechanisms'),
    ('S5',  'Domain adaptation for contrast,\ndose, frame rate, and motion'),
    ('S6',  'Video Transformer architectures\nwith long-range attention & SSMs'),
    ('S7',  'Physics-informed networks with\nprojection geometry & multi-view fusion'),
    ('S8',  'Semi-supervised, active &\nself-supervised learning for annotation'),
    ('S9',  'Uncertainty quantification &\nOOD failure detection'),
    ('S10', 'Prospective multi-center RCTs\nwith clinical outcome endpoints'),
    ('S11', 'Outcome-supervised training for\nclinically meaningful prediction'),
    ('S12', 'Longitudinal cohort datasets linking\nimaging to clinical endpoints'),
    ('S13', 'Vision-language models for image\n& free-text report integration'),
    ('S14', 'Generative augmentation &\nrare-event simulation pipelines'),
]

INTERSECTIONS = {
    frozenset(['C1', 'C2'])             : 'S3, S14',
    frozenset(['C2', 'C3'])             : 'S9',
    frozenset(['C1', 'C4'])             : '—',
    frozenset(['C3', 'C4'])             : 'S10, S11,\nS12, S13',
    frozenset(['C1', 'C3'])             : '—',
    frozenset(['C2', 'C4'])             : '—',
    frozenset(['C1', 'C2', 'C3'])       : 'S8',
    frozenset(['C1', 'C2', 'C4'])       : '—',
    frozenset(['C2', 'C3', 'C4'])       : '—',
    frozenset(['C1', 'C3', 'C4'])       : '—',
    frozenset(['C1', 'C2', 'C3', 'C4']) : 'S1',
}

UNIQUE = {
    'C1': 'S2, S4, S5',
    'C2': 'S6, S7',
    'C3': '—',
    'C4': '—',
}

COLOURS = {
    'C1': dict(fill='#CECBF6', edge='#534AB7', txt='#26215C'),
    'C2': dict(fill='#9FE1CB', edge='#0F6E56', txt='#04342C'),
    'C3': dict(fill='#F5C4B3', edge='#993C1D', txt='#4A1B0C'),
    'C4': dict(fill='#FAC775', edge='#854F0B', txt='#412402'),
}

# Drawn at the manuscript text width (6.84 in) without cropping, so 8 pt here
# prints at 8 pt, the caption size.
from pathlib import Path
import textwrap
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'analysis-results'
OUT.mkdir(exist_ok=True)
# ponytail: list panels keep their old absolute size; the extra height all goes to the Venn.
H = 8.2
fig = plt.figure(figsize=(6.84, H), facecolor='white')
ax = fig.add_axes([0, 4.351/H, 1, 1-4.351/H])
ax.set(xlim=(-3.5, 3.5), ylim=(-2.32, 2.32), aspect='equal')
ax.axis('off')
centres = {'C1':(-1.25,0), 'C2':(0,1.05), 'C3':(1.25,0), 'C4':(0,-1.05)}
for k,(x,y) in centres.items():
    ax.add_patch(Circle((x,y),1.25,fc=COLOURS[k]['fill'],ec=COLOURS[k]['edge'],alpha=.45,lw=1.3))
labels = {'C1':(-1.78,0), 'C2':(0,1.75), 'C3':(1.78,0), 'C4':(0,-1.75)}
for k,(x,y) in labels.items():
    gaps=', '.join(g[0] for g in CLUSTERS[k]['gaps'])
    ax.text(x,y,'\n'+gaps+'\nUnique: '+UNIQUE[k],ha='center',va='center',fontsize=8,color=COLOURS[k]['txt'])
    ax.text(x,y+0.13,k,ha='center',va='center',fontsize=10,weight='bold',style='italic',color=COLOURS[k]['txt'])
positions = {frozenset(['C1','C2']):(-.85,.85),frozenset(['C2','C3']):(.85,.85),frozenset(['C1','C4']):(-.85,-.85),frozenset(['C3','C4']):(.85,-.85),frozenset(['C1','C2','C3']):(0,.57),frozenset(['C1','C2','C3','C4']):(0,0)}
for region,(x,y) in positions.items():
    label=INTERSECTIONS[region]
    if label == '—':
        continue
    ax.text(x,y,label,ha='center',va='center',fontsize=8,weight='bold')
R=fig.canvas.get_renderer()
def below(t,panel,gap):
    # Next entry starts under the drawn text, so wrapped lines never collide.
    return t.get_window_extent(R).transformed(panel.transAxes.inverted()).y0-gap
left=fig.add_axes([.025,.037/H,.45,4.255/H]); right=fig.add_axes([.515,.037/H,.46,4.255/H])
for panel in (left,right):
    panel.set(xlim=(0,1),ylim=(0,1)); panel.axis('off')
left.text(0,1,'Research gaps',fontsize=8,weight='bold',va='top')
y=.94
for k,cluster in CLUSTERS.items():
    y=below(left.text(0,y,k+'  '+cluster['name'],fontsize=8,weight='bold',color=COLOURS[k]['txt'],va='top'),left,.014)
    for code,desc in cluster['gaps']:
        lines=textwrap.fill(' '.join(desc.split()),44)
        left.text(0,y,code,fontsize=8,weight='bold',va='top')
        y=below(left.text(.13,y,lines,fontsize=8,va='top',linespacing=1.1),left,.008)
    y-=.022
right.text(0,1,'Mitigation strategies',fontsize=8,weight='bold',va='top')
y=.94
for code,desc in STRATEGIES:
    lines=textwrap.fill(' '.join(desc.split()),50)
    right.text(0,y,code,fontsize=8,weight='bold',va='top')
    y=below(right.text(.12,y,lines,fontsize=8,va='top',linespacing=1.1),right,.008)
for ext in ('pdf','png'):
    fig.savefig(OUT / ('venn_diagram.'+ext),dpi=300,facecolor='white')
plt.close(fig)
