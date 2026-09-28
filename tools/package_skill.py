#!/usr/bin/env python3
"""Bundle the esgpro-brochure skill (SKILL.md + engine) into one zip.

The same zip uploads as a Claude skill or a ChatGPT skill: both read SKILL.md
at the archive root folder and run the bundled Python.

    python tools/package_skill.py                   # public engine only
    python tools/package_skill.py --with-private    # also bundles private_assets/ (owner's own upload only)
"""
from pathlib import Path
import argparse, zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = 'esgpro-brochure'
PUBLIC = ['brochure.py', 'brochure_icons.py', 'requirements.txt', 'LICENSE', 'NOTICE.md',
          'themes', 'intake', 'fonts', 'facts/demo_facts.json', 'assets',
          'programmes/_template.json', 'programmes/demo.json']


def files(rel):
    p = ROOT / rel
    if p.is_dir():
        return sorted(f for f in p.rglob('*') if f.is_file() and '__pycache__' not in f.parts)
    return [p]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--with-private', action='store_true', help='include private_assets/ (never share this zip)')
    ap.add_argument('--output', default=str(ROOT / 'dist' / (NAME + '-skill.zip')))
    a = ap.parse_args()
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    items = PUBLIC + (['private_assets'] if a.with_private else [])
    n = 0
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        skill = ROOT / 'skill' / NAME
        for f in sorted(skill.rglob('*')):
            if f.is_file():
                z.write(f, NAME + '/' + f.relative_to(skill).as_posix()); n += 1
        for rel in items:
            for f in files(rel):
                z.write(f, NAME + '/' + f.relative_to(ROOT).as_posix()); n += 1
    print('%s: %d files%s' % (out, n, ' (includes PRIVATE assets; do not share)' if a.with_private else ''))


if __name__ == '__main__':
    main()
