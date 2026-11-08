#!/usr/bin/env python3
"""Build 00-main.tex and split it into the files uploaded to Computers in Biology and Medicine.

The compiled PDF holds every item; each starts with \\SubmissionPart{name} in 00-main.tex,
which writes its first page to 00-main.parts. This script recompiles, then writes clean
per-item files to ~/Documents/CBM submission (or --out DIR). Before the real submission,
set \\colorlet{editcolor}{black} in 00-main.tex so revision highlights disappear.

Needs pdflatex + bibtex, poppler (pdfinfo, pdftotext) and macOS textutil (for .docx).
Usage (repo root):  python3 tools/split_submission.py [--out DIR] [--no-build]
"""
import argparse, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEX = os.path.expanduser('~/Library/TinyTeX/bin/universal-darwin')
ENV = dict(os.environ, PATH=TEX + os.pathsep + os.environ['PATH'])
# part name in 00-main.parts -> upload file name; 'manuscript' is everything before the first part
NAMES = {'manuscript': '01_manuscript', 'supplementary': '02_supplementary_material',
         'cover_letter': '03_cover_letter', 'highlights': '04_highlights',
         'abstract': '05_abstract', 'ethics_statement': '06_ethics_statement'}
DOCX = {'highlights', 'abstract', 'ethics_statement'}  # portal asks for Word versions of these


def run(*cmd):
    subprocess.run(cmd, cwd=ROOT, env=ENV, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def build():
    for cmd in (['pdflatex', '-interaction=nonstopmode', '00-main'], ['bibtex', '00-main'],
                ['pdflatex', '-interaction=nonstopmode', '00-main'], ['pdflatex', '-interaction=nonstopmode', '00-main']):
        subprocess.run(cmd, cwd=ROOT, env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log = (ROOT / '00-main.log').read_text(errors='ignore')
    errs = [l for l in log.splitlines() if l.startswith('!')]
    undef = re.findall(r'(?:Reference|Citation) `[^\']+\' .*undefined', log)
    if errs or undef:
        sys.exit(f'LaTeX problems, fix before splitting:\n' + '\n'.join(errs + undef))


def parts(npages):
    starts = [l.split() for l in (ROOT / '00-main.parts').read_text().splitlines() if l.strip()]
    starts = [('manuscript', 1)] + [(n, int(p)) for n, p in starts]
    return [(n, a, (starts[i + 1][1] - 1) if i + 1 < len(starts) else npages) for i, (n, a) in enumerate(starts)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.expanduser('~/Documents/CBM submission'))
    ap.add_argument('--no-build', action='store_true')
    a = ap.parse_args()
    if not a.no_build:
        build()
    if re.search(r'^\\colorlet\{editcolor\}\{edityellow\}', (ROOT / '00-main.tex').read_text(), re.M):
        print('WARNING: review highlighting is ON (editcolor = edityellow). Set it to black before submitting.')
    pdf = ROOT / '00-main.pdf'
    npages = int(re.search(r'Pages:\s+(\d+)', subprocess.run(['pdfinfo', str(pdf)], capture_output=True, text=True).stdout).group(1))
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    for f in out.glob('0[1-7]_*'):  # only files this script owns; anything else (e.g. declaration .docx) is kept
        f.unlink()
    w, h = re.search(r'Page size:\s+([\d.]+) x ([\d.]+)', subprocess.run(['pdfinfo', str(pdf)], capture_output=True, text=True).stdout).groups()
    with tempfile.TemporaryDirectory() as tmp:
        for name, first, last in parts(npages):
            assert first <= last, f'empty part {name}'
            dest = out / f'{NAMES[name]}.pdf'
            # re-embed the pages with pdfTeX itself: keeps files small (poppler's pdfunite copies all fonts per page)
            body = ''.join(f'\\includegraphics[page={i}]{{{pdf}}}\\newpage\n' for i in range(first, last + 1))
            Path(tmp, 'part.tex').write_text(
                '\\documentclass{article}\\usepackage{graphicx}\\pagestyle{empty}\n'
                f'\\pdfpagewidth={w}bp \\pdfpageheight={h}bp \\hoffset=-1in \\voffset=-1in\n'
                '\\oddsidemargin=0pt \\topmargin=0pt \\headheight=0pt \\headsep=0pt \\parindent=0pt \\topskip=0pt\n'
                f'\\textwidth={w}bp \\textheight={h}bp\n\\begin{{document}}\n{body}\\end{{document}}\n')
            run_in = lambda: subprocess.run(['pdflatex', '-interaction=nonstopmode', 'part.tex'], cwd=tmp, env=ENV,
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            run_in()
            shutil.copy(Path(tmp, 'part.pdf'), dest)
            if name in DOCX:
                text = subprocess.run(['pdftotext', '-layout', str(dest), '-'], capture_output=True, text=True).stdout.strip()
                subprocess.run(['textutil', '-convert', 'docx', '-stdin', '-output', str(dest.with_suffix('.docx'))],
                               input=text, text=True, check=True)
            print(f'{dest.name:34s} pages {first}-{last}')
    shutil.copy(ROOT / 'graphical_abstract.pdf', out / '07_graphical_abstract.pdf')
    print('07_graphical_abstract.pdf          copied')
    print(f'\nWritten to: {out}\nStill needed from you: the Declaration of Interest .docx from Elsevier\'s Declaration tool.')


if __name__ == '__main__':
    main()
