import math
import graphics
from vector_math import vec2, line_length, radian, intersection


class LineSegment(object):
    def __init__(self, startp, endp, w=0):
        self.start = startp
        self.end = endp
        self.w = w
        self.upper_v = []
        self.lower_v = []
        if w > 0:
            self.calculate_tangents()
        self.upper_join = None
        self.lower_join = None

    @property
    def upper_edge(self):
        return LineSegment(self.start + self.up_normal,
                           self.end + self.up_normal)

    @property
    def lower_edge(self):
        return LineSegment(self.start + self.dn_normal,
                           self.end + self.dn_normal)

    def calculate_tangents(self):
        v = (self.end - self.start).normalized()
        angle = math.atan2(v.y, v.x)
        half_width = self.w * 0.5
        self.up_normal = vec2(math.cos(angle - radian(90)) * half_width,
                              math.sin(angle - radian(90)) * half_width)
        self.dn_normal = vec2(math.cos(angle + radian(90)) * half_width,
                              math.sin(angle + radian(90)) * half_width)


def _process_joint(ln, pln, miter_limit):
    up_intersection, ln.upper_join = ln_intersection(pln.upper_edge, ln.upper_edge)
    lo_intersection, ln.lower_join = ln_intersection(pln.lower_edge, ln.lower_edge)

    if ln.upper_join == None:
        ln.upper_join = ln.upper_edge.start

    if ln.lower_join == None:
        ln.lower_join = ln.lower_edge.start

    if line_length(ln.upper_edge.start, ln.upper_join) > miter_limit and not up_intersection:
        #bevel
        ln.upper_join = ln.upper_edge.start
        pln.upper_v.append(pln.upper_join)
        pln.upper_v.append(pln.upper_edge.end)
        pln.upper_v.append(ln.upper_join)
    else:
        pln.upper_v.append(pln.upper_join)
        pln.upper_v.append(ln.upper_join)

    if line_length(ln.lower_edge.start, ln.lower_join) > miter_limit and not lo_intersection:
        #bevel
        ln.lower_join = ln.lower_edge.start
        pln.lower_v.append(pln.lower_join)
        pln.lower_v.append(pln.lower_edge.end)
        pln.lower_v.append(ln.lower_join)
    else:
        pln.lower_v.append(pln.lower_join)
        pln.lower_v.append(ln.lower_join)


class DashGenerator:

    def __init__(self, pattern):
        self.pattern = pattern
        self.index = 0
        self.remainder = 0

        if len(pattern) % 2 == 1:
            self.pattern *= 2

    def next(self, limit):
        start_index = int(self.index)
        pct = self.index - int(self.index)
        n = self.pattern[int(self.index)] * (1-pct)
        if n > limit:
            n = limit
        consumed = n/self.pattern[int(self.index)]
        self.index = (self.index + consumed) % len(self.pattern)

        should_flip = (int(self.index) - start_index) > 0
        return n, should_flip


def split_line_by_pattern(points, pattern):

    dg = DashGenerator(pattern)
    lines = []
    is_whitespace = False

    for p in xrange(1, len(points)):
        start = vec2(points[p-1])
        end = vec2(points[p])
        normal = (end - start).normalized()
        amount_to_move = (end - start).length()

        current = start
        while amount_to_move > 0:
            l, should_flip = dg.next(amount_to_move)
            a = current
            b = current + normal * l
            current = b
            if not is_whitespace:
                lines.append((a, b))
            if should_flip:
                is_whitespace = not is_whitespace
            amount_to_move -= l
    return lines


def calc_polyline(points, w, miter_limit=4, closed=False):
    points = [vec2(p) for p in points]
    if closed and points[0] != points[-1]:
        points.append(vec2(points[0]))

    lines = []
    for i in range(len(points) - 1):
        lines.append(
            LineSegment(points[i], points[i+1], w))

    lines[0].upper_join = lines[0].upper_edge.start
    lines[0].lower_join = lines[0].lower_edge.start

    for i in range(1, len(lines)):
        ln, pln = lines[i], lines[i-1]
        _process_joint(ln, pln, miter_limit)

    ll = lines[-1]
    lf = lines[0]
    if closed:
        b_up_int, upper_join = ln_intersection(ll.upper_edge, lf.upper_edge)
        b_lo_int, lower_join = ln_intersection(ll.lower_edge, lf.lower_edge)

        if upper_join == None: upper_join = ll.upper_edge.end
        if lower_join == None: lower_join = ll.lower_edge.end

        if line_length(ll.upper_edge.end, upper_join) > miter_limit and b_up_int:
            ll.upper_v.append(ll.upper_join)
            ll.upper_v.append(ll.upper_edge.end)
            ll.upper_v.append(lf.upper_edge.start)
        else:
            lf.upper_v[0] = upper_join
            ll.upper_v.append(ll.upper_join)
            ll.upper_v.append(upper_join)

        if line_length(ll.lower_edge.end, lower_join) > miter_limit and b_lo_int:
            ll.lower_v.append(ll.lower_join)
            ll.lower_v.append(ll.lower_edge.end)
            ll.lower_v.append(lf.lower_edge.start)
        else:
            lf.lower_v[0] = lower_join
            ll.lower_v.append(ll.lower_join)
            ll.lower_v.append(lower_join)

    else:
        ll.upper_v.append(ll.upper_join)
        ll.upper_v.append(ll.upper_edge.end)
        ll.lower_v.append(ll.lower_join)
        ll.lower_v.append(ll.lower_edge.end)

    return lines


def draw_polyline(points, w, colors=None, miter_limit=10, closed=False, debug=False):
    if len(points) == 0:
        return

    #remove any duplicate points
    unique_points = []
    unique_colors = []
    last_point = None
    for p in points:
        if p != last_point:
            unique_points.append(p)
        last_point = p
    points = unique_points

    if len(points) == 1:
        return

    if points[0] == points[-1]:
        closed = True

    lines = calc_polyline(points, w, miter_limit, closed)
    swap = False
    vertices = []
    color_list = []

    for line, color in zip(lines, colors):
        first = line.upper_v if not swap else line.lower_v
        second = line.lower_v if not swap else line.upper_v

        vertices.extend(first[0].tolist())
        color_list.extend(color)
        vertices.extend(second[0].tolist())
        color_list.extend(color)
        vertices.extend(first[1].tolist())
        color_list.extend(color)
        vertices.extend(second[1].tolist())
        color_list.extend(color)

        if len(first) > len(second):
            vertices.extend(first[-1].tolist())
            swap = not swap
        elif len(second) > len(first):
            vertices.extend(second[-1].tolist())
            swap = not swap

    graphics.draw_triangle_strip(vertices, color_list)



def ln_intersection(l1, l2):
    return intersection(l1.start, l1.end, l2.start, l2.end)




