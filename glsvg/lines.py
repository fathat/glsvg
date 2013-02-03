from OpenGL.GL import *
import math

ep = 0.001

class vec2(object):
    def __init__(self, *args):
        if isinstance(args[0], vec2):
            self.x = args[0].x
            self.y = args[0].y
        elif isinstance(args[0], list):
            self.x, self.y = args[0]
        else:
            self.x, self.y = args[0], args[1]

    def __repr__(self):
        return '(' + str(self.x) + ',' + str(self.y) + ')'

    def __neg__(self):
        return vec2(-self.x, -self.y)

    def __abs__(self):
        return self.length()

    def __add__(self, other):
        return vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return vec2(self.x - other.x, self.y - other.y)

    def __mul__(self, scale):
        return vec2(self.x * scale, self.y * scale)

    def __div__(self, scale):
        return vec2(self.x / scale, self.y / scale)

    def __eq__(self, other):
        return abs(self.x-other.x) < ep and abs(self.y-other.y) < ep

    def __ne__(self, other): return not(self.__eq__(other))

    def normalized(self):
        l = self.length()
        if l == 0:
            return vec2(1, 0)
        else:
            return vec2(self.x, self.y) / self.length()

    def length(self):
        return math.sqrt((self.x)**2 + (self.y)**2)

def line_length(a, b): return math.sqrt((b.x-a.x)**2 + (b.y-a.y)**2)

def radian(deg): return deg * (math.pi/180.0)

ninety_degrees = radian(90)

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
        hw = self.w*0.5
        self.up_normal = vec2(math.cos(angle - radian(90))*hw,
                              math.sin(angle - radian(90))*hw)
        self.dn_normal = vec2(math.cos(angle + radian(90))*hw,
                              math.sin(angle + radian(90))*hw)


def _process_joint(ln, pln, miter_limit):
    up_intersection, ln.upper_join = ln_intersection(pln.upper_edge, ln.upper_edge)
    lo_intersection, ln.lower_join = ln_intersection(pln.lower_edge, ln.lower_edge)

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
    #if points[0] == points[-1]: closed = True

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

def draw_polyline(points, w, colors=None, miter_limit=4, closed=False):
    if len(points) == 0:
        return
    lines = calc_polyline(points, w, miter_limit, closed)

    if colors:
        for line in lines:
            glBegin(GL_TRIANGLE_FAN)
            for v, c in zip(line.upper_v, colors):
                glColor4ub(*c)
                glVertex2f(v.x, v.y)
            for v, c in reversed(zip(line.lower_v, colors)):
                glColor4ub(*c)
                glVertex2f(v.x, v.y)
            glEnd()
    else:
        for line in lines:
            glBegin(GL_TRIANGLE_FAN)
            for v in line.upper_v: glVertex2f(v.x, v.y)
            for v in reversed(line.lower_v): glVertex2f(v.x, v.y)
            glEnd()

def ln_intersection(l1, l2):
    return intersection(l1.start, l1.end, l2.start, l2.end)

def intersection(p1, p2, p3, p4):
    A1 = p2.y-p1.y
    B1 = p1.x-p2.x
    C1 = A1*p1.x+B1*p1.y

    A2 = p4.y-p3.y
    B2 = p3.x-p4.x
    C2 = A2*p3.x+B2*p3.y

    det = A1*B2 - A2*B1

    if det == 0: #Lines are parallel
        return False, vec2(0,0)
    else:
        result =  vec2(
            (B2*C1 - B1*C2)/det,
            (A1*C2 - A2*C1)/det)

    epsilon = .01

    on_line_segment = True
    on_line_segment &= result.x >= (min(p1.x, p2.x)-epsilon)
    on_line_segment &= result.y >= (min(p1.y, p2.y)-epsilon)
    on_line_segment &= result.x <= (max(p1.x, p2.x)+epsilon)
    on_line_segment &= result.y <= (max(p1.y, p2.y)+epsilon)

    return on_line_segment, result



