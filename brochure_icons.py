"""Line icons drawn as vectors on a 24-unit grid (origin bottom-left).

Every icon uses the same stroke weight, round caps and grid so infographics look
like one family. No external artwork is needed and nothing is rasterised.
"""
import math


def _poly(c, pts, close=False, fill=0):
    p = c.beginPath()
    p.moveTo(*pts[0])
    for pt in pts[1:]:
        p.lineTo(*pt)
    if close:
        p.close()
    c.drawPath(p, stroke=1, fill=fill)


def leaf(c):
    p = c.beginPath(); p.moveTo(5, 5); p.curveTo(5, 16, 11, 21, 20, 20); p.curveTo(20, 11, 15, 5, 5, 5); p.close()
    c.drawPath(p, stroke=1, fill=0); c.line(5, 5, 14, 14)


def factory(c):
    _poly(c, [(3, 4), (3, 13), (8, 10), (8, 13), (13, 10), (13, 13), (16, 11), (16, 20), (20, 20), (20, 4)], close=True)
    for x in (6, 10, 14):
        c.rect(x, 6.5, 1.8, 1.8, stroke=0, fill=1)


def chart(c):
    c.line(4, 4, 4, 20); c.line(4, 4, 20, 4)
    for x, h in ((7, 5), (12, 9), (17, 13)):
        c.rect(x, 4, 2.6, h, stroke=1, fill=0)


def trend(c):
    _poly(c, [(3, 6), (9, 12), (13, 9), (20, 17)]); _poly(c, [(15, 17), (20, 17), (20, 12)])


def target(c):
    c.circle(12, 12, 9); c.circle(12, 12, 5.5); c.circle(12, 12, 1.8, stroke=0, fill=1)


def globe(c):
    c.circle(12, 12, 9); c.ellipse(8, 3, 16, 21); c.line(3, 12, 21, 12)
    c.line(4.6, 7, 19.4, 7); c.line(4.6, 17, 19.4, 17)


def document(c):
    _poly(c, [(6, 3), (6, 21), (14, 21), (18, 17), (18, 3)], close=True); _poly(c, [(14, 21), (14, 17), (18, 17)])
    c.line(9, 13, 15, 13); c.line(9, 10, 15, 10); c.line(9, 7, 13, 7)


def people(c):
    c.circle(9, 15, 3); c.circle(16.5, 15.5, 2.4)
    c.arc(3, 1, 15, 13, 0, 180); c.arc(12.5, 4, 21, 13, 20, 160)


def calendar(c):
    c.roundRect(4, 4, 16, 15, 2); c.line(4, 15, 20, 15); c.line(8, 17, 8, 21); c.line(16, 17, 16, 21)
    for x, y in ((7, 10.5), (11, 10.5), (15, 10.5), (7, 6.5), (11, 6.5)):
        c.rect(x, y, 2, 2, stroke=0, fill=1)


def certificate(c):
    c.roundRect(3, 8, 18, 12, 1.5); c.line(6, 16, 14, 16); c.line(6, 13, 11, 13)
    c.circle(16, 9.5, 3); c.line(14.6, 6.8, 13.6, 3); c.line(17.4, 6.8, 18.4, 3)


def shield(c):
    p = c.beginPath(); p.moveTo(12, 21); p.curveTo(15, 19.5, 18, 19, 20, 19); p.lineTo(20, 12)
    p.curveTo(20, 7, 16, 4, 12, 3); p.curveTo(8, 4, 4, 7, 4, 12); p.lineTo(4, 19); p.curveTo(6, 19, 9, 19.5, 12, 21); p.close()
    c.drawPath(p, stroke=1, fill=0); _poly(c, [(8.5, 12), (11, 9.5), (15.5, 14.5)])


def gear(c):
    c.circle(12, 12, 3.2); c.circle(12, 12, 7)
    for k in range(8):
        a = k * math.pi / 4
        c.line(12 + 7 * math.cos(a), 12 + 7 * math.sin(a), 12 + 9.5 * math.cos(a), 12 + 9.5 * math.sin(a))


def bolt(c):
    _poly(c, [(13.5, 21), (5.5, 11), (11, 11), (9.5, 3), (18.5, 14), (13, 14), (15, 21)], close=True)


def truck(c):
    c.rect(2, 8, 12, 10); _poly(c, [(14, 8), (14, 15), (18, 15), (21, 11), (21, 8)], close=True)
    c.circle(6, 6, 2); c.circle(17, 6, 2)


def coins(c):
    for y in (4, 9, 14):
        c.ellipse(5, y, 19, y + 5)


def check(c):
    _poly(c, [(5, 12), (10, 7), (19, 17)])


def book(c):
    c.line(12, 6, 12, 19)
    for s in (1, -1):
        p = c.beginPath(); p.moveTo(12, 19); p.curveTo(12 - s * 3, 20, 12 - s * 6, 20, 12 - s * 9, 19)
        p.lineTo(12 - s * 9, 6); p.curveTo(12 - s * 6, 7, 12 - s * 3, 7, 12, 6); c.drawPath(p, stroke=1, fill=0)


def search(c):
    c.circle(10, 14, 6); c.line(14.3, 9.7, 20, 4)


def layers(c):
    _poly(c, [(12, 20), (21, 15.5), (12, 11), (3, 15.5)], close=True)
    _poly(c, [(3, 11.5), (12, 7), (21, 11.5)]); _poly(c, [(3, 7.5), (12, 3), (21, 7.5)])


def clock(c):
    c.circle(12, 12, 9); c.line(12, 12, 12, 17.5); c.line(12, 12, 16, 10)


def mic(c):
    c.roundRect(9, 9, 6, 11, 3); c.arc(6, 5, 18, 17, 180, 180); c.line(12, 5, 12, 3); c.line(9, 3, 15, 3)


def network(c):
    nodes = [(12, 19), (5, 7), (19, 7), (12, 11.5)]
    for a, b in ((0, 3), (1, 3), (2, 3), (1, 2)):
        c.line(*nodes[a], *nodes[b])
    for x, y in nodes:
        c.circle(x, y, 2.2, stroke=1, fill=1)


def bulb(c):
    c.arc(6, 8, 18, 20, -40, 260); c.line(9.5, 8.8, 10, 6); c.line(14.5, 8.8, 14, 6)
    c.line(10, 6, 14, 6); c.line(10.5, 3.8, 13.5, 3.8)


def cycle(c):
    c.arc(4, 4, 20, 20, 60, 270)
    ex, ey = 12 + 8 * math.cos(math.radians(330)), 12 + 8 * math.sin(math.radians(330))
    _poly(c, [(ex - 3.5, ey - 0.5), (ex, ey), (ex + 0.6, ey + 3.4)])


def flag(c):
    c.line(5, 3, 5, 21); _poly(c, [(5, 20), (18, 20), (15, 16.5), (18, 13), (5, 13)])


def building(c):
    c.rect(5, 3, 14, 18)
    for x in (8, 11, 14):
        for y in (15, 11, 7):
            c.rect(x, y, 1.8, 1.8, stroke=0, fill=1)


def briefcase(c):
    c.roundRect(3, 5, 18, 12, 2); c.rect(9, 17, 6, 3); c.line(3, 11, 21, 11)


def cloud(c):
    p = c.beginPath(); p.moveTo(6.5, 7); p.curveTo(2.5, 7, 2.5, 13, 6.5, 13); p.curveTo(7, 18, 14, 19, 15.5, 14.5)
    p.curveTo(19.5, 16, 22, 12, 19.5, 9.5); p.curveTo(21, 7.5, 19.5, 7, 18, 7); p.close(); c.drawPath(p, stroke=1, fill=0)


def co2(c):
    cloud(c)
    c.saveState(); c.setFont('Helvetica-Bold', 5.2); c.drawCentredString(12, 9, 'CO2'); c.restoreState()


def medal(c):
    c.circle(12, 14, 6); c.circle(12, 14, 2.6)
    _poly(c, [(8.5, 9.2), (6.5, 2.5), (9.3, 4), (10.8, 2)]); _poly(c, [(15.5, 9.2), (17.5, 2.5), (14.7, 4), (13.2, 2)])


def mail(c):
    c.roundRect(3, 6, 18, 13, 1.5); _poly(c, [(3.5, 18), (12, 11.5), (20.5, 18)])


def route(c):
    c.circle(5, 6, 2.2); c.circle(19, 18, 2.2)
    p = c.beginPath(); p.moveTo(7, 6); p.curveTo(15, 6, 9, 18, 17, 18); c.drawPath(p, stroke=1, fill=0)


def scale(c):
    c.line(12, 4, 12, 19); c.line(5, 17, 19, 17); c.line(8, 4, 16, 4)
    _poly(c, [(2.5, 11), (5, 17), (7.5, 11)]); c.arc(2.5, 8.5, 7.5, 13.5, 180, 180)
    _poly(c, [(16.5, 11), (19, 17), (21.5, 11)]); c.arc(16.5, 8.5, 21.5, 13.5, 180, 180)


ICONS = {n: f for n, f in globals().items() if callable(f) and not n.startswith('_') and n not in ('math',)}
ICONS.pop('draw', None)


def draw(c, name, cx, cy, size, color, width=1.7):
    """Draw icon `name` centred on (cx, cy) in PDF coordinates."""
    fn = ICONS.get(name)
    if fn is None:
        raise KeyError('Unknown icon "%s"; available: %s' % (name, ', '.join(sorted(ICONS))))
    c.saveState()
    c.translate(cx - size / 2.0, cy - size / 2.0)
    c.scale(size / 24.0, size / 24.0)
    c.setStrokeColor(color); c.setFillColor(color)
    c.setLineWidth(width); c.setLineCap(1); c.setLineJoin(1)
    fn(c)
    c.restoreState()
