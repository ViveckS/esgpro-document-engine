#!/usr/bin/env python3
"""ESGPro declarative PDF renderer. All content, styles and geometry are external."""
from pathlib import Path
import argparse, json, hashlib, re, sys, html
from urllib.parse import urlparse
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor
from PIL import Image

ROOT = Path(__file__).resolve().parent

def load(path):
    return json.loads(Path(path).read_text())

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()

def content_digest(model):
    return digest({k: v for k, v in model.items() if k not in ('approval', 'publication_status')})

def numbers(t):
    return re.findall(r'\d[\d,.]*(?:\+|%|°C)?', re.sub('<[^>]+>', '', t))

def valid_url(u):
    p = urlparse(u)
    return p.scheme in ('https', 'http') and bool(p.hostname) and not any(c.isspace() for c in u)

def validate_content_schema(model, schema_path=None):
    """Validate content model against content.schema.json if available."""
    errors = []
    sp = Path(schema_path) if schema_path else (ROOT / 'content.schema.json')
    if not sp.is_file():
        return errors
    try:
        import jsonschema
        schema = load(sp)
        validator = jsonschema.Draft202012Validator(schema)
        for err in validator.iter_errors(model):
            loc = '.'.join(str(p) for p in err.path) if err.path else 'root'
            errors.append(f"Content schema violation at '{loc}': {err.message}")
    except ImportError:
        for req in ['schema_version', 'programme', 'publication_status', 'approval', 'blocks']:
            if req not in model:
                errors.append(f"Missing required top-level content property: {req}")
    return errors

def render_previews(pdf_path, dpi=150):
    """Render page previews as PNG images into <stem>_previews folder."""
    pdf_path = Path(pdf_path)
    outdir = pdf_path.parent / (pdf_path.stem + '_previews')
    outdir.mkdir(parents=True, exist_ok=True)
    try:
        import pymupdf
        doc = pymupdf.open(str(pdf_path))
        files = []
        for k, page in enumerate(doc, 1):
            out_f = outdir / ('page_%02d.png' % k)
            page.get_pixmap(dpi=dpi).save(str(out_f))
            files.append(str(out_f))
        return files
    except ImportError:
        pass
    import shutil, subprocess
    if shutil.which('pdftoppm'):
        prefix = str(outdir / 'page')
        subprocess.run(['pdftoppm', '-png', '-r', str(dpi), str(pdf_path), prefix], check=False)
        return [str(p) for p in sorted(outdir.glob('page-*.png'))]
    return []

def render(content, config, layout, out, final=False, validate_schema=False, previews=False, dpi=150):
    model, brand, master = load(content), load(config), load(layout)
    errors = []; warnings = []; metrics = []
    hashes = {'content': content_digest(model), 'configuration': digest(brand), 'layout': digest(master)}

    if validate_schema or final:
        schema_errs = validate_content_schema(model)
        if schema_errs:
            errors.extend(schema_errs)

    # Fail before drawing for missing resources; no font substitution.
    for alias, path in brand['fonts'].items():
        if not (ROOT / path).is_file():
            errors.append('Missing font: ' + path)
    for p in master['pages']:
        for e in p['elements']:
            if e['type'] == 'image' and not (ROOT / e['asset']).is_file():
                errors.append('Missing asset: ' + e['asset'])
    if not brand['logos'].get('primary') or not (ROOT / brand['logos']['primary']).is_file():
        errors.append('Required primary logo missing')
    for ident, b in model['blocks'].items():
        if numbers(b['rich_text']) != b['locked_numeric_tokens']:
            errors.append('Numeric change requires explicit content review: ' + ident)
        if '{{' in b['rich_text'] or not b['rich_text'].strip():
            errors.append('Unfilled content slot: ' + ident)
    if final:
        a = model['approval']
        if model.get('open_issue_ids'):
            errors.append('Open content issues: ' + ', '.join(model['open_issue_ids']))
        if not a.get('owner') or not a.get('date'):
            errors.append('Missing named owner approval/date')
        for key in hashes:
            if a.get('approved_' + key + '_sha256') != hashes[key]:
                errors.append('Missing or stale ' + key + ' approval hash')
        if not a.get('visual_qa_passed'):
            errors.append('Visual QA not signed off')
        if not a.get('links_verified'):
            errors.append('Destination links not verified')
        if any(c.get('status') not in ('verified', 'confirmed_by_owner') for c in model['claims']):
            errors.append('Unverified structured claims remain')
        if any(b.get('source_status') not in ('source_verified', 'owner_approved', 'editorial_nonfactual') for b in model['blocks'].values()):
            errors.append('Content blocks require reviewed provenance')
        if brand.get('approval_status') != 'approved_by_owner':
            errors.append('Brand configuration not owner approved')
    if errors:
        raise ValueError('\n'.join(errors))

    for alias, path in brand['fonts'].items():
        pdfmetrics.registerFont(TTFont(alias, str(ROOT / path)))
    pdfmetrics.registerFontFamily('Sans', normal='Sans', bold='Bold', italic='Italic', boldItalic='Italic')
    pdfmetrics.registerFontFamily('Editorial', normal='Editorial', bold='EditorialBold', italic='EditorialItalic', boldItalic='EditorialItalic')
    w, h = brand['page']['width_pt'], brand['page']['height_pt']
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + '.building.pdf')
    c = canvas.Canvas(str(tmp), pagesize=(w, h), initialFontName='Sans', initialFontSize=12)
    c.setTitle(model['programme']['display_name'] + (' — REVIEW PROOF' if not final else ''))
    c.setAuthor(brand['brand'])
    boxlist = []

    for pi, p in enumerate(master['pages'], 1):
        for e in p['elements']:
            typ = e['type']; x = e.get('x', 0); y = e.get('y', 0); col = brand['colors'].get(e.get('color'), '#1A1A1A')
            if typ == 'rect':
                c.setFillColor(HexColor(col))
                c.roundRect(x, h - y - e['height'], e['width'], e['height'], e['radius'], stroke=0, fill=1)
            elif typ == 'line':
                c.setStrokeColor(HexColor(col))
                c.setLineWidth(e['stroke'])
                c.line(x, h - y, x + e['width'], h - y)
            elif typ == 'circle':
                r = e['radius']
                cx = x + r
                cy = h - y - r
                c.saveState()
                c.setFillColor(HexColor(col))
                stroke = e.get('stroke', 0)
                if stroke:
                    stroke_col = brand['colors'].get(e.get('stroke_color'), col)
                    c.setStrokeColor(HexColor(stroke_col))
                    c.setLineWidth(stroke)
                    c.circle(cx, cy, r, stroke=1, fill=1 if e.get('fill', True) else 0)
                else:
                    c.circle(cx, cy, r, stroke=0, fill=1)
                c.restoreState()
            elif typ == 'badge':
                txt = e.get('text', '')
                if 'content_id' in e and e['content_id'] in model['blocks']:
                    txt = model['blocks'][e['content_id']]['rich_text']
                st = brand['styles'].get(e.get('style', 'style_01'), brand['styles']['style_01'])
                sz = st['size']
                rad = e.get('radius', e['height'] / 2)
                c.setFillColor(HexColor(col))
                c.roundRect(x, h - y - e['height'], e['width'], e['height'], rad, stroke=0, fill=1)
                text_col = brand['colors'].get(e.get('text_color', 'white'), '#FFFFFF')
                c.saveState()
                c.setFillColor(HexColor(text_col))
                c.setFont(st['font'], sz)
                plain = html.unescape(re.sub('<[^>]+>', '', txt))
                tw = pdfmetrics.stringWidth(plain, st['font'], sz)
                c.drawString(x + (e['width'] - tw) / 2, h - y - e['height'] + (e['height'] - sz) / 2 + 1, plain)
                c.restoreState()
            elif typ in ('text', 'label'):
                b = model['blocks'][e['content_id']]
                st = brand['styles'][e['style']]
                t = b['rich_text']
                sz = st['size']
                if typ == 'label':
                    plain = html.unescape(re.sub('<[^>]+>', '', t))
                    actual = pdfmetrics.stringWidth(plain, st['font'], sz) + max(0, len(plain) - 1) * st.get('tracking', 0)
                    if actual > e['width'] + 1:
                        errors.append(f"Page {pi}: label overflow {e['content_id']}")
                    c.saveState()
                    c.setFillColor(HexColor(col))
                    obj = c.beginText(x, h - y - sz)
                    obj.setFont(st['font'], sz)
                    obj.setCharSpace(st.get('tracking', 0))
                    obj.textLine(plain)
                    c.drawText(obj)
                    c.restoreState()
                    hh = e['max_height']
                else:
                    sty = ParagraphStyle('p', fontName=st['font'], fontSize=sz, leading=st['leading'], textColor=HexColor(col))
                    para = Paragraph(t, sty)
                    _, hh = para.wrap(e['width'], h)
                    if hh > e['max_height'] + 0.01:
                        errors.append(f"Page {pi}: text overflow {e['content_id']} ({hh:.1f} > {e['max_height']:.1f}pt); restructure or add a page")
                    para.drawOn(c, x, h - y - hh)
                if x < 0 or x + e['width'] > w + 1 or y < 0 or y + hh > h:
                    errors.append(f"Page {pi}: text outside page {e['content_id']}")
                boxlist.append({'page': pi, 'id': e['content_id'], 'box': [x, y, x + e['width'], y + hh]})
            elif typ == 'image':
                im = Image.open(ROOT / e['asset'])
                iw, ih = im.size
                scale = min(e['width'] / iw, e['height'] / ih)
                dw, dh = iw * scale, ih * scale
                ppi = 72 / scale
                metrics.append({'page': pi, 'asset': e['asset'], 'effective_ppi': round(ppi, 1)})
                if ppi < brand['images']['preferred_print_ppi'] and 'qr' not in e['asset']:
                    warnings.append(f"Page {pi}: {e['asset']} is {ppi:.0f}ppi; below preferred 300ppi print target")
                c.drawImage(str(ROOT / e['asset']), x + (e['width'] - dw) / 2, h - y - e['height'] + (e['height'] - dh) / 2, dw, dh, mask='auto')
            elif typ == 'wave':
                pts = e['points']
                c.setStrokeColor(HexColor(col))
                c.setLineWidth(e['stroke'])
                path = c.beginPath()
                path.moveTo(pts[0], h - pts[1])
                path.curveTo(pts[2], h - pts[3], pts[4], h - pts[5], pts[6], h - pts[7])
                c.drawPath(path)
            elif typ == 'link':
                if not valid_url(e['url']):
                    errors.append(f"Malformed URL: {e['url']}")
                else:
                    c.linkURL(e['url'], (x, h - y - e['height'], x + e['width'], h - y), relative=0)
            else:
                errors.append('Unsupported component primitive: ' + typ)
        if not final:
            c.setFillColor(HexColor(brand['colors']['gold']))
            c.rect(0, h - 20, w, 20, stroke=0, fill=1)
            c.setFont('Bold', 8)
            c.setFillColor(HexColor(brand['colors']['charcoal']))
            c.drawCentredString(w / 2, h - 13, 'REVIEW PROOF • CONTENT APPROVAL PENDING • NOT FOR CIRCULATION')
        c.showPage()
    c.save()
    if errors:
        tmp.unlink(missing_ok=True)
        raise ValueError('\n'.join(errors))
    tmp.replace(out)
    report = {
        'status': 'final_export' if final else 'review_only',
        'pages': len(master['pages']),
        'text_blocks': len(boxlist),
        'errors': errors,
        'warnings': sorted(set(warnings)),
        'image_metrics': metrics,
        'hashes': hashes,
        'checks': {
            'fonts': 'present; embedded without substitutions',
            'numeric_tokens': 'match frozen model values',
            'text_fit': 'all measured slots fit',
            'page_bounds': 'passed',
            'url_syntax': 'passed',
            'live_url_destinations': 'not checked by renderer',
            'visual_quality': 'requires human or rendered-image inspection',
            'regulatory_truth': 'not certified by renderer',
            'press_readiness': 'RGB office/digital print; not PDF/X',
            'schema_validation': 'validated' if validate_schema else 'runtime structure verified'
        }
    }
    if previews:
        report['previews'] = render_previews(out, dpi=dpi)
    out.with_suffix('.qa.json').write_text(json.dumps(report, indent=2))
    return report

if __name__ == '__main__':
    p = argparse.ArgumentParser(description='ESGPro declarative PDF renderer')
    p.add_argument('--content', default=str(ROOT / 'models/demo_content.json'))
    p.add_argument('--config', default=str(ROOT / 'brand_config.json'))
    p.add_argument('--layout', default=str(ROOT / 'layouts/demo.json'))
    p.add_argument('--output', default=str(ROOT / 'output/demo.pdf'))
    p.add_argument('--final', action='store_true')
    p.add_argument('--hashes', action='store_true')
    p.add_argument('--previews', action='store_true', help='generate PNG page previews')
    p.add_argument('--dpi', type=int, default=150, help='preview DPI (default: 150)')
    p.add_argument('--validate-schema', action='store_true', help='strictly validate content against JSON Schema')
    a = p.parse_args()
    try:
        if a.hashes:
            print(json.dumps({'content': content_digest(load(a.content)), 'configuration': digest(load(a.config)), 'layout': digest(load(a.layout))}, indent=2))
        else:
            print(json.dumps(render(a.content, a.config, a.layout, a.output, final=a.final, validate_schema=a.validate_schema, previews=a.previews, dpi=a.dpi), indent=2))
    except (ValueError, KeyError, FileNotFoundError) as e:
        print('EXPORT BLOCKED: ' + str(e), file=sys.stderr)
        sys.exit(2)
