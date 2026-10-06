#!/usr/bin/env python3
"""ESGPro brochure builder (v2).

Pages are composed from a library of infographic components instead of fixed
text slots, so every programme shares one visual system. A programme file holds
only programme-specific content. Shared facts, people, testimonials and images
come from single registries, so numbers and photos cannot drift between
brochures, and the build fails when they do.

    python brochure.py intake programmes/<id>.json      # questions still unanswered
    python brochure.py build  programmes/<id>.json --output output/<id>.pdf [--proof] [--previews]
    python brochure.py new    <id>                       # start a programme from the template
"""
from pathlib import Path
import argparse, copy, html, json, math, re, shutil, sys
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF
from PIL import Image, ImageOps
import brochure_icons

ROOT = Path(__file__).resolve().parent
TOKEN = re.compile(r'\{\{\s*([A-Za-z0-9_.\-]+)\s*\}\}')
UNFINISHED = re.compile(r'\b(TBC|TBD|TODO|XXX|lorem ipsum)\b|example\.com', re.I)


class BuildError(Exception):
    pass


def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def rel(base, p):
    p = Path(p)
    return p if p.is_absolute() else Path(base) / p


def plain(t):
    return html.unescape(re.sub(r'<[^>]+>', '', str(t)))


def fix_amp(t):
    return re.sub(r'&(?!#?\w+;)', '&amp;', str(t))


# ---------------------------------------------------------------- data context

class Context:
    """Resolved programme, shared facts, theme and image registry for one build."""

    def __init__(self, programme_path, proof=False, allow_placeholders=False):
        self.path = Path(programme_path).resolve()
        self.prog = load(self.path)
        self.proof, self.allow_placeholders = proof, allow_placeholders
        self.errors, self.warnings = [], []
        self.theme = load(rel(ROOT, self.prog.get('theme', 'themes/esgpro.json')))
        self.facts = load(rel(ROOT, self.prog.get('facts', 'facts/esgpro_common.json')))
        self.assets = Assets(rel(ROOT, self.prog.get('assets', 'private_assets/manifest.json')), self)
        self.tokens = self._tokens()
        self.used_tokens = set()

    def _tokens(self):
        t = {}

        def put(prefix, obj):
            for k, v in obj.items():
                key = prefix + k
                if isinstance(v, dict):
                    if 'value' in v:
                        t[key] = v['value']
                    put(key + '.', v)
                elif isinstance(v, (str, int, float)):
                    t[key] = str(v)
        put('fact.', self.facts.get('facts', {}))
        put('contact.', self.facts.get('contact', {}))
        put('org.', self.facts.get('organisation', {}))
        put('programme.', {k: v for k, v in self.prog.get('programme', {}).items() if not isinstance(v, list)})
        put('var.', self.prog.get('vars', {}))
        return t

    def resolve(self, obj, where='programme'):
        """Deep-resolve {{tokens}}; unresolved tokens are errors and stay visible."""
        if isinstance(obj, str):
            def sub(m):
                key = m.group(1)
                if key in self.tokens:
                    self.used_tokens.add(key)
                    return self.tokens[key]
                self.errors.append('Unresolved token {{%s}} in %s' % (key, where))
                return '[[' + key + ']]'
            return TOKEN.sub(sub, obj)
        if isinstance(obj, list):
            return [self.resolve(v, where) for v in obj]
        if isinstance(obj, dict):
            return {k: self.resolve(v, where) for k, v in obj.items()}
        return obj

    def person(self, pid):
        p = self.facts.get('people', {}).get(pid)
        if p is None:
            raise BuildError('Unknown person "%s" (define it in the facts file under people)' % pid)
        return self.resolve(p, 'people.' + pid)

    def testimonial(self, tid):
        t = self.facts.get('testimonials', {}).get(tid)
        if t is None:
            raise BuildError('Unknown testimonial "%s" (define it in the facts file under testimonials)' % tid)
        return self.resolve(t, 'testimonials.' + tid)


def dhash(path, n=8):
    im = Image.open(path).convert('L').resize((n + 1, n), Image.LANCZOS)
    px = list(im.getdata())
    bits = 0
    for r in range(n):
        for c in range(n):
            bits = (bits << 1) | (px[r * (n + 1) + c] > px[r * (n + 1) + c + 1])
    return bits


class Assets:
    """Image registry. Enforces presence, per-role reuse limits and near-duplicate photos."""

    def __init__(self, manifest_path, ctx):
        self.ctx, self.uses, self.images = ctx, {}, {}
        self.manifest_path = manifest_path
        if manifest_path.is_file():
            m = load(manifest_path)
            self.base = rel(manifest_path.parent, m.get('base_dir', '.'))
            self.images = m.get('images', {})
        else:
            self.base = manifest_path.parent
            ctx.warnings.append('No image manifest at %s; copy private_assets/manifest.example.json' % manifest_path)

    def path(self, aid, purpose, record=True):
        if record:
            self.uses.setdefault(aid, []).append(purpose)
        spec = self.images.get(aid)
        why = None
        if not spec:
            why = 'not registered in the image manifest'
        else:
            p = rel(self.base, spec['file'])
            if p.is_file():
                return p
            why = 'file not found: %s' % p
        if record:
            msg = 'Missing image "%s" for %s (%s)' % (aid, purpose, why)
            if self.ctx.allow_placeholders:
                self.ctx.warnings.append(msg + '; visible placeholder drawn')
            else:
                self.ctx.errors.append(msg)
        return None

    def spec(self, aid):
        return self.images.get(aid, {})

    def finish(self):
        rules = self.ctx.theme['image_rules']
        for aid, purposes in self.uses.items():
            spec = self.images.get(aid, {})
            role = spec.get('role', 'photo')
            limit = spec.get('max_uses', rules['default_max_uses'].get(role, 1))
            if limit is not None and len(purposes) > limit:
                self.ctx.errors.append('Image repetition: "%s" (%s) used %d times, limit %d: %s'
                                       % (aid, role, len(purposes), limit, '; '.join(purposes)))
        hashes = []
        for aid in self.uses:
            spec = self.images.get(aid, {})
            if spec.get('role', 'photo') in ('logo', 'partner_logo'):
                continue
            p = self.path(aid, '', record=False)
            if p:
                hashes.append((aid, dhash(p)))
        for i in range(len(hashes)):
            for j in range(i + 1, len(hashes)):
                d = bin(hashes[i][1] ^ hashes[j][1]).count('1')
                if d <= rules['near_duplicate_hamming']:
                    self.ctx.errors.append('Same photo under two names: "%s" and "%s" (hash distance %d)'
                                           % (hashes[i][0], hashes[j][0], d))

    def report(self):
        return {aid: {'uses': len(p), 'purposes': p, 'role': self.images.get(aid, {}).get('role')}
                for aid, p in self.uses.items()}


# ---------------------------------------------------------------- drawing pen

class Pen:
    """Top-down drawing helpers. In dry mode nothing is drawn; only sizes are computed."""

    def __init__(self, c, ctx, styles, page_no):
        self.c, self.ctx, self.th, self.styles = c, ctx, ctx.theme, styles
        self.H = ctx.theme['page']['height']
        self.W = ctx.theme['page']['width']
        self.dry = False
        self.page_no = page_no

    def hexc(self, name):
        return self.th['colors'].get(name, name)

    def col(self, name):
        return HexColor(self.hexc(name))

    def style(self, name, color=None, align=None, size=None, leading=None):
        s = self.styles[name]
        font = self.ctx.font_names[s['font']]
        return ParagraphStyle(name, fontName=font, bulletFontName=font, fontSize=size or s['size'], leading=leading or s['leading'],
                              textColor=self.col(color or s['color']),
                              alignment={'left': 0, 'center': 1, 'right': 2}[align or s.get('align', 'left')])

    def _glyphs(self, text, font_alias):
        face = pdfmetrics.getFont(self.ctx.font_names[font_alias]).face
        missing = sorted({ch for ch in plain(text) if ord(ch) > 126 and ord(ch) not in face.charToGlyph})
        if missing:
            self.ctx.errors.append('Page %d: font %s has no glyph for %s' % (self.page_no, font_alias, ' '.join(missing)))

    def _para(self, text, style, w, **kw):
        st = self.style(style, **kw)
        self._glyphs(text, self.styles[style]['font'])
        p = Paragraph(fix_amp(text).replace('\n', '<br/>'), st)
        _, h = p.wrap(w, 10000)
        return p, h

    def ph(self, text, style, w, **kw):
        if text is None or text == '':
            return 0
        return self._para(text, style, w, **kw)[1]

    def lines(self, text, style, w, **kw):
        if not text:
            return 0
        p, h = self._para(text, style, w, **kw)
        return max(1, round(h / (kw.get('leading') or self.styles[style]['leading'])))

    def para(self, text, style, x, y, w, **kw):
        if text is None or text == '':
            return 0
        p, h = self._para(text, style, w, **kw)
        if not self.dry:
            p.drawOn(self.c, x, self.H - y - h)
        return h

    def label(self, text, x, y, style='kicker', color=None, align='left', max_w=None):
        s = self.styles[style]
        font = self.ctx.font_names[s['font']]
        t = plain(text).upper() if s.get('tracking', 0) >= 1 else plain(text)
        tr = s.get('tracking', 0)
        w = pdfmetrics.stringWidth(t, font, s['size']) + max(0, len(t) - 1) * tr
        if max_w is not None and w > max_w + 0.5:
            self.ctx.errors.append('Page %d: label "%s" is %.0fpt wide, slot is %.0fpt' % (self.page_no, t, w, max_w))
        if not self.dry:
            self._glyphs(t, s['font'])
            x0 = x - w if align == 'right' else (x - w / 2 if align == 'center' else x)
            c = self.c
            c.saveState(); c.setFillColor(self.col(color or s['color']))
            o = c.beginText(x0, self.H - y - s['size'] * 0.82); o.setFont(font, s['size']); o.setCharSpace(tr)
            o.textLine(t); c.drawText(o); c.restoreState()
        return s['leading'], w

    def rect(self, x, y, w, h, fill=None, radius=0, stroke=None, lw=0.8, alpha=None):
        if self.dry:
            return
        c = self.c
        c.saveState()
        if fill:
            c.setFillColor(self.col(fill))
            if alpha is not None:
                c.setFillAlpha(alpha)
        if stroke:
            c.setStrokeColor(self.col(stroke)); c.setLineWidth(lw)
        if radius:
            c.roundRect(x, self.H - y - h, w, h, radius, stroke=1 if stroke else 0, fill=1 if fill else 0)
        else:
            c.rect(x, self.H - y - h, w, h, stroke=1 if stroke else 0, fill=1 if fill else 0)
        c.restoreState()

    def top_rounded(self, x, y, w, h, fill, radius=8):
        """Band with rounded top corners and square bottom corners."""
        self.rect(x, y, w, h, fill, radius)
        self.rect(x, y + h - radius, w, radius, fill)

    def line(self, x1, y1, x2, y2, color='rule', lw=0.8, dash=None):
        if self.dry:
            return
        c = self.c
        c.saveState(); c.setStrokeColor(self.col(color)); c.setLineWidth(lw); c.setLineCap(1)
        if dash:
            c.setDash(*dash)
        c.line(x1, self.H - y1, x2, self.H - y2); c.restoreState()

    def circle(self, cx, cy, r, fill=None, stroke=None, lw=1):
        if self.dry:
            return
        c = self.c
        c.saveState()
        if fill:
            c.setFillColor(self.col(fill))
        if stroke:
            c.setStrokeColor(self.col(stroke)); c.setLineWidth(lw)
        c.circle(cx, self.H - cy, r, stroke=1 if stroke else 0, fill=1 if fill else 0)
        c.restoreState()

    def poly(self, pts, fill, stroke=None):
        if self.dry:
            return
        c = self.c
        c.saveState(); c.setFillColor(self.col(fill))
        p = c.beginPath(); p.moveTo(pts[0][0], self.H - pts[0][1])
        for x, y in pts[1:]:
            p.lineTo(x, self.H - y)
        p.close()
        if stroke:
            c.setStrokeColor(self.col(stroke))
        c.drawPath(p, stroke=1 if stroke else 0, fill=1); c.restoreState()

    def icon(self, name, cx, cy, size, color='forest', badge=None, badge_r=None):
        if name not in brochure_icons.ICONS:
            self.ctx.errors.append('Page %d: unknown icon "%s"' % (self.page_no, name))
            return
        if self.dry:
            return
        if badge:
            self.circle(cx, cy, badge_r or size * 0.85, fill=badge)
        brochure_icons.draw(self.c, name, cx, self.H - cy, size, self.col(color))

    def check_badge(self, cx, cy, r=7, fill='lime', color='white'):
        if self.dry:
            return
        self.circle(cx, cy, r, fill=fill)
        brochure_icons.draw(self.c, 'check', cx, self.H - cy, r * 1.35, self.col(color), width=2.4)

    def number_badge(self, cx, cy, r, text, fill='forest', color='white', style='h4'):
        if self.dry:
            return
        self.circle(cx, cy, r, fill=fill)
        s = self.styles[style]
        font = self.ctx.font_names[s['font']]
        c = self.c
        c.saveState(); c.setFillColor(self.col(color)); c.setFont(font, s['size'])
        c.drawCentredString(cx, self.H - cy - s['size'] * 0.35, plain(text)); c.restoreState()

    def link(self, url, x, y, w, h):
        if self.dry:
            return
        self.c.linkURL(url, (x, self.H - y - h, x + w, self.H - y), relative=0)

    def qr(self, url, x, y, size):
        if self.dry:
            return
        wdg = QrCodeWidget(url, barLevel='M')
        b = wdg.getBounds()
        bw, bh = b[2] - b[0], b[3] - b[1]
        d = Drawing(size, size, transform=[size / bw, 0, 0, size / bh, 0, 0])
        d.add(wdg)
        renderPDF.draw(d, self.c, x, self.H - y - size)
        self.link(url, x, y, size, size)

    def _crop(self, path, w, h, focus_y):
        im = ImageOps.exif_transpose(Image.open(path))
        if im.mode not in ('RGB', 'RGBA'):
            im = im.convert('RGBA')
        iw, ih = im.size
        target = w / float(h)
        if iw / float(ih) > target:
            nw = int(ih * target); x0 = (iw - nw) // 2; box = (x0, 0, x0 + nw, ih)
        else:
            nh = int(iw / target); y0 = int((ih - nh) * focus_y); box = (0, y0, iw, y0 + nh)
        return im.crop(box)

    def photo(self, aid, x, y, w, h, purpose, shape='rect', radius=0, ring=None):
        """Cover-fit photo clipped to rect/rounded/circle. Missing photos draw a loud placeholder."""
        if self.dry:
            return
        path = self.ctx.assets.path(aid, 'page %d %s' % (self.page_no, purpose))
        spec = self.ctx.assets.spec(aid)
        c, by = self.c, self.H - y - h
        c.saveState()
        p = c.beginPath()
        if shape == 'circle':
            p.circle(x + w / 2, by + h / 2, min(w, h) / 2)
        elif radius:
            p.roundRect(x, by, w, h, radius)
        else:
            p.rect(x, by, w, h)
        c.clipPath(p, stroke=0, fill=0)
        if path:
            im = self._crop(path, w, h, spec.get('focus_y', 0.3))
            ppi = im.size[0] / (w / 72.0)
            if ppi < self.th['image_rules']['min_effective_ppi']:
                self.ctx.warnings.append('Page %d: image "%s" prints at %.0f ppi' % (self.page_no, aid, ppi))
            if im.mode == 'RGBA':
                bg = Image.new('RGBA', im.size, self.hexc(spec.get('matte', 'mist')))
                bg.alpha_composite(im); im = bg.convert('RGB')
            c.drawImage(ImageReader(im), x, by, w, h)
        else:
            c.setFillColor(self.col('gold_tint')); c.rect(x, by, w, h, stroke=0, fill=1)
            brochure_icons.draw(c, 'people', x + w / 2, by + h / 2 + 6, min(w, h) * 0.4, self.col('gold'))
            c.setFillColor(self.col('ink')); c.setFont(self.ctx.font_names['SansBold'], 6.5)
            c.drawCentredString(x + w / 2, by + h * 0.18, 'PHOTO NEEDED: ' + aid[:24])
        c.restoreState()
        if ring:
            c.saveState(); c.setStrokeColor(self.col(ring)); c.setLineWidth(2.2)
            if shape == 'circle':
                c.circle(x + w / 2, by + h / 2, min(w, h) / 2)
            else:
                c.roundRect(x, by, w, h, radius or 0.1)
            c.restoreState()

    def initials(self, name, cx, cy, r, fill='forest_2'):
        if self.dry:
            return
        self.circle(cx, cy, r, fill=fill)
        parts = [w for w in re.sub(r'[^A-Za-z ]', ' ', name).split() if w.upper() not in ('CA', 'DR', 'MR', 'MS')]
        ini = ''.join(w[0] for w in parts[:2]).upper() or '?'
        c = self.c
        c.saveState(); c.setFillColor(self.col('white')); c.setFont(self.ctx.font_names['SerifBold'], r * 0.8)
        c.drawCentredString(cx, self.H - cy - r * 0.28, ini); c.restoreState()

    def logo(self, aid, x, y, w, h, purpose, align='left'):
        path = self.ctx.assets.path(aid, 'page %d %s' % (self.page_no, purpose)) if not self.dry else None
        if self.dry:
            return
        if not path:
            self.rect(x, y, w, h, 'gold_tint', 4)
            self.para('<b>LOGO NEEDED</b>', 'caption', x + 6, y + h / 2 - 6, w - 12)
            return
        iw, ih = Image.open(path).size
        s = min(w / iw, h / ih)
        dw, dh = iw * s, ih * s
        dx = x if align == 'left' else (x + w - dw if align == 'right' else x + (w - dw) / 2)
        self.c.drawImage(str(path), dx, self.H - y - h + (h - dh) / 2, dw, dh, mask='auto')

    def ramp(self, a, b, n):
        ha, hb = self.hexc(a).lstrip('#'), self.hexc(b).lstrip('#')
        ca = [int(ha[i:i + 2], 16) for i in (0, 2, 4)]
        cb = [int(hb[i:i + 2], 16) for i in (0, 2, 4)]
        out = []
        for k in range(n):
            t = k / float(max(1, n - 1))
            out.append('#%02X%02X%02X' % tuple(int(ca[i] + (cb[i] - ca[i]) * t) for i in range(3)))
        return out

    def bullets(self, items, style, x, y, w, marker='dot', color='lime', gap=5, text_color=None):
        yy = y
        s = self.styles[style]
        for k, it in enumerate(items):
            h = self.para(it, style, x + 14, yy, w - 14, color=text_color)
            my = yy + s['leading'] * 0.5
            if marker == 'check':
                self.check_badge(x + 5, my, 5)
            elif marker == 'dash':
                self.line(x + 1, my, x + 8, my, color, 1.4)
            else:
                self.circle(x + 4, my, 2.3, fill=color)
            yy += h + (gap if k < len(items) - 1 else 0)
        return yy - y


# ---------------------------------------------------------------- blocks
# Each block function lays out AND draws; with pen.dry it only measures.
# Signature: fn(pen, block, x, y, w) -> height

def b_paragraph(p, b, x, y, w):
    return p.para(b['text'], b.get('style', 'body'), x, y, w, color=b.get('color'))


def b_label(p, b, x, y, w):
    h, tw = p.label(b['text'], x, y, b.get('style', 'kicker'), max_w=w)
    if b.get('rule', True):
        p.line(x + tw + 10, y + 5, x + w, y + 5, 'rule', 0.6)
    return h


def b_spacer(p, b, x, y, w):
    return b.get('height', 8)


def b_divider(p, b, x, y, w):
    p.line(x, y + 4, x + w, y + 4, b.get('color', 'rule'), b.get('weight', 0.6))
    return 8


def b_kpi_row(p, b, x, y, w):
    items = b['items']; n = len(items); g = 10
    tw = (w - g * (n - 1)) / n
    dark = b.get('variant') == 'dark'
    pad, inner = 14, tw - 34
    vst = b.get('value_style', 'kpi')
    ih = 26 if any(it.get('icon') for it in items) else 0
    vh = max(p.ph(it['value'], vst, inner) for it in items)
    lh = max(p.ph(it['label'], 'kpi_label', inner) for it in items)
    nh = max(p.ph(it.get('note'), 'caption', inner) for it in items)
    h = pad + ih + vh + 4 + lh + (4 + nh if nh else 0) + pad
    for k, it in enumerate(items):
        tx = x + k * (tw + g)
        p.rect(tx, y, tw, h, 'forest' if dark else b.get('fill', 'white'), 6)
        p.rect(tx + pad, y + pad, 3, h - 2 * pad, 'lime')
        yy = y + pad
        if ih:
            p.icon(it.get('icon', 'check'), tx + pad + 23, yy + 9, 17, 'lime' if dark else 'forest')
            yy += ih
        p.para(it['value'], vst, tx + pad + 14, yy, inner, color='white' if dark else None)
        yy += vh + 4
        p.para(it['label'], 'kpi_label', tx + pad + 14, yy, inner, color='on_dark_muted' if dark else None)
        if it.get('note'):
            p.para(it['note'], 'caption', tx + pad + 14, yy + lh + 4, inner, color='on_dark_label' if dark else None)
    return h


def b_stat_band(p, b, x, y, w):
    pad = 20
    vw = b.get('value_width', 190)
    tw = w - 2 * pad - vw - 20
    vh = p.ph(b['value'], 'stat_xl', vw)
    th = p.ph(b.get('title'), 'h3', tw)
    bh = p.ph(b.get('text'), 'small', tw)
    h = pad + max(vh, th + (6 if th else 0) + bh) + pad
    dark = b.get('variant', 'soft') == 'dark'
    p.rect(x, y, w, h, 'forest' if dark else 'mist', 8)
    p.para(b['value'], 'stat_xl', x + pad, y + (h - vh) / 2, vw, color='lime' if dark else None)
    p.line(x + pad + vw + 8, y + pad, x + pad + vw + 8, y + h - pad, 'lime', 2)
    ty = y + (h - (th + (6 if th else 0) + bh)) / 2
    p.para(b.get('title'), 'h3', x + pad + vw + 20, ty, tw, color='white' if dark else None)
    p.para(b.get('text'), 'small', x + pad + vw + 20, ty + th + (6 if th else 0), tw,
           color='on_dark_muted' if dark else None)
    return h


def b_process_flow(p, b, x, y, w):
    steps = b['steps']; n = len(steps); ah = 11; gap = 3
    sw = (w + gap) / n
    shades = p.ramp(b.get('from', 'forest_3'), b.get('to', 'forest_deep'), n)
    tw = sw - 2 * ah - 10
    titles = ["<font color='%s'>%02d</font>&nbsp;&nbsp;%s" % (p.hexc('on_dark_label'), k + 1, s['title'])
              for k, s in enumerate(steps)]
    th_ = max(p.ph(t, 'chev', tw) for t in titles)
    bh = max(40, th_ + 18)
    txt = max(p.ph(s.get('text'), 'small', sw - 14) for s in steps)
    out = max(p.ph(s.get('output'), 'caption', sw - 26) for s in steps)
    for k, s in enumerate(steps):
        sx = x + k * sw
        ex = sx + sw - gap
        pts = [(sx, y), (ex - ah, y), (ex, y + bh / 2), (ex - ah, y + bh), (sx, y + bh)]
        if k == n - 1:
            pts = [(sx, y), (ex, y), (ex, y + bh), (sx, y + bh)]
        if k > 0:
            pts.append((sx + ah, y + bh / 2))
        p.poly(pts, shades[k])
        lx = sx + (ah + 6 if k > 0 else 12)
        p.para(titles[k], 'chev', lx, y + (bh - p.ph(titles[k], 'chev', tw)) / 2, tw)
        p.para(s.get('text'), 'small', sx + 2, y + bh + 10, sw - 14)
        if s.get('output'):
            oy = y + bh + 10 + txt + 8
            p.rect(sx + 2, oy - 2, sw - 12, out + 10, 'mist', 4)
            p.icon('document', sx + 12, oy + 5, 10, 'forest')
            p.para(s['output'], 'caption', sx + 22, oy + 3, sw - 36, color='forest')
    return bh + (10 + txt if txt else 0) + (18 + out if out else 0)


def b_week_plan(p, b, x, y, w):
    """Gantt-style plan: rows are workstreams, columns are weeks/phases."""
    cols, rows = b['columns'], b['rows']
    lw = b.get('label_width', 150)
    cw = (w - lw) / len(cols)
    hh = 26
    p.rect(x, y, w, hh, 'forest', 6)
    p.para('<b>%s</b>' % b.get('corner', ''), 'caption', x + 10, y + 8, lw - 14, color='on_dark_label')
    for k, cname in enumerate(cols):
        p.para('<b>%s</b>' % cname, 'caption', x + lw + k * cw, y + 8, cw, color='white', align='center')
    yy = y + hh + 6
    for r, row in enumerate(rows):
        lh = p.ph(row['label'], 'h4', lw - 12)
        bars = row['bars']
        texts = [p.ph(bar.get('text'), 'caption', (bar['end'] - bar['start'] + 1) * cw - 14) for bar in bars]
        rh = max(lh, 20 + max(texts or [0])) + 12
        if r % 2 == 0:
            p.rect(x, yy - 3, w, rh, 'white', 4)
        p.para(row['label'], 'h4', x + 10, yy + 3, lw - 16)
        for bar, t in zip(bars, texts):
            bx = x + lw + (bar['start'] - 1) * cw + 4
            bw = (bar['end'] - bar['start'] + 1) * cw - 8
            p.rect(bx, yy + 2, bw, 16, bar.get('color', 'lime' if bar.get('milestone') else 'forest_2'), 8)
            p.para('<b>%s</b>' % bar['title'], 'caption', bx + 8, yy + 5.5, bw - 16,
                   color='forest_deep' if bar.get('milestone') else 'white')
            p.para(bar.get('text'), 'caption', bx + 4, yy + 21, bw - 8)
        yy += rh + 4
    for k in range(1, len(cols)):
        p.line(x + lw + k * cw, y + hh + 2, x + lw + k * cw, yy - 4, 'rule', 0.5, dash=(2, 2))
    return yy - y


def b_timeline(p, b, x, y, w):
    items = b['items']
    lw = b.get('tag_width', 78)
    node_x = x + lw + 10
    cx = node_x + 18
    cw = w - (cx - x)
    yy = y
    nodes = []
    for k, it in enumerate(items):
        tag_h = p.ph(it['tag'], 'h4', lw)
        meta_h = p.ph(it.get('meta'), 'caption', lw)
        title_h = p.ph(it['title'], 'h3', cw)
        if it.get('points'):
            ncol = it.get('columns', b.get('columns', 1))
            chunks = [it['points'][i::ncol] for i in range(ncol)] if ncol > 1 else [it['points']]
            colw = (cw - 14 * (ncol - 1)) / ncol
            pts_h = max(_bul_h(p, ch, colw) for ch in chunks)
        else:
            pts_h = p.ph(it.get('text'), 'small', cw)
        out_h = p.ph(it.get('output'), 'small', cw - 26)
        ih = max(tag_h + meta_h + 4, title_h + 5 + pts_h + (10 + out_h + 8 if out_h else 0))
        p.para(it['tag'], 'h4', x, yy, lw, align='right')
        p.para(it.get('meta'), 'caption', x, yy + tag_h + 2, lw, align='right')
        nodes.append(yy + 7)
        p.para(it['title'], 'h3', cx, yy, cw)
        ty = yy + title_h + 5
        if it.get('points'):
            for i, ch in enumerate(chunks):
                p.bullets(ch, 'small', cx + i * (colw + 14), ty, colw)
        else:
            p.para(it.get('text'), 'small', cx, ty, cw)
        if out_h:
            oy = ty + pts_h + 10
            p.rect(cx, oy - 4, cw, out_h + 10, 'mist', 4)
            p.icon('document', cx + 11, oy + 5, 11, 'forest')
            p.para(it['output'], 'small', cx + 24, oy + 1, cw - 30)
        yy += ih + (b.get('gap', 16) if k < len(items) - 1 else 0)
    if nodes:
        p.line(node_x, nodes[0], node_x, nodes[-1], 'mist_2', 3)
        for k, ny in enumerate(nodes):
            p.circle(node_x, ny, 7.5, fill='lime' if items[k].get('highlight') else 'forest')
            p.circle(node_x, ny, 2.8, fill='white')
    return yy - y


def _bul_h(p, items, w, style='small', gap=5):
    return sum(p.ph(i, style, w - 14) for i in items) + gap * max(0, len(items) - 1)


def b_module_grid(p, b, x, y, w):
    mods = b['modules']; cols = b.get('columns', 2); g = 12
    cw = (w - g * (cols - 1)) / cols
    yy = y
    for r in range(0, len(mods), cols):
        row = mods[r:r + cols]
        heads = [p.ph(m['title'], 'h3', cw - 60, color='white') for m in row]
        hh = max(heads) + 22
        bodies = [_bul_h(p, m.get('points', []), cw - 28) if m.get('points') else p.ph(m.get('text'), 'small', cw - 28)
                  for m in row]
        foots = [p.ph(m.get('output'), 'caption', cw - 48) for m in row]
        fh = max(foots)
        rh = hh + 12 + max(bodies) + (16 + fh if fh else 0) + 14
        for k, m in enumerate(row):
            mx = x + k * (cw + g)
            p.rect(mx, yy, cw, rh, 'white', 8)
            p.top_rounded(mx, yy, cw, hh, 'forest', 8)
            p.number_badge(mx + 24, yy + hh / 2, 13, m.get('code', str(r + k + 1)), fill='lime', color='forest_deep')
            p.para(m['title'], 'h3', mx + 46, yy + (hh - heads[k]) / 2, cw - 60, color='white')
            if m.get('meta'):
                p.label(m['meta'], mx + cw - 12, yy - 13 + hh, 'meta', color='on_dark_label', align='right')
            by = yy + hh + 12
            if m.get('points'):
                p.bullets(m['points'], 'small', mx + 14, by, cw - 28)
            else:
                p.para(m.get('text'), 'small', mx + 14, by, cw - 28)
            if m.get('output'):
                fy = yy + rh - 14 - fh
                p.line(mx + 14, fy - 8, mx + cw - 14, fy - 8, 'rule', 0.5)
                p.icon('document', mx + 21, fy + 5, 11, 'lime_dark')
                p.para('<b>Builds:</b> ' + m['output'], 'caption', mx + 34, fy, cw - 48, color='forest')
        yy += rh + g
    return yy - y - g


def b_icon_grid(p, b, x, y, w):
    items = b['items']; cols = b.get('columns', 3); g = b.get('gap', 14)
    cw = (w - g * (cols - 1)) / cols
    boxed = b.get('boxed', True)
    side = b.get('layout', 'side' if cols <= 2 else 'top') == 'side'
    pad = 14 if boxed else 0
    yy = y
    for r in range(0, len(items), cols):
        row = items[r:r + cols]
        if side:
            tw = cw - 2 * pad - 46
            hs = [p.ph(it['title'], 'h4', tw) + 4 + p.ph(it.get('text'), 'small', tw) for it in row]
            rh = max(max(hs), 34) + 2 * pad
        else:
            tw = cw - 2 * pad
            hs = [40 + p.ph(it['title'], 'h4', tw) + 4 + p.ph(it.get('text'), 'small', tw) for it in row]
            rh = max(hs) + 2 * pad
        for k, it in enumerate(row):
            ix = x + k * (cw + g)
            if boxed:
                p.rect(ix, yy, cw, rh, b.get('fill', 'white'), 8)
            if side:
                p.icon(it['icon'], ix + pad + 17, yy + pad + 17, 18, 'forest', badge='mist', badge_r=17)
                th = p.para(it['title'], 'h4', ix + pad + 46, yy + pad, tw)
                p.para(it.get('text'), 'small', ix + pad + 46, yy + pad + th + 4, tw)
            else:
                p.icon(it['icon'], ix + pad + 17, yy + pad + 17, 18, 'forest', badge='mist', badge_r=17)
                th = p.para(it['title'], 'h4', ix + pad, yy + pad + 40, tw)
                p.para(it.get('text'), 'small', ix + pad, yy + pad + 44 + th, tw)
        yy += rh + g
    return yy - y - g


def b_comparison(p, b, x, y, w):
    cols, rows = b['columns'], b['rows']
    fw = w * b.get('first_col', 0.36)
    cw = (w - fw) / (len(cols) - 1)
    hl = b.get('highlight')
    hh = max(p.ph('<b>%s</b>' % c, 'small', cw - 12) for c in cols[1:]) + 18
    xs = [x] + [x + fw + i * cw for i in range(len(cols) - 1)]
    ws = [fw] + [cw] * (len(cols) - 1)
    p.top_rounded(x, y, w, hh, 'forest', 6)
    p.para('<b>%s</b>' % cols[0], 'small', x + 12, y + 9, fw - 20, color='on_dark_label')
    for i in range(1, len(cols)):
        if i == hl:
            p.top_rounded(xs[i], y - 6, ws[i], hh + 6, 'lime', 6)
        p.para('<b>%s</b>' % cols[i], 'small', xs[i] + 6, y + 9, ws[i] - 12,
               color='forest_deep' if i == hl else 'white', align='center')
    yy = y + hh
    for r, row in enumerate(rows):
        vals = row['values']
        lh = p.ph(row['label'], 'small', fw - 24)
        vh = max([p.ph(v, 'small', ws[i + 1] - 16) if isinstance(v, str) else 14 for i, v in enumerate(vals)])
        rh = max(lh, vh) + 14
        p.rect(x, yy, w, rh, 'white' if r % 2 == 0 else 'mist')
        if hl:
            p.rect(xs[hl], yy, ws[hl], rh, 'gold_tint' if r % 2 else '#F6F3E6')
        p.para(row['label'], 'small', x + 12, yy + (rh - lh) / 2, fw - 24)
        for i, v in enumerate(vals):
            cx0 = xs[i + 1]
            if v is True:
                p.check_badge(cx0 + ws[i + 1] / 2, yy + rh / 2, 7)
            elif v is False or v is None:
                p.line(cx0 + ws[i + 1] / 2 - 5, yy + rh / 2, cx0 + ws[i + 1] / 2 + 5, yy + rh / 2, 'muted', 1.2)
            else:
                vh_ = p.ph(v, 'small', ws[i + 1] - 16)
                p.para(v, 'small', cx0 + 8, yy + (rh - vh_) / 2, ws[i + 1] - 16, align='center')
        yy += rh
    p.line(x, yy, x + w, yy, 'forest', 1.2)
    return yy - y + 2


def b_evidence_table(p, b, x, y, w):
    """Numbered rows: item + detail on the left, why-it-matters callout on the right."""
    rows = b['rows']
    lw = w * b.get('split', 0.6)
    rw = w - lw
    hh = 26
    p.top_rounded(x, y, w, hh, 'forest', 6)
    p.label(b.get('left_header', ''), x + 44, y + 9, 'meta', color='on_dark_label')
    p.label(b.get('right_header', ''), x + lw + 14, y + 9, 'meta', color='on_dark_label')
    yy = y + hh
    for r, row in enumerate(rows):
        th = p.ph(row['title'], 'h4', lw - 60)
        dh = p.ph(row.get('text'), 'small', lw - 60)
        wh = p.ph(row.get('why'), 'small', rw - 42)
        rh = max(th + 3 + dh, wh) + 20
        p.rect(x, yy, w, rh, 'white' if r % 2 == 0 else 'mist')
        p.number_badge(x + 22, yy + 10 + 9, 10, '%d' % (r + 1), fill='forest', style='caption')
        p.para(row['title'], 'h4', x + 44, yy + 10, lw - 60)
        p.para(row.get('text'), 'small', x + 44, yy + 13 + th, lw - 60)
        p.rect(x + lw, yy + 8, 2, rh - 16, 'lime')
        p.icon(row.get('icon', 'shield'), x + lw + 21, yy + 18, 13, 'lime_dark')
        p.para(row.get('why'), 'small', x + lw + 34, yy + 10, rw - 42, color='forest')
        yy += rh
    p.line(x, yy, x + w, yy, 'forest', 1.2)
    return yy - y + 2


def b_ladder(p, b, x, y, w):
    steps = b['steps']; n = len(steps); g = 8
    sw = (w - g * (n - 1)) / n
    base, inc = b.get('base', 58), b.get('step', 26)
    inner = [p.ph(s['title'], 'h4', sw - 20, color='white') + 16 for s in steps]
    bars = [max(base + k * inc, inner[k] + 26) for k in range(n)]
    top = max(bars)
    shades = p.ramp('forest_3', 'forest_deep', n)
    th = max(p.ph(s.get('text'), 'small', sw - 6) for s in steps)
    for k, s in enumerate(steps):
        sx = x + k * (sw + g)
        by = y + top - bars[k]
        last = s.get('highlight') or (k == n - 1 and b.get('highlight_last', True))
        p.top_rounded(sx, by, sw, bars[k], 'lime' if last else shades[k], 6)
        p.label(s.get('level', 'STEP %d' % (k + 1)), sx + 10, by + 10, 'meta',
                color='forest_deep' if last else 'on_dark_label', max_w=sw - 20)
        p.para(s['title'], 'h4', sx + 10, by + 24, sw - 20, color='forest_deep' if last else 'white')
        p.para(s.get('text'), 'small', sx + 2, y + top + 10, sw - 6)
    if n > 1 and not p.dry:
        p.line(x + sw / 2, y + top - bars[0] - 12, x + (n - 1) * (sw + g) + sw / 2, y + top - bars[-1] - 12,
               'gold', 1.2, dash=(3, 3))
    return top + (10 + th if th else 0)


def b_bar_chart(p, b, x, y, w):
    items = b['items']
    th = p.ph(b.get('title'), 'h4', w)
    lw = w * b.get('label_width', 0.38)
    vw = 64
    bw = w - lw - vw - 10
    mx = max(float(i['value']) for i in items)
    yy = y + (th + 10 if th else 0)
    p.para(b.get('title'), 'h4', x, y, w)
    for it in items:
        lh = p.ph(it['label'], 'small', lw - 10)
        rh = max(lh, 16) + 10
        p.para(it['label'], 'small', x, yy + (rh - lh) / 2 - 2, lw - 10)
        p.rect(x + lw, yy + rh / 2 - 7, bw, 12, 'mist', 6)
        p.rect(x + lw, yy + rh / 2 - 7, max(12, bw * float(it['value']) / mx), 12,
               'lime' if it.get('highlight') else 'forest', 6)
        p.para('<b>%s</b>' % it.get('display', it['value']), 'small', x + lw + bw + 8, yy + rh / 2 - 8, vw)
        yy += rh
    sh = p.ph(b.get('source'), 'caption', w)
    p.para(b.get('source'), 'caption', x, yy + 4, w)
    return yy - y + (sh + 4 if sh else 0)


def b_donut(p, b, x, y, w):
    segs = b['segments']
    r = b.get('radius', 58)
    total = float(sum(s['value'] for s in segs))
    colors = p.th['series']
    lx = x + 2 * r + 26
    lwid = w - (lx - x)
    th = p.ph(b.get('title'), 'h4', w)
    top = y + (th + 12 if th else 0)
    p.para(b.get('title'), 'h4', x, y, w)
    rows = [p.ph('<b>%s</b>  %s' % (s.get('display', s['value']), s['label']), 'small', lwid - 22) for s in segs]
    lh = sum(rows) + 8 * (len(rows) - 1)
    h = max(2 * r, lh)
    cy = top + h / 2
    if not p.dry:
        c = p.c
        start = 90.0
        for k, s in enumerate(segs):
            ext = -360.0 * s['value'] / total
            c.saveState(); c.setFillColor(HexColor(s.get('color') and p.hexc(s['color']) or colors[k % len(colors)]))
            c.wedge(x, p.H - cy - r, x + 2 * r, p.H - cy + r, start, ext, stroke=0, fill=1); c.restoreState()
            start += ext
        p.circle(x + r, cy, r * 0.6, fill=b.get('hole', 'paper'))
        ch = p.ph(b.get('centre'), 'kpi_sm', r * 1.1)
        cc = p.ph(b.get('centre_label'), 'caption', r * 1.1)
        p.para(b.get('centre'), 'kpi_sm', x + r * 0.45, cy - (ch + cc) / 2, r * 1.1, align='center')
        p.para(b.get('centre_label'), 'caption', x + r * 0.45, cy - (ch + cc) / 2 + ch, r * 1.1, align='center')
    yy = cy - lh / 2
    for k, s in enumerate(segs):
        p.rect(lx, yy + 2, 11, 11, s.get('color') or colors[k % len(colors)], 2)
        p.para('<b>%s</b>  %s' % (s.get('display', s['value']), s['label']), 'small', lx + 20, yy, lwid - 22)
        yy += rows[k] + 8
    return (top - y) + h


def b_matrix_2x2(p, b, x, y, w):
    """Consulting 2x2: axes labels plus four quadrants, one highlighted."""
    q = b['quadrants']
    ax = 22
    cw = (w - ax - 6) / 2
    hs = [p.ph(qq['title'], 'h4', cw - 28) + 4 + p.ph(qq.get('text'), 'small', cw - 28) for qq in q]
    ch = max(hs) + 28
    gx, gy = x + ax + 6, y
    for k, qq in enumerate(q):
        qx = gx + (k % 2) * cw
        qy = gy + (k // 2) * ch
        hi = qq.get('highlight')
        p.rect(qx + 2, qy + 2, cw - 4, ch - 4, 'forest' if hi else ('white' if k % 3 == 0 else 'mist'), 6)
        th = p.para(qq['title'], 'h4', qx + 14, qy + 14, cw - 28, color='white' if hi else None)
        p.para(qq.get('text'), 'small', qx + 14, qy + 18 + th, cw - 28, color='on_dark_muted' if hi else None)
    p.line(gx, gy + 2 * ch + 6, gx + 2 * cw, gy + 2 * ch + 6, 'forest', 1.2)
    p.line(gx - 6, gy, gx - 6, gy + 2 * ch, 'forest', 1.2)
    p.para('<b>%s</b>' % b.get('x_axis', ''), 'caption', gx, gy + 2 * ch + 10, 2 * cw, align='center')
    if not p.dry and b.get('y_axis'):
        c = p.c
        s = p.styles['caption']
        c.saveState(); c.translate(x + 8, p.H - (gy + ch)); c.rotate(90)
        c.setFont(p.ctx.font_names['SansBold'], s['size']); c.setFillColor(p.col('muted'))
        c.drawCentredString(0, 0, plain(b['y_axis'])); c.restoreState()
    return 2 * ch + 24


def b_split(p, b, x, y, w):
    ratio, g = b.get('ratio', 0.5), b.get('gap', 22)
    lw = (w - g) * ratio
    rw = w - g - lw
    lh = stack(p, b['left'], x, y, lw, measure_only=True)
    rh = stack(p, b['right'], x + lw + g, y, rw, measure_only=True)
    h = max(lh, rh)
    if b.get('valign') == 'center':
        stack(p, b['left'], x, y + (h - lh) / 2, lw)
        stack(p, b['right'], x + lw + g, y + (h - rh) / 2, rw)
    else:
        stack(p, b['left'], x, y, lw)
        stack(p, b['right'], x + lw + g, y, rw)
    if b.get('divider'):
        p.line(x + lw + g / 2, y, x + lw + g / 2, y + h, 'rule', 0.6)
    return h


def b_callout(p, b, x, y, w):
    pad = 20
    v = b.get('variant', 'dark')
    fill = {'dark': 'forest', 'soft': 'mist', 'gold': 'gold_tint'}[v]
    dark = v == 'dark'
    ic = 40 if b.get('icon') else 0
    tw = w - 2 * pad - ic
    th = p.ph(b.get('title'), 'callout_title', tw, color='white' if dark else 'forest')
    bh = p.ph(b.get('text'), 'body', tw, color='on_dark_muted' if dark else None)
    h = pad + th + (6 if th and bh else 0) + bh + pad
    p.rect(x, y, w, h, fill, 8)
    if ic:
        p.icon(b['icon'], x + pad + 14, y + pad + 12, 20, 'lime' if dark else 'forest',
               badge='forest_2' if dark else 'white', badge_r=17)
    p.para(b.get('title'), 'callout_title', x + pad + ic, y + pad, tw, color='white' if dark else 'forest')
    p.para(b.get('text'), 'body', x + pad + ic, y + pad + th + (6 if th and bh else 0), tw,
           color='on_dark_muted' if dark else None)
    return h


def b_pull_quote(p, b, x, y, w):
    qh = p.ph(b['text'], 'pull_quote', w - 24)
    ah = p.ph(b.get('attribution'), 'caption', w - 24)
    p.rect(x, y, 3, qh + (ah + 6 if ah else 0), 'lime')
    p.para(b['text'], 'pull_quote', x + 18, y, w - 24)
    p.para(b.get('attribution'), 'caption', x + 18, y + qh + 6, w - 24)
    return qh + (ah + 6 if ah else 0)


def b_checklist(p, b, x, y, w):
    items = b['items']; cols = b.get('columns', 2); g = 18
    cw = (w - g * (cols - 1)) / cols
    st = b.get('style', 'small')
    th = 0
    if b.get('title'):
        th = p.para(b['title'], 'h4', x, y, w) + 8
    yy = y + th
    for r in range(0, len(items), cols):
        row = items[r:r + cols]
        rh = max(p.ph(it, st, cw - 22) for it in row)
        for k, it in enumerate(row):
            ix = x + k * (cw + g)
            p.check_badge(ix + 7, yy + p.styles[st]['leading'] / 2, 6.5)
            p.para(it, st, ix + 20, yy, cw - 22)
        yy += rh + 8
    return yy - y - 8


def b_mentor(p, b, x, y, w):
    m = p.ctx.person(b.get('person', 'mentor'))
    pw = b.get('photo_width', 170)
    ph_ = pw * 1.18
    tx, tw = x + pw + 26, w - pw - 26
    yy = y
    lh, _ = p.label(b.get('kicker', 'YOUR LEAD MENTOR'), tx, yy, 'kicker', color='lime_dark', max_w=tw)
    yy += lh + 4
    yy += p.para(m['name'], 'h2', tx, yy, tw) + 2
    yy += p.para(m.get('role'), 'small', tx, yy, tw, color='muted') + 10
    yy += p.para(m.get('bio'), 'body', tx, yy, tw) + 10
    if m.get('credentials'):
        yy += b_checklist(p, {'items': m['credentials'], 'columns': b.get('cred_columns', 2)}, tx, yy, tw) + 12
    stats = m.get('stats', [])[:3]
    if stats and b.get('show_stats', True):
        sw = tw / len(stats)
        sh = max(p.ph(s['value'], 'kpi_sm', sw - 12) + 2 + p.ph(s['label'], 'caption', sw - 12) for s in stats)
        for k, s in enumerate(stats):
            sx = tx + k * sw
            if k:
                p.line(sx, yy, sx, yy + sh, 'rule', 0.6)
            vh = p.para(s['value'], 'kpi_sm', sx + (10 if k else 0), yy, sw - 12)
            p.para(s['label'], 'caption', sx + (10 if k else 0), yy + vh + 2, sw - 12)
        yy += sh
    h = max(ph_ + 10, yy - y)
    p.rect(x + 10, y + 10, pw, ph_, 'lime', 8)
    p.photo(m['photo'], x, y, pw, ph_, 'mentor profile', radius=8)
    return h


def b_testimonials(p, b, x, y, w):
    items = [p.ctx.testimonial(t) for t in b['ids']]
    cols = b.get('columns', min(3, len(items))); g = 12
    cw = (w - g * (cols - 1)) / cols
    pad = 16
    yy = y
    for r in range(0, len(items), cols):
        row = items[r:r + cols]
        qh = max(p.ph('“%s”' % t['quote'], 'quote', cw - 2 * pad) if t.get('quote') else 0 for t in row)
        oh = max(p.ph(t.get('outcome'), 'h4', cw - 2 * pad) for t in row)
        nh = max(p.ph('<b>%s</b>' % t['name'], 'small', cw - 2 * pad - 56) + p.ph(t.get('role'), 'caption', cw - 2 * pad - 56)
                 + p.ph(t.get('company'), 'caption', cw - 2 * pad - 56) for t in row)
        ah = max(46, nh)
        rh = pad + (oh + 8 if oh else 0) + (qh + 12 if qh else 0) + ah + pad
        for k, t in enumerate(row):
            tx = x + k * (cw + g)
            p.rect(tx, yy, cw, rh, 'white', 8)
            p.rect(tx, yy, cw, 4, 'lime')
            cy = yy + pad
            if oh:
                p.para(t.get('outcome'), 'h4', tx + pad, cy, cw - 2 * pad)
                cy += oh + 8
            if qh:
                p.para('“%s”' % t['quote'], 'quote', tx + pad, cy, cw - 2 * pad)
            ay = yy + rh - pad - ah
            if t.get('photo'):
                p.photo(t['photo'], tx + pad, ay, 46, 46, 'testimonial ' + t['name'], shape='circle', ring='lime')
            else:
                p.initials(t['name'], tx + pad + 23, ay + 23, 23)
            ny = ay + (ah - nh) / 2
            ny += p.para('<b>%s</b>' % t['name'], 'small', tx + pad + 56, ny, cw - 2 * pad - 56)
            ny += p.para(t.get('role'), 'caption', tx + pad + 56, ny, cw - 2 * pad - 56)
            p.para(t.get('company'), 'caption', tx + pad + 56, ny, cw - 2 * pad - 56, color='forest')
        yy += rh + g
    return yy - y - g


def b_pricing(p, b, x, y, w):
    opts = b['options']; n = len(opts); g = 12
    cw = (w - g * (n - 1)) / n
    pad = 18
    parts = []
    for o in opts:
        ps = o.get('price_style', 'price' if o.get('highlight') else 'price_sm')
        a = p.ph(o['price'], ps, cw - 2 * pad)
        nt = p.ph(o.get('note'), 'small', cw - 2 * pad)
        fe = _bul_h(p, o.get('features', []), cw - 2 * pad) if o.get('features') else 0
        parts.append((ps, a, nt, fe))
    h = pad + 14 + 8 + max(pp[1] for pp in parts) + 6 + max(pp[2] for pp in parts) + \
        (14 + max(pp[3] for pp in parts) if any(pp[3] for pp in parts) else 0) + pad
    for k, o in enumerate(opts):
        ox = x + k * (cw + g)
        hi = o.get('highlight')
        ps, a, nt, fe = parts[k]
        p.rect(ox, y, cw, h, 'forest' if hi else 'white', 8)
        if o.get('tag'):
            s = p.styles['meta']
            tag_w = pdfmetrics.stringWidth(plain(o['tag']).upper(), p.ctx.font_names[s['font']], s['size']) + \
                len(o['tag']) * s['tracking'] + 16
            p.rect(ox + cw - pad - tag_w, y - 9, tag_w, 18, 'lime', 9)
            p.label(o['tag'], ox + cw - pad - tag_w + 8, y - 4, 'meta', color='forest_deep')
        p.label(o['label'], ox + pad, y + pad, 'kicker', color='on_dark_label' if hi else 'forest', max_w=cw - 2 * pad)
        yy = y + pad + 22
        p.para(o['price'], ps, ox + pad, yy, cw - 2 * pad, color='white' if hi else None)
        yy += max(pp[1] for pp in parts) + 6
        p.para(o.get('note'), 'small', ox + pad, yy, cw - 2 * pad, color='on_dark_muted' if hi else 'muted')
        yy += max(pp[2] for pp in parts) + 14
        if o.get('features'):
            p.line(ox + pad, yy - 7, ox + cw - pad, yy - 7, 'forest_2' if hi else 'rule', 0.6)
            p.bullets(o['features'], 'small', ox + pad, yy, cw - 2 * pad, color='lime',
                      text_color='white' if hi else None)
    return h


def b_cta(p, b, x, y, w):
    pad = 26
    qs = 104 if b.get('qr_url') else 0
    tw = w - 2 * pad - (qs + 30 if qs else 0)
    th = p.ph(b['title'], 'cta_title', tw)
    bh = p.ph(b.get('text'), 'body', tw, color='on_dark_muted')
    steps = b.get('steps', [])
    sh = _bul_h(p, steps, tw, style='small') if steps else 0
    btn_text = b.get('button', 'Enrol now')
    bs = p.styles['button']
    btn_w = pdfmetrics.stringWidth(plain(btn_text), p.ctx.font_names[bs['font']], bs['size']) + 36
    ch = p.ph(b.get('contact'), 'caption', tw, color='on_dark_muted')
    content = th + 8 + bh + (12 + sh if sh else 0) + 16 + 32 + (12 + ch if ch else 0)
    h = pad + max(content, qs + 26) + pad
    p.rect(x, y, w, h, 'forest', 10)
    if not p.dry:
        c = p.c
        c.saveState(); c.setStrokeColor(p.col('forest_2')); c.setLineWidth(0.7)
        for k in range(9):
            pa = c.beginPath(); yy0 = p.H - (y + h - 10 - k * 9)
            pa.moveTo(x + w * 0.35, yy0); pa.curveTo(x + w * 0.55, yy0 + 30, x + w * 0.7, yy0 - 25, x + w - 2, yy0 + 12)
            c.drawPath(pa, stroke=1, fill=0)
        c.restoreState()
    yy = y + pad
    yy += p.para(b['title'], 'cta_title', x + pad, yy, tw) + 8
    yy += p.para(b.get('text'), 'body', x + pad, yy, tw, color='on_dark_muted')
    if steps:
        yy += 12
        yy_ = yy
        for k, s in enumerate(steps):
            hh = p.para(s, 'small', x + pad + 24, yy_, tw - 24, color='white')
            p.number_badge(x + pad + 8, yy_ + 7, 8, str(k + 1), fill='lime', color='forest_deep', style='caption')
            yy_ += hh + 5
        yy += sh
    yy += 16
    p.rect(x + pad, yy, btn_w, 32, 'lime', 16)
    p.para(btn_text, 'button', x + pad, yy + 9.5, btn_w, align='center')
    if b.get('url'):
        p.link(b['url'], x + pad, yy, btn_w, 32)
    if b.get('url_text'):
        p.para(b['url_text'], 'small', x + pad + btn_w + 14, yy + 9, tw - btn_w - 14, color='white')
        if b.get('url'):
            p.link(b['url'], x + pad + btn_w + 14, yy + 6, tw - btn_w - 14, 20)
    yy += 32
    if ch:
        p.para(b.get('contact'), 'caption', x + pad, yy + 12, tw, color='on_dark_muted')
    if qs:
        qx, qy = x + w - pad - qs - 6, y + (h - qs - 26) / 2
        p.rect(qx - 6, qy - 6, qs + 12, qs + 12, 'white', 8)
        p.qr(b['qr_url'], qx, qy, qs)
        p.para(b.get('qr_caption', 'Scan to enrol'), 'caption', qx - 6, qy + qs + 10, qs + 12,
               color='on_dark_muted', align='center')
    return h


def b_logo_strip(p, b, x, y, w):
    ids = b['ids']; n = len(ids); g = 10
    cw = (w - g * (n - 1)) / n
    hh = b.get('height', 44)
    for k, aid in enumerate(ids):
        lx = x + k * (cw + g)
        p.rect(lx, y, cw, hh, 'white', 6)
        p.logo(aid, lx + 10, y + 8, cw - 20, hh - 16, 'logo strip', align='center')
    return hh


def b_text_list(p, b, x, y, w):
    """Headed short paragraphs in columns (e.g. FAQs, 'who this is for')."""
    items = b['items']; cols = b.get('columns', 2); g = 22
    cw = (w - g * (cols - 1)) / cols
    yy = y
    for r in range(0, len(items), cols):
        row = items[r:r + cols]
        rh = max(p.ph(it['title'], 'h4', cw) + 4 + p.ph(it.get('text'), 'small', cw) for it in row)
        for k, it in enumerate(row):
            ix = x + k * (cw + g)
            th = p.para(it['title'], 'h4', ix, yy, cw)
            p.para(it.get('text'), 'small', ix, yy + th + 4, cw)
        yy += rh + 14
    return yy - y - 14


BLOCKS = {n[2:]: f for n, f in globals().items() if n.startswith('b_') and callable(f)}


def run_block(p, b, x, y, w):
    fn = BLOCKS.get(b.get('type'))
    if fn is None:
        raise BuildError('Unknown block type "%s"; available: %s' % (b.get('type'), ', '.join(sorted(BLOCKS))))
    return fn(p, b, x, y, w)


def stack(p, blocks, x, y, w, measure_only=False):
    was = p.dry
    if measure_only:
        p.dry = True
    yy = y
    gap = p.th['page']['inner_gap']
    for k, bl in enumerate(blocks):
        yy += run_block(p, bl, x, yy, w) + (bl.get('gap_after', gap) if k < len(blocks) - 1 else 0)
    p.dry = was
    return yy - y


def measure(p, b, w):
    was = p.dry
    p.dry = True
    try:
        return run_block(p, b, 0, 0, w)
    finally:
        p.dry = was


# ---------------------------------------------------------------- page templates

def page_frame(p, pg, i, n, cover=False):
    th = p.th['page']
    W, H, M = p.W, p.H, th['margin']
    bgrole = 'cover' if cover else 'standard'
    p.rect(0, 0, W, H, p.th['page_backgrounds'][bgrole])
    p.rect(0, 0, W, th['top_bar'], 'lime' if cover else 'forest')
    lx, ly, lw, lh = th['header_logo_box']
    p.logo('logo', lx, ly, lw, lh, 'header')
    if not cover:
        p.label(p.ctx.prog['programme'].get('header_label', ''), W - M, th['header_label_y'], 'meta', align='right',
                max_w=W - 2 * M - lw - 20)
    p.line(M, th['footer_rule_y'], W - M, th['footer_rule_y'], 'rule', 0.6)
    p.label(p.ctx.prog['programme'].get('footer_label', ''), M, th['footer_text_y'], 'footer', max_w=W - 2 * M - 70)
    p.label('%02d / %02d' % (i, n), W - M, th['footer_text_y'] - 1, 'footer_num', align='right')


def page_title(p, pg, x, y, w):
    yy = y
    if pg.get('kicker'):
        s, _ = p.label(pg['kicker'], x, yy, 'kicker', max_w=w)
        yy += s + 12
    t1 = p.para(pg['title'], 'h1', x, yy, w)
    lines = p.lines(pg['title'], 'h1', w)
    yy += t1
    if pg.get('title_em'):
        yy += p.para(pg['title_em'], 'h1_em', x, yy, w)
        lines += p.lines(pg['title_em'], 'h1_em', w)
    if lines > p.th['design_rules']['max_title_lines']:
        p.ctx.errors.append('Page %d: action title runs to %d lines (max %d); shorten it'
                            % (p.page_no, lines, p.th['design_rules']['max_title_lines']))
    if pg.get('subtitle'):
        yy += 8 + p.para(pg['subtitle'], 'sub', x, yy + 8, w)
    return yy - y


def draw_standard(p, pg, i, n):
    th = p.th['page']
    M, W = th['margin'], p.W - 2 * th['margin']
    page_frame(p, pg, i, n)
    y = th['content_top']
    y += page_title(p, pg, M, y, W) + th['block_gap'] + 4
    bottom = th['content_bottom']
    top = y
    gap = th['block_gap']
    blocks = pg.get('blocks', [])
    total = sum(measure(p, b, W) for b in blocks) + gap * max(0, len(blocks) - 1)
    free = bottom - y - total
    if free < -0.5:
        p.ctx.errors.append('Page %d overflows by %.0fpt; cut copy, drop a block or split the page' % (i, -free))
    elif free > (bottom - top) * th['underfill_warning_ratio'] and not pg.get('allow_whitespace'):
        p.ctx.warnings.append('Page %d leaves %.0fpt empty; add an infographic or enlarge one' % (i, free))
    extra = 0
    if pg.get('distribute', True) and free > 0 and len(blocks) > 1:
        extra = min(free / (len(blocks) - 1), pg.get('max_spread', 30))
    for b in blocks:
        h = run_block(p, b, M, y, W)
        y += h + gap + b.get('gap_after_extra', 0) + extra
    return [b.get('type') for b in blocks]


def draw_cover(p, pg, i, n):
    th = p.th['page']
    M, W, H = th['margin'], p.W - 2 * th['margin'], p.H
    page_frame(p, pg, i, n, cover=True)
    prog = p.ctx.prog['programme']
    y = 118
    s, _ = p.label(pg.get('kicker', prog.get('kicker', '')), M, y, 'cover_kicker', max_w=W)
    y += s + 16
    y += p.para(pg['title'], 'cover_title', M - 2, y, W - 20)
    if pg.get('title_em'):
        y += 2 + p.para(pg['title_em'], 'cover_em', M, y + 2, W - 40)
    y += 12
    y += p.para(pg.get('subtitle'), 'cover_sub', M, y, W - 60) + 8
    y += p.para(pg.get('lead'), 'cover_lead', M, y, W - 120)
    # forest proof band
    band_top = y + pg.get('band_gap', 34)
    qf_h = 70 if pg.get('quick_facts') else 0
    band_h = th['footer_rule_y'] - 40 - qf_h - band_top
    p.rect(0, band_top, p.W, band_h, 'forest')
    if not p.dry:
        c = p.c
        c.saveState(); c.setStrokeColor(p.col('forest_2')); c.setLineWidth(0.6)
        for k in range(10):
            yy0 = H - (band_top + band_h - 150 + k * 12)
            pa = c.beginPath(); pa.moveTo(0, yy0); pa.curveTo(200, yy0 + 80, 420, yy0 - 90, p.W, yy0 + 10)
            c.drawPath(pa, stroke=1, fill=0)
        c.restoreState()
    # left: proof KPIs (2x2) ; right: mentor photo card
    col_w = 372
    p.label(pg.get('band_label', 'PROOF, NOT PROMISES'), M, band_top + 24, 'kicker', color='on_dark_label')
    kpis = pg.get('kpis', [])
    kw, kh, g = (col_w - 10) / 2, 92, 10
    for k, it in enumerate(kpis[:4]):
        kx = M + (k % 2) * (kw + g)
        ky = band_top + 50 + (k // 2) * (kh + g)
        p.rect(kx, ky, kw, kh, 'forest_deep', 8)
        p.icon(it.get('icon', 'check'), kx + 24, ky + 24, 18, 'lime', badge='forest_2', badge_r=15)
        p.para(it['value'], 'kpi', kx + 48, ky + 12, kw - 58, color='white')
        p.para(it['label'], 'small', kx + 48, ky + 48, kw - 58, color='on_dark_muted')
    ky_end = band_top + 50 + 2 * (kh + g)
    p.para(pg.get('band_statement'), 'callout_title', M, ky_end + 8, col_w, color='white')
    m = p.ctx.person(pg.get('mentor', 'mentor'))
    px, pw = M + col_w + 40, W - col_w - 40
    pht = min(pw, 200)
    p.photo(pg.get('mentor_photo', m.get('cover_photo', m['photo'])), px + (pw - pht) / 2, band_top + 34, pht, pht,
            'cover mentor', shape='circle', ring='lime')
    ny = band_top + 34 + pht + 14
    ny += p.para(m['name'], 'h3', px, ny, pw, color='white', align='center') + 2
    p.para(m.get('cover_line', m.get('role')), 'small', px, ny, pw, color='on_dark_muted', align='center')
    wf = pg.get('workflow', [])
    if wf:
        cy0 = band_top + band_h - 66
        cw = (W - 10 * (len(wf) - 1)) / len(wf)
        for k, step in enumerate(wf):
            cx0 = M + k * (cw + 10)
            p.rect(cx0, cy0, cw, 44, 'forest_deep', 6)
            p.rect(cx0, cy0, 4, 44, 'lime')
            p.label('%02d  %s' % (k + 1, step['title']), cx0 + 16, cy0 + 9, 'meta', color='on_dark_label', max_w=cw - 24)
            p.para(step.get('text'), 'small', cx0 + 16, cy0 + 22, cw - 24, color='white')
    # quick facts row
    qy = band_top + band_h + 24
    facts = pg.get('quick_facts', [])
    if facts:
        fw = W / len(facts)
        for k, f in enumerate(facts):
            fx = M + k * fw
            p.icon(f.get('icon', 'check'), fx + 11, qy + 11, 16, 'forest', badge='mist', badge_r=13)
            p.label(f['label'], fx + 32, qy + 1, 'meta', color='forest', max_w=fw - 36)
            p.para(f['value'], 'small', fx + 32, qy + 14, fw - 36)
    if pg.get('disclaimer'):
        p.para(pg['disclaimer'], 'caption', M, th['footer_rule_y'] - 22, W)
    return ['cover']


# ---------------------------------------------------------------- build

def register_fonts(ctx):
    ctx.font_names = {}
    for alias, path in ctx.theme['fonts'].items():
        fp = rel(ROOT, path)
        if not fp.is_file():
            raise BuildError('Missing font %s; no substitution is allowed' % fp)
        name = 'ESG' + alias
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(fp)))
        ctx.font_names[alias] = name
    pdfmetrics.registerFontFamily('ESGSans', normal='ESGSans', bold='ESGSansBold', italic='ESGSansItalic',
                                  boldItalic='ESGSansBold')
    pdfmetrics.registerFontFamily('ESGSerif', normal='ESGSerif', bold='ESGSerifBold', italic='ESGSerifItalic',
                                  boldItalic='ESGSerifBold')


def lint(ctx, pages):
    text = json.dumps(pages, ensure_ascii=False) + json.dumps(ctx.prog.get('programme', {}), ensure_ascii=False)
    for rv in ctx.facts.get('retired_values', []):
        if rv['value'] in text:
            ctx.errors.append('Retired fact "%s" found (%s). Use {{fact.%s}}' % (rv['value'], rv['reason'], rv['use']))
    for g in ctx.facts.get('fact_guards', []):
        want = ctx.tokens.get('fact.' + g['fact'])
        for m in re.finditer(g['pattern'], plain(text), re.I):
            if m.group(1) != want:
                ctx.errors.append('Stale or conflicting figure "%s"; the shared fact is %s. Use {{fact.%s}}'
                                  % (m.group(0), want, g['fact']))
    for m in UNFINISHED.finditer(text):
        ctx.errors.append('Unfinished content marker "%s"; run the intake questions' % m.group(0))


def variety(ctx, used):
    rules = ctx.theme['design_rules']
    infog = set(ctx.theme['infographic_blocks'])
    counts = {}
    for i, types in enumerate(used, 1):
        if types == ['cover']:
            continue
        flat = set(types)
        if rules['require_infographic_per_page'] and not (flat & infog):
            ctx.errors.append('Page %d has no infographic block; add one of: %s' % (i, ', '.join(sorted(infog))))
        for t in flat & infog:
            counts.setdefault(t, []).append(i)
    for t, pages in counts.items():
        if len(pages) > rules['max_same_block_type_pages']:
            ctx.warnings.append('Visual repetition: "%s" appears on pages %s' % (t, pages))


def collect_types(blocks):
    out = []
    for b in blocks:
        out.append(b.get('type'))
        if b.get('type') == 'split':
            out += collect_types(b.get('left', [])) + collect_types(b.get('right', []))
    return out


def build(programme, output, proof=False, previews=False, allow_placeholders=False, dpi=150):
    ctx = Context(programme, proof=proof, allow_placeholders=allow_placeholders)
    register_fonts(ctx)
    if 'page_backgrounds' in json.dumps(ctx.prog.get('pages', [])) or \
            any('background' in pg for pg in ctx.prog.get('pages', [])):
        ctx.errors.append('Page backgrounds are theme-locked; remove "background" from the programme file')
    pages = ctx.resolve(ctx.prog['pages'], 'pages')
    ctx.prog['programme'] = ctx.resolve(ctx.prog['programme'], 'programme')
    lint(ctx, pages)
    th = ctx.theme['page']
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + '.building.pdf')
    c = canvas.Canvas(str(tmp), pagesize=(ctx.theme['page']['width'], ctx.theme['page']['height']),
                      initialFontName=ctx.font_names['Sans'], initialFontSize=10)
    prog = ctx.prog['programme']
    c.setTitle(prog['title'] + (' - REVIEW PROOF' if proof else ''))
    c.setAuthor(ctx.facts.get('organisation', {}).get('name', 'ESGPro Mastery Institute'))
    c.setSubject(prog.get('subtitle', ''))
    c.setCreator('ESGPro brochure builder 2.0')
    used = []
    for i, pg in enumerate(pages, 1):
        p = Pen(c, ctx, ctx.theme['styles'], i)
        if pg.get('template') == 'cover':
            used.append(draw_cover(p, pg, i, len(pages)))
        else:
            draw_standard(p, pg, i, len(pages))
            used.append(collect_types(pg.get('blocks', [])))
        if proof:
            p.rect(0, 0, p.W, 16, 'gold')
            p.label('REVIEW PROOF - FACTS PENDING OWNER APPROVAL - NOT FOR CIRCULATION', p.W / 2, 3, 'meta',
                    color='ink', align='center')
        c.showPage()
    ctx.assets.finish()
    variety(ctx, used)
    ctx.errors = list(dict.fromkeys(ctx.errors))
    c.save()
    report = {
        'programme': prog['title'], 'output': str(out), 'mode': 'proof' if proof else 'clean',
        'pages': len(pages), 'errors': ctx.errors, 'warnings': sorted(set(ctx.warnings)),
        'images': ctx.assets.report(), 'facts_used': sorted(k for k in ctx.used_tokens if k.startswith('fact.')),
        'page_blocks': used,
    }
    if ctx.errors:
        failed = out.with_name(out.stem + '.FAILED.pdf')
        tmp.replace(failed)
        report['output'] = str(failed)
        out.with_suffix('.qa.json').write_text(json.dumps(report, indent=2, ensure_ascii=False))
        raise BuildError('\n'.join(ctx.errors) + '\nInspection copy: %s' % failed)
    tmp.replace(out)
    if previews:
        report['previews'] = render_previews(out, dpi=dpi)
    out.with_suffix('.qa.json').write_text(json.dumps(report, indent=2, ensure_ascii=False))
    return report


def render_previews(pdf, dpi=150):
    outdir = Path(pdf).with_suffix('')
    outdir = outdir.parent / (outdir.name + '_previews')
    outdir.mkdir(parents=True, exist_ok=True)
    try:
        import pymupdf
        d = pymupdf.open(str(pdf))
        files = []
        for k, page in enumerate(d, 1):
            f = outdir / ('page_%02d.png' % k)
            page.get_pixmap(dpi=dpi).save(str(f))
            files.append(str(f))
        return files
    except ImportError:
        pass
    import shutil, subprocess
    if shutil.which('pdftoppm'):
        prefix = str(outdir / 'page')
        subprocess.run(['pdftoppm', '-png', '-r', str(dpi), str(pdf), prefix], check=False)
        return [str(p) for p in sorted(outdir.glob('page-*.png'))]
    return 'PyMuPDF or pdftoppm not installed; install pymupdf for PNG previews'


# ---------------------------------------------------------------- intake

def get_path(obj, dotted):
    for part in dotted.split('.'):
        if isinstance(obj, dict) and part in obj:
            obj = obj[part]
        else:
            return None
    return obj


def intake(programme_path, as_json=False):
    """List intake questions whose answers are missing or unfinished in the programme file."""
    prog = load(programme_path)
    qs = load(ROOT / 'intake/questions.json')['questions']
    open_q = []
    for q in qs:
        v = get_path(prog, q['key'])
        blank = v is None or v == '' or v == [] or (isinstance(v, str) and UNFINISHED.search(v))
        if blank and q.get('required', True):
            open_q.append(q)
    if as_json:
        print(json.dumps(open_q, indent=2, ensure_ascii=False))
    else:
        if not open_q:
            print('All intake questions answered for %s.' % programme_path)
        for k, q in enumerate(open_q, 1):
            print('%2d. [%s] %s' % (k, q['group'], q['question']))
            if q.get('example'):
                print('    e.g. %s' % q['example'])
    return open_q


def validate_programme(programme, allow_placeholders=False):
    """Validate programme content, token references, and assets without building PDF."""
    ctx = Context(programme, proof=True, allow_placeholders=allow_placeholders)
    register_fonts(ctx)
    if 'page_backgrounds' in json.dumps(ctx.prog.get('pages', [])) or \
            any('background' in pg for pg in ctx.prog.get('pages', [])):
        ctx.errors.append('Page backgrounds are theme-locked; remove "background" from the programme file')
    pages = ctx.resolve(ctx.prog['pages'], 'pages')
    ctx.prog['programme'] = ctx.resolve(ctx.prog['programme'], 'programme')
    lint(ctx, pages)
    used = []
    for pg in pages:
        if pg.get('template') != 'cover':
            used.append(collect_types(pg.get('blocks', [])))
    ctx.assets.finish()
    variety(ctx, used)
    ctx.errors = list(dict.fromkeys(ctx.errors))
    ctx.warnings = sorted(set(ctx.warnings))
    qs = load(ROOT / 'intake/questions.json')['questions']
    open_q = []
    for q in qs:
        v = get_path(ctx.prog, q['key'])
        blank = v is None or v == '' or v == [] or (isinstance(v, str) and UNFINISHED.search(v))
        if blank and q.get('required', True):
            open_q.append(f"{q['group']}.{q['key']}")
    return {
        'programme': ctx.prog['programme'].get('title', 'Unknown'),
        'valid': len(ctx.errors) == 0,
        'pages': len(pages),
        'errors': ctx.errors,
        'warnings': ctx.warnings,
        'open_intake_questions': open_q,
        'facts_used': sorted(k for k in ctx.used_tokens if k.startswith('fact.')),
    }


def new_programme(pid):
    dst = ROOT / 'programmes' / (pid + '.json')
    if dst.exists():
        raise BuildError('%s already exists' % dst)
    shutil.copy(ROOT / 'programmes/_template.json', dst)
    print('Created %s. Answer these before building:\n' % dst)
    intake(dst)
    return dst


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('programme')
    b.add_argument('--output')
    b.add_argument('--proof', action='store_true', help='add the review ribbon')
    b.add_argument('--previews', action='store_true', help='also write PNG page previews (needs PyMuPDF)')
    b.add_argument('--dpi', type=int, default=150, help='preview DPI (default: 150)')
    b.add_argument('--allow-placeholders', action='store_true', help='draw visible placeholders for missing images')
    v = sub.add_parser('validate', help='validate programme content and assets without building PDF')
    v.add_argument('programme')
    v.add_argument('--allow-placeholders', action='store_true')
    v.add_argument('--json', action='store_true')
    i = sub.add_parser('intake')
    i.add_argument('programme')
    i.add_argument('--json', action='store_true')
    nw = sub.add_parser('new')
    nw.add_argument('id')
    a = ap.parse_args(argv)
    try:
        if a.cmd == 'build':
            outp = a.output or str(ROOT / 'output' / (Path(a.programme).stem + ('.proof' if a.proof else '') + '.pdf'))
            r = build(a.programme, outp, a.proof, a.previews, a.allow_placeholders, dpi=a.dpi)
            print(json.dumps({k: r[k] for k in ('output', 'mode', 'pages', 'warnings')}, indent=2, ensure_ascii=False))
        elif a.cmd == 'validate':
            res = validate_programme(a.programme, a.allow_placeholders)
            if a.json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                status_str = 'VALID' if res['valid'] else 'INVALID'
                print(f"Validation for: {res['programme']} ({res['pages']} pages) - Status: {status_str}")
                if res['open_intake_questions']:
                    print(f"Open intake questions ({len(res['open_intake_questions'])}): {', '.join(res['open_intake_questions'])}")
                if res['warnings']:
                    print(f"Warnings ({len(res['warnings'])}):")
                    for w in res['warnings']:
                        print(f"  - {w}")
                if res['errors']:
                    print(f"Errors ({len(res['errors'])}):")
                    for e in res['errors']:
                        print(f"  - {e}")
            sys.exit(0 if res['valid'] else 2)
        elif a.cmd == 'intake':
            sys.exit(3 if intake(a.programme, a.json) else 0)
        else:
            new_programme(a.id)
    except BuildError as e:
        print('BUILD BLOCKED:\n' + str(e), file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()
