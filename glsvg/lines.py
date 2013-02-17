from OpenGL.GL import *
import math
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

    #draw points for start of line and end of line
    if debug:
        glPointSize(6)
        glBegin(GL_POINTS)
        if closed:
            glColor4f(1, 0, 1, 1)
        else:
            glColor4f(1, 0, 0, 1)
        glVertex2f(lines[0].upper_v[0].x, lines[0].upper_v[0].y)
        glVertex2f(lines[0].lower_v[0].x, lines[0].lower_v[0].y)
        glEnd()

        glPointSize(6)

    if colors:
        for line in lines:
            glBegin(GL_TRIANGLE_FAN)
            for v, c in zip(line.upper_v, colors):
                glColor4ub(*c)
                if debug: glColor4f(1, 0, 0, 1)
                glVertex2f(v.x, v.y)
            for v, c in reversed(zip(line.lower_v, colors)):
                glColor4ub(*c)
                if debug: glColor4f(0, 1, 0, 1)
                glVertex2f(v.x, v.y)
            glEnd()
    else:
        for line in lines:
            glBegin(GL_LINE_STRIP)
            for v in line.upper_v: glVertex2f(v.x, v.y)
            for v in reversed(line.lower_v): glVertex2f(v.x, v.y)
            glEnd()


def ln_intersection(l1, l2):
    return intersection(l1.start, l1.end, l2.start, l2.end)




