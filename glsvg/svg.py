"""GLSVG library for SVG rendering in PyOpenGL.

Example usage:
    >>> import glsvg
    >>> my_svg = glsvg.SVG('filename.svg')
    >>> my_svg.draw(100, 200, angle=15)
    
"""

from OpenGL.GL import *
from OpenGL.GL.ARB import *
from OpenGL.GLU import *

try:
    import xml.etree.ElementTree
    from xml.etree.cElementTree import parse
except:
    import elementtree.ElementTree
    from elementtree.ElementTree import parse

import re
import math
import sys
import string
import shader
import lines

from matrix import *
from parser_utils import *
from gradient import *

tess = gluNewTess()
gluTessNormal(tess, 0, 0, 1)
gluTessProperty(tess, GLU_TESS_WINDING_RULE, GLU_TESS_WINDING_NONZERO)

def set_tess_callback(which):
    def set_call(func):
        gluTessCallback(tess, which, func)
    return set_call
    
BEZIER_POINTS = 40
CIRCLE_POINTS = 24
TOLERANCE = 0.001

DEFAULT_FILL = [0, 0, 0, 255]
DEFAULT_STROKE = [0, 0, 0, 0]

#svg namespace
XMLNS = 'http://www.w3.org/2000/svg'

class _AttributeScope:
    def __init__(self, element, parent):
        self.parent = parent

        if parent:
            self.fill = parent.fill
            self.stroke = parent.stroke
        else:
            self.fill = DEFAULT_FILL
            self.stroke = DEFAULT_STROKE
        self.stroke_width = None
        self.transform = None
        self.opacity = 1.0

        self.fill = parse_color(element.get('fill'), self.fill)
        self.stroke = parse_color(element.get('stroke'), self.stroke)

        self.stroke_width = float(element.get('stroke-width', 1.0))

        self.fill_rule = 'nonzero'
        oldopacity = self.opacity
        self.opacity *= float(element.get('opacity', 1))
        fill_opacity = float(element.get('fill-opacity', 1))
        stroke_opacity = float(element.get('stroke-opacity', 1))
        self.path_id = element.get('id', '')
        self.path_title = element.findtext('{%s}title' % (XMLNS,))
        self.path_description = element.findtext('{%s}desc' % (XMLNS,))

        style = element.get('style')
        if style:
            sdict = parse_style(style)
            if 'fill' in sdict:
                self.fill = parse_color(sdict['fill'])
            if 'fill-opacity' in sdict:
                fill_opacity *= float(sdict['fill-opacity'])
            if 'stroke' in sdict:
                self.stroke = parse_color(sdict['stroke'])
            if 'stroke-opacity' in sdict:
                stroke_opacity *= float(sdict['stroke-opacity'])
            if 'stroke-width' in sdict:
                sw = sdict['stroke-width']
                self.stroke_width = parse_float(sw)
            if 'opacity' in sdict:
                fill_opacity *= float(sdict['opacity'])
                stroke_opacity *= float(sdict['opacity'])
            if 'fill-rule' in sdict:
                self.fill_rule = sdict['fill-rule']
        if isinstance(self.stroke, list):
            self.stroke[3] = int(self.opacity * stroke_opacity * self.stroke[3])
        if isinstance(self.fill, list):
            self.fill[3] = int(self.opacity * fill_opacity * self.fill[3])


class _SvgPath(object):
    def __init__(self, scope, path, polygon, transform):
        self.scope = scope
        self.fill = scope.fill
        self.stroke = scope.stroke
        self.stroke_width = scope.stroke_width
        self.path = list(path) if path else []
        self.polygon = polygon
        self.transform = Matrix(transform.values)
        self.id = scope.path_id
        self.title = scope.path_title
        self.description = scope.path_description

        
        
    def __repr__(self):
        return "<SvgPath id=%s title='%s' description='%s' transform=%s>" %(
            self.id, self.title, self.description, self.transform
        )

class _PathContext(object):
    def __init__(self):
        self.x = 0
        self.y = 0

class SVG(object):
    """
    Opaque SVG image object.
    
    Users should instantiate this object once for each SVG file they wish to 
    render.
    
    """
    
    _disp_list_cache = {}
    def __init__(self, filename, anchor_x=0, anchor_y=0, bezier_points=BEZIER_POINTS, circle_points=CIRCLE_POINTS, invert_y=False):
        """Creates an SVG object from a .svg or .svgz file.
        
            `filename`: str
                The name of the file to be loaded.
            `anchor_x`: float
                The horizontal anchor position for scaling and rotations. Defaults to 0. The symbolic 
                values 'left', 'center' and 'right' are also accepted.
            `anchor_y`: float
                The vertical anchor position for scaling and rotations. Defaults to 0. The symbolic 
                values 'bottom', 'center' and 'top' are also accepted.
            `bezier_points`: int
                The number of line segments into which to subdivide Bezier splines. Defaults to 10.
            `circle_points`: int
                The number of line segments into which to subdivide circular and elliptic arcs. 
                Defaults to 10.
                
        """
        self.path_lookup = {}
        self._paths = []
        self.invert_y = invert_y
        self.filename = filename
        self._n_bezier_points = bezier_points
        self._n_circle_points = circle_points
        self._bezier_coefficients = []
        self._gradients = GradientContainer()
        self._generate_disp_list()
        self._anchor_x = anchor_x
        self._anchor_y = anchor_y


    def _set_anchor_x(self, anchor_x):
        self._anchor_x = anchor_x
        if self._anchor_x == 'left':
            self._a_x = 0
        elif self._anchor_x == 'center':
            self._a_x = self.width * .5
        elif self._anchor_x == 'right':
            self._a_x = self.width
        else:
            self._a_x = self._anchor_x
    
    def _get_anchor_x(self):
        return self._anchor_x
    
    anchor_x = property(_get_anchor_x, _set_anchor_x)
    
    def _set_anchor_y(self, anchor_y):
        self._anchor_y = anchor_y
        if self._anchor_y == 'bottom':
            self._a_y = 0
        elif self._anchor_y == 'center':
            self._a_y = self.height * .5
        elif self._anchor_y == 'top':
            self._a_y = self.height
        else:
            self._a_y = self.anchor_y

    def _get_anchor_y(self):
        return self._anchor_y
        
    anchor_y = property(_get_anchor_y, _set_anchor_y)
    
    def _generate_disp_list(self):
        if (self.filename, self._n_bezier_points) in self._disp_list_cache:
            self.disp_list, self.width, self.height = self._disp_list_cache[self.filename, self._n_bezier_points]
        else:
            if open(self.filename, 'rb').read(3) == '\x1f\x8b\x08': #gzip magic numbers
                import gzip
                f = gzip.open(self.filename, 'rb')
            else:
                f = open(self.filename, 'rb')
            self.tree = parse(f)
            self._parse_doc()
            self.disp_list = glGenLists(1)
            glNewList(self.disp_list, GL_COMPILE)
            self.render()
            glEndList()
            self._disp_list_cache[self.filename, self._n_bezier_points] = (self.disp_list, self.width, self.height)

    def draw(self, x, y, z=0, angle=0, scale=1):
        """Draws the SVG to screen.
        
        :Parameters
            `x` : float
                The x-coordinate at which to draw.
            `y` : float
                The y-coordinate at which to draw.
            `z` : float
                The z-coordinate at which to draw. Defaults to 0. Note that z-ordering may not 
                give expected results when transparency is used.
            `angle` : float
                The angle by which the image should be rotated (in degrees). Defaults to 0.
            `scale` : float
                The amount by which the image should be scaled, either as a float, or a tuple 
                of two floats (xscale, yscale).

        """
        glPushMatrix()
        glTranslatef(x, y, z)
        if angle:
            glRotatef(angle, 0, 0, 1)
        if scale != 1:
            try:
                glScalef(scale[0], scale[1], 1)
            except TypeError:
                glScalef(scale, scale, 1)
        if self._a_x or self._a_y:  
            glTranslatef(-self._a_x, -self._a_y, 0)
        glCallList(self.disp_list)
        glPopMatrix()

    def render(self):
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self.n_tris = 0
        self.n_lines = 0
        for svgpath in self._paths:
            path = svgpath.path
            stroke = svgpath.stroke
            tris = svgpath.polygon
            fill = svgpath.fill
            stroke_width = svgpath.stroke_width
            transform = svgpath.transform
            if tris:
                self.n_tris += len(tris)/3
                g = None
                if isinstance(fill, str):
                    g = self._gradients[fill]
                    fills = [g.sample(x) for x in tris]
                else:
                    fills = [fill for x in tris]

                glPushMatrix()
                glMultMatrixf(transform.to_mat4())
                if g: g.apply_shader(transform)
                glBegin(GL_TRIANGLES)
                for vtx, clr in zip(tris, fills):
                    #vtx = transform(vtx)
                    if not g: glColor4ub(*clr)
                    else: glColor4f(1,1,1,1)
                    glVertex3f(vtx[0], vtx[1], 0)
                glEnd()
                glPopMatrix()
                if g: g.unapply_shader()
            if path:
                for loop in path:
                    self.n_lines += len(loop) - 1
                    loop_plus = []
                    for i in xrange(len(loop) - 1):
                        loop_plus += [loop[i], loop[i+1]]
                    if isinstance(stroke, str):
                        g = self._gradients[stroke]
                        strokes = [g.sample(x) for x in loop_plus]
                    else:
                        strokes = [stroke for x in loop_plus]

                    glPushMatrix()
                    glMultMatrixf(transform.to_mat4())
                    lines.draw_polyline(loop_plus, stroke_width, colors=strokes)
                    glPopMatrix()
                                     


    def _parse_doc(self):
        self._paths = []

        #get the height measurement... if it ends
        #with "cm" just sort of fake out some sort of
        #measurement (right now it adds a zero)
        wm = self.tree._root.get("width", '0')
        hm = self.tree._root.get("height", '0')
        if 'cm' in wm: wm = wm.replace('cm', '0')
        if 'cm' in hm: hm = hm.replace('cm', '0')

        self.width = parse_float(wm)
        self.height = parse_float(hm)

        if self.height:
            if self.invert_y:
                self.transform = Matrix([1, 0, 0, -1, 0, self.height])
            else:
                self.transform = Matrix([1, 0, 0, 1, 0, 0])
        elif self.tree._root.get("viewBox"):
            x, y, w, h = (parse_float(x) for x in parse_list(self.tree._root.get("viewBox")))
            if self.invert_y:
                self.transform = Matrix([1, 0, 0, -1, 0, 0])
            else:
                self.transform = Matrix([1, 0, 0, 1, 0, 0])
            self.height = h
            self.width = w
        else:
            #no height or width defined.. make something up
            self.height = 600
            self.width = 800
            self.transform = Matrix([1, 0, 0, 1, 0, 0])

        self.opacity = 1.0
        for e in self.tree._root.getchildren():
            try:
                self._parse_element(e)
            except Exception, ex:
                print 'Exception while parsing element', e
                raise

    def _is_path_tag(self, e): return e.tag.endswith('path')
    def _is_rect_tag(self, e): return e.tag.endswith('rect')

    def _parse_element(self, e, parent_scope=None):
        oldtransform = self.transform

        scope = _AttributeScope(e, parent_scope)

        self.scope = scope
        self.transform = self.transform * Matrix(e.get('transform'))

        if self._is_path_tag(e):
            pathdata = e.get('d', '')
            pathdata = re.findall("([A-Za-z]|-?[0-9]+\.?[0-9]*(?:e-?[0-9]*)?)", pathdata)
            def pnext():
                return (float(pathdata.pop(0)), float(pathdata.pop(0)))

            self._new_path()
            opcode = ''
            while pathdata:
                prev_opcode = opcode
                if pathdata[0] in string.letters:
                    opcode = pathdata.pop(0)
                else:
                    opcode = prev_opcode
                
                if opcode == 'M':
                    self._set_cursor_position(*pnext())
                elif opcode == 'm':
                    mx, my = pnext()
                    self._set_cursor_position(self.cursor_x + mx, self.cursor_y + my)
                elif opcode == 'Q': # absolute quadratic curve
                    self._quadratic_curve_to(*(pnext() + pnext()))
                elif opcode == 'q': # relative quadratic curve
                    ax, ay = pnext()
                    bx, by = pnext()
                    self._quadratic_curve_to(
                        ax + self.cursor_x, ay + self.cursor_y,
                        bx + self.cursor_x, by + self.cursor_y)

                elif opcode == 'T':
                    #quadratic curve with control point as reflection
                    mx = 2 * self.cursor_x - self.last_cx
                    my = 2 * self.cursor_y - self.last_cy
                    x,y = pnext()
                    self._quadratic_curve_to(mx, my, x, y)

                elif opcode == 't':
                    #relative quadratic curve with control point as reflection
                    mx = 2 * self.cursor_x - self.last_cx
                    my = 2 * self.cursor_y - self.last_cy
                    x,y = pnext()
                    self._quadratic_curve_to(mx+self.cursor_x, my+self.cursor_y, x+self.cursor_x, y+self.cursor_y)

                elif opcode == 'C':
                    self._curve_to(*(pnext() + pnext() + pnext()))
                elif opcode == 'c':
                    mx = self.cursor_x
                    my = self.cursor_y
                    x1, y1 = pnext()
                    x2, y2 = pnext()
                    x, y = pnext()
                    
                    self._curve_to(mx + x1, my + y1, mx + x2, my + y2, mx + x, my + y)
                elif opcode == 'S':
                    self._curve_to(2 * self.cursor_x - self.last_cx, 2 * self.cursor_y - self.last_cy, *(pnext() + pnext()))
                elif opcode == 's':
                    mx = self.cursor_x
                    my = self.cursor_y
                    x1, y1 = 2 * self.cursor_x - self.last_cx, 2 * self.cursor_y - self.last_cy
                    x2, y2 = pnext()
                    x, y = pnext()
                    
                    self._curve_to(x1, y1, mx + x2, my + y2, mx + x, my + y)
                elif opcode == 'A':
                    rx, ry = pnext()
                    phi = float(pathdata.pop(0))
                    large_arc = int(pathdata.pop(0))
                    sweep = int(pathdata.pop(0))
                    x, y = pnext()
                    self._arc_to(rx, ry, phi, large_arc, sweep, x, y)
                elif opcode == 'a': #relative arc
                    rx, ry = pnext()
                    phi = float(pathdata.pop(0))
                    large_arc = int(pathdata.pop(0))
                    sweep = int(pathdata.pop(0))
                    x, y = pnext()
                    self._arc_to( rx,  ry, phi, large_arc, sweep, self.cursor_x + x, self.cursor_y + y)
                elif opcode in 'zZ':
                    self._close_path()
                elif opcode == 'L':
                    self._line_to(*pnext())
                elif opcode == 'l':
                    x, y = pnext()
                    self._line_to(self.cursor_x + x, self.cursor_y + y)
                elif opcode == 'H':
                    x = float(pathdata.pop(0))
                    self._line_to(x, self.cursor_y)
                elif opcode == 'h':
                    x = float(pathdata.pop(0))
                    self._line_to(self.cursor_x + x, self.cursor_y)
                elif opcode == 'V':
                    y = float(pathdata.pop(0))
                    self._line_to(self.cursor_x, y)
                elif opcode == 'v':
                    y = float(pathdata.pop(0))
                    self._line_to(self.cursor_x, self.cursor_y + y)
                else:
                    self._warn("Unrecognised opcode: " + opcode)
                    raise Exception("Unrecognised opcode: " + opcode)
            self._end_path()
        elif self._is_rect_tag(e):
            x = float(e.get('x', 0))
            y = float(e.get('y', 0))
            h = float(e.get('height'))
            w = float(e.get('width'))
            self._new_path()
            self._set_cursor_position(x, y)
            self._line_to(x+w,y)
            self._line_to(x+w,y+h)
            self._line_to(x,y+h)
            self._line_to(x,y)
            self._end_path()
        elif e.tag.endswith('polyline') or e.tag.endswith('polygon'):
            pathdata = e.get('points')
            pathdata = re.findall("(-?[0-9]+\.?[0-9]*(?:e-?[0-9]*)?)", pathdata)
            def pnext():
                return (float(pathdata.pop(0)), float(pathdata.pop(0)))
            self._new_path()
            while pathdata:
                self._line_to(*pnext())
            if e.tag.endswith('polygon'):
                self._close_path()
            self._end_path()
        elif e.tag.endswith('line'):
            x1 = float(e.get('x1'))
            y1 = float(e.get('y1'))
            x2 = float(e.get('x2'))
            y2 = float(e.get('y2'))
            self._new_path()
            self._set_cursor_position(x1, y1)
            self._line_to(x2, y2)
            self._end_path()
        elif e.tag.endswith('circle'):
            cx = float(e.get('cx'))
            cy = float(e.get('cy'))
            r = float(e.get('r'))
            self._new_path()
            for i in xrange(self._n_circle_points):
                theta = 2 * i * math.pi / self._n_circle_points
                self._line_to(cx + r * math.cos(theta), cy + r * math.sin(theta))
            self._close_path()
            self._end_path()
        elif e.tag.endswith('ellipse'):
            cx = float(e.get('cx'))
            cy = float(e.get('cy'))
            rx = float(e.get('rx'))
            ry = float(e.get('ry'))
            self._new_path()
            for i in xrange(self._n_circle_points):
                theta = 2 * i * math.pi / self._n_circle_points
                self._line_to(cx + rx * math.cos(theta), cy + ry * math.sin(theta))
            self._close_path()
            self._end_path()
        elif e.tag.endswith("text"):
            self._warn("Text tag not supported")
        elif e.tag.endswith('linearGradient'):
            self._gradients[e.get('id')] = LinearGradient(e, self)
        elif e.tag.endswith('radialGradient'):
            self._gradients[e.get('id')] = RadialGradient(e, self)
        for c in e.getchildren():
            try:
                self._parse_element(c, scope)
            except Exception, ex:
                print 'Exception while parsing element', c
                raise
        self.transform = oldtransform

    def _new_path(self):
        self.cursor_x = 0
        self.cursor_y = 0
        self.close_index = 0
        self.path = []
        self.loop = []

    def _close_path(self):
        self.loop.append(self.loop[0][:])
        self.path.append(self.loop)
        self.loop = []
        
    def _set_cursor_position(self, x, y):
        self.cursor_x = x
        self.cursor_y = y
        self.loop.append([x,y])
    
    def _arc_to(self, rx, ry, phi, large_arc, sweep, x, y):
        # This function is made out of magical fairy dust
        # http://www.w3.org/TR/2003/REC-SVG11-20030114/implnote.html#ArcImplementationNotes
        x1 = self.cursor_x
        y1 = self.cursor_y
        x2 = x
        y2 = y
        cp = math.cos(phi)
        sp = math.sin(phi)
        dx = .5 * (x1 - x2)
        dy = .5 * (y1 - y2)
        x_ = cp * dx + sp * dy
        y_ = -sp * dx + cp * dy
        r2 = (((rx * ry)**2 - (rx * y_)**2 - (ry * x_)**2)/
             ((rx * y_)**2 + (ry * x_)**2))
        if r2 < 0: r2 = 0
        r = math.sqrt(r2)
        if large_arc == sweep:
            r = -r
        cx_ = r * rx * y_ / ry
        cy_ = -r * ry * x_ / rx
        cx = cp * cx_ - sp * cy_ + .5 * (x1 + x2)
        cy = sp * cx_ + cp * cy_ + .5 * (y1 + y2)
        def angle(u, v):
            a = math.acos((u[0]*v[0] + u[1]*v[1]) / math.sqrt((u[0]**2 + u[1]**2) * (v[0]**2 + v[1]**2)))
            sgn = 1 if u[0]*v[1] > u[1]*v[0] else -1
            return sgn * a
        
        psi = angle((1,0), ((x_ - cx_)/rx, (y_ - cy_)/ry))
        delta = angle(((x_ - cx_)/rx, (y_ - cy_)/ry), 
                      ((-x_ - cx_)/rx, (-y_ - cy_)/ry))
        if sweep and delta < 0: delta += math.pi * 2
        if not sweep and delta > 0: delta -= math.pi * 2
        n_points = max(int(abs(self._n_circle_points * delta / (2 * math.pi))), 1)
        
        for i in xrange(n_points + 1):
            theta = psi + i * delta / n_points
            ct = math.cos(theta)
            st = math.sin(theta)
            self._line_to(cp * rx * ct - sp * ry * st + cx,
                         sp * rx * ct + cp * ry * st + cy)


    def _quadratic_curve_to(self, x1, y1, x2, y2):
        x0 = self.cursor_x
        y0 = self.cursor_y

        for i in xrange(self._n_bezier_points+1):
            t = float(i)/self._n_bezier_points
            q0x = (x1 - x0)*t + x0
            q0y = (y1 - y0)*t + y0

            q1x = (x2 - x1)*t + x1
            q1y = (y2 - y1)*t + y1

            bx = (q1x-q0x)*t + q0x
            by = (q1y-q0y)*t + q0y

            self.loop.append([bx, by])

        self.last_cx = x1
        self.last_cy = y1

        self.cursor_x, self.cursor_y = x2, y2

    def _curve_to(self, x1, y1, x2, y2, x, y):
        if not self._bezier_coefficients:
            for i in xrange(self._n_bezier_points+1):
                t = float(i)/self._n_bezier_points
                t0 = (1 - t) ** 3
                t1 = 3 * t * (1 - t) ** 2
                t2 = 3 * t ** 2 * (1 - t)
                t3 = t ** 3
                self._bezier_coefficients.append([t0, t1, t2, t3])
        self.last_cx = x2
        self.last_cy = y2
        for i, t in enumerate(self._bezier_coefficients):
            px = t[0] * self.cursor_x + t[1] * x1 + t[2] * x2 + t[3] * x
            py = t[0] * self.cursor_y + t[1] * y1 + t[2] * y2 + t[3] * y
            self.loop.append([px, py])

        self.cursor_x, self.cursor_y = px, py

    def _line_to(self, x, y):
        self._set_cursor_position(x, y)

    def _end_path(self):
        self.path.append(self.loop)
        if self.path:
            path = []
            for orig_loop in self.path:
                if not orig_loop: continue
                loop = [orig_loop[0]]
                for pt in orig_loop:
                    if (pt[0] - loop[-1][0])**2 + (pt[1] - loop[-1][1])**2 > TOLERANCE:
                        loop.append(pt)
                path.append(loop)
            path_object = _SvgPath(self.scope,
                               path if self.scope.stroke else None,
                               self._triangulate(path) if self.scope.fill else None,
                               self.transform)
            self._paths.append(path_object)
            self.path_lookup[self.scope.path_id] = path_object
        self.path = []

    def _triangulate(self, looplist):
        tlist = []
        self.curr_shape = []
        spareverts = []

        @set_tess_callback(GLU_TESS_VERTEX)
        def vertexCallback(vertex):
            self.curr_shape.append(list(vertex[0:2]))

        @set_tess_callback(GLU_TESS_BEGIN)
        def beginCallback(which):
            self.tess_style = which

        @set_tess_callback(GLU_TESS_END)
        def endCallback():
            if self.tess_style == GL_TRIANGLE_FAN:
                c = self.curr_shape.pop(0)
                p1 = self.curr_shape.pop(0)
                while self.curr_shape:
                    p2 = self.curr_shape.pop(0)
                    tlist.extend([c, p1, p2])
                    p1 = p2
            elif self.tess_style == GL_TRIANGLE_STRIP:
                p1 = self.curr_shape.pop(0)
                p2 = self.curr_shape.pop(0)
                while self.curr_shape:
                    p3 = self.curr_shape.pop(0)
                    tlist.extend([p1, p2, p3])
                    p1 = p2
                    p2 = p3
            elif self.tess_style == GL_TRIANGLES:
                tlist.extend(self.curr_shape)
            else:
                self._warn("Unrecognised tesselation style: %d" % (self.tess_style,))
            self.tess_style = None
            self.curr_shape = []

        @set_tess_callback(GLU_TESS_ERROR)
        def errorCallback(code):
            ptr = gluErrorString(code)
            err = ''
            idx = 0
            while ptr[idx]: 
                err += chr(ptr[idx])
                idx += 1
            self._warn("GLU Tesselation Error: " + err)

        @set_tess_callback(GLU_TESS_COMBINE)
        def combineCallback(coords, vertex_data, weights):
            x, y, z = coords[0:3]
            dataOut = (x,y,z)
            spareverts.append((x,y,z))
            return dataOut
        
        data_lists = []
        for vlist in looplist:
            d_list = []
            for x, y in vlist:
                v_data = (GLdouble * 3)(x, y, 0)
                d_list.append(v_data)
            data_lists.append(d_list)

        if self.scope.fill_rule == 'nonzero':
            gluTessProperty(tess, GLU_TESS_WINDING_RULE, GLU_TESS_WINDING_NONZERO)
        elif self.scope.fill_rule == 'evenodd':
            gluTessProperty(tess, GLU_TESS_WINDING_RULE, GLU_TESS_WINDING_ODD)

        gluTessBeginPolygon(tess, None)
        for d_list in data_lists:    
            gluTessBeginContour(tess)
            for v_data in d_list:
                gluTessVertex(tess, v_data, v_data)
            gluTessEndContour(tess)
        gluTessEndPolygon(tess)
        return tlist       

    def _warn(self, message):
        print "Warning: SVG Parser (%s) - %s" % (self.filename, message)
