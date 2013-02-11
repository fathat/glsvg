"""GLSVG library for SVG rendering in PyOpenGL.

Example usage:
    $ import glsvg
    $ my_svg = glsvg.SVG('filename.svg')
    $ my_svg.draw(100, 200, angle=15)
    
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
import string
import lines
import traceback

import render_target

from glutils import *
from matrix import *
from parser_utils import parse_color, parse_float, parse_style, parse_list
from gradient import *


BEZIER_POINTS = 40
CIRCLE_POINTS = 24
TOLERANCE = 0.001

DEFAULT_FILL = [0, 0, 0, 255]
DEFAULT_STROKE = [0, 0, 0, 0]

PATTERN_TEX_SIZE = 1024

#svg namespace
XMLNS = 'http://www.w3.org/2000/svg'


class _AttributeScope:
    def __init__(self, element, parent):
        self.parent = parent
        self.is_pattern = element.tag.endswith("pattern")
        self.is_pattern_part = False

        if parent:
            self.fill = parent.fill
            self.stroke = parent.stroke

            if parent.is_pattern:
                self.is_pattern_part = True
        else:
            self.fill = DEFAULT_FILL
            self.stroke = DEFAULT_STROKE
        self.stroke_width = None

        if parent:
            self.transform = parent.transform * Matrix(element.get('transform'))
        else:
            self.transform = Matrix(element.get('transform', None))

            if not self.transform:
                self.transform = Matrix([1, 0, 0, 1, 0, 0])

        self.opacity = 1.0

        self.tag_type = element.tag

        self.fill = parse_color(element.get('fill'), self.fill)
        self.fill_rule = 'nonzero'

        self.stroke = parse_color(element.get('stroke'), self.stroke)
        self.stroke_width = float(element.get('stroke-width', 1.0))

        self.opacity *= float(element.get('opacity', 1))
        fill_opacity = float(element.get('fill-opacity', 1))
        stroke_opacity = float(element.get('stroke-opacity', 1))
        self.path_id = element.get('id', '')
        self.path_title = element.findtext('{%s}title' % (XMLNS,))
        self.path_description = element.findtext('{%s}desc' % (XMLNS,))

        style = element.get('style')
        if style:
            style_dict = parse_style(style)
            if 'fill' in style_dict:
                self.fill = parse_color(style_dict['fill'])
            if 'fill-opacity' in style_dict:
                fill_opacity *= float(style_dict['fill-opacity'])
            if 'stroke' in style_dict:
                self.stroke = parse_color(style_dict['stroke'])
            if 'stroke-opacity' in style_dict:
                stroke_opacity *= float(style_dict['stroke-opacity'])
            if 'stroke-width' in style_dict:
                sw = style_dict['stroke-width']
                self.stroke_width = parse_float(sw)
            if 'opacity' in style_dict:
                fill_opacity *= float(style_dict['opacity'])
                stroke_opacity *= float(style_dict['opacity'])
            if 'fill-rule' in style_dict:
                self.fill_rule = style_dict['fill-rule']
        if isinstance(self.stroke, list):
            self.stroke[3] = int(self.opacity * stroke_opacity * self.stroke[3])
        if isinstance(self.fill, list):
            self.fill[3] = int(self.opacity * fill_opacity * self.fill[3])


class SvgPath(object):
    """

    """

    def __init__(self, svg, scope, path, polygon):
        self.svg = svg
        self.scope = scope
        self.transform = scope.transform
        self.fill = scope.fill
        self.stroke = scope.stroke
        self.stroke_width = scope.stroke_width
        self.path = list(path) if path else []
        self.polygon = polygon
        self.id = scope.path_id
        self.title = scope.path_title
        self.description = scope.path_description
        self.shape = None
        self.is_pattern = scope.is_pattern
        self.is_pattern_part = scope.is_pattern_part

        if self.is_pattern_part:
            svg.register_pattern_part(scope.parent.path_id, self)

    def render_stroke(self):
        stroke = self.stroke
        stroke_width = self.stroke_width
        for loop in self.path:
            self.svg.n_lines += len(loop) - 1
            loop_plus = []
            for i in xrange(len(loop) - 1):
                loop_plus += [loop[i], loop[i+1]]
            if isinstance(stroke, str):
                g = self._gradients[stroke]
                strokes = [g.sample(x) for x in loop_plus]
            else:
                strokes = [stroke for x in loop_plus]
            lines.draw_polyline(loop_plus, stroke_width, colors=strokes)

    def render_stroke_stencil(self):
        stroke_width = self.stroke_width
        for loop in self.path:
            loop_plus = []
            for i in xrange(len(loop) - 1):
                loop_plus += [loop[i], loop[i+1]]
            lines.draw_polyline(loop_plus, stroke_width)

    def render_gradient_fill(self):
        fill = self.fill
        tris = self.polygon
        self.svg.n_tris += len(tris)/3
        g = None
        if isinstance(fill, str):
            g = self.svg._gradients[fill]
            fills = [g.sample(x) for x in tris]
        else:
            fills = [fill] * len(tris)  # for x in tris]

        if g:
            g.apply_shader(self.transform)

        glBegin(GL_TRIANGLES)
        for vtx, clr in zip(tris, fills):
            if not g:
                glColor4ub(*clr)
            else:
                glColor4f(1, 1, 1, 1)
            glVertex3f(vtx[0], vtx[1], 0)
        glEnd()

        if g:
            g.unapply_shader()

    def render_pattern_fill(self):
        fill = self.fill
        tris = self.polygon
        pattern = None
        if fill in self.svg.patterns:
            pattern = self.svg.patterns[fill]
            glEnable(GL_TEXTURE_2D)
            pattern.bind_texture()

        glBegin(GL_TRIANGLES)
        for vtx in tris:
            glColor4f(1, 1, 1, 1)
            glTexCoord2f(vtx[0]/20.0, vtx[1]/20.0)
            glVertex3f(vtx[0], vtx[1], 0)
        glEnd()

        if not pattern:
            pattern.unbind_texture()

        glDisable(GL_TEXTURE_2D)

    def render(self):
        with self.transform:
            if self.polygon:
                try:
                    #if stencil is on
                    if self.svg.is_stencil_enabled():
                        glEnable(GL_STENCIL_TEST)
                        mask = self.svg.next_stencil_mask()
                        glStencilFunc(GL_NEVER, mask, 0xFF);
                        glStencilOp(GL_REPLACE, GL_KEEP, GL_KEEP);  # draw mask id on test fail (always)
                        glStencilMask(mask)
                        self.render_stroke_stencil()

                        #draw where stencil hasn't masked out
                        glStencilFunc(GL_NOTEQUAL, mask, 0xFF)

                    #stencil fill
                    if isinstance(self.fill, str) and self.fill in self.svg.patterns:
                        self.render_pattern_fill()
                    else:
                        self.render_gradient_fill()

                except Exception as exception:
                    traceback.print_exc(exception)
                finally:
                    if self.svg.is_stencil_enabled():
                        glDisable(GL_STENCIL_TEST)
            if self.path:
                self.render_stroke()
        
    def __repr__(self):
        return "<SvgPath id=%s title='%s' description='%s' transform=%s>" % (
            self.id, self.title, self.description, self.transform
        )


class Pattern(object):

    def __init__(self, element, svg):
        self.svg = svg
        self.id = element.get('id')
        self.units = element.get('patternContentUnits', 'objectBoundingBox')
        self.width = parse_float(element.get('width', '1.0'))
        self.height = parse_float(element.get('height', '1.0'))
        self.render_texture = None
        self.paths = []

    def bind_texture(self):
        if not self.render_texture: return
        self.render_texture.texture.bind()

    def unbind_texture(self):
        if not self.render_texture: return
        self.render_texture.texture.unbind()

    def render(self):
        self.render_texture = render_target.RenderTarget(PATTERN_TEX_SIZE, PATTERN_TEX_SIZE)

        self.render_texture.bind()

        #setup projection matrix..

        viewport = list(glGetFloatv(GL_VIEWPORT))

        print "viewport", viewport
        glViewport(0, 0, PATTERN_TEX_SIZE, PATTERN_TEX_SIZE)
        glMatrixMode(GL_PROJECTION)
        glPushMatrix();
        glLoadIdentity();
        glOrtho(0, self.width, 0, self.height, 0, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        glClearColor(0.0, 0.5, 1.0, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        for path in self.paths:
            print "path: ", str(path)
            path.render()
        glMatrixMode(GL_PROJECTION)

        glPopMatrix()
        glViewport(int(viewport[0]), int(viewport[1]), int(viewport[2]), int(viewport[3]))
        glMatrixMode(GL_MODELVIEW)

        self.render_texture.unbind()



class SVG(object):
    """
    Opaque SVG image object.
    
    Users should instantiate this object once for each SVG file they wish to 
    render.
    
    """

    def __init__(self, filename, anchor_x=0, anchor_y=0, bezier_points=BEZIER_POINTS, circle_points=CIRCLE_POINTS, allow_stencil=True):
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
        self.stencil_bits = glGetInteger(GL_STENCIL_BITS)
        self.stencil_mask = 0
        self.n_tris = 0
        self.n_lines = 0
        self.path_lookup = {}
        self._paths = []
        self.patterns = {}
        self.allow_stencil = allow_stencil
        self.filename = filename
        self._n_bezier_points = bezier_points
        self._n_circle_points = circle_points
        self._bezier_coefficients = []
        self._gradients = GradientContainer()
        self._generate_disp_list()
        self._anchor_x = anchor_x
        self._anchor_y = anchor_y

    def next_stencil_mask(self):
        self.stencil_mask += 1

        # if we run out of unique bits in stencil buffer,
        # clear stencils and restart
        if self.stencil_mask > (2**self.stencil_bits-1):
            self.stencil_mask = 1
            glStencilMask(0xFF)
            glClear(GL_STENCIL_BUFFER_BIT)

        return self.stencil_mask

    def is_stencil_enabled(self):
        return self.stencil_bits > 0 and self.allow_stencil

    def register_pattern_part(self, pattern_id, pattern_svg_path):
        print "registering pattern"
        self.patterns[pattern_id].paths.append(pattern_svg_path)

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
        if open(self.filename, 'rb').read(3) == '\x1f\x8b\x08':  # gzip magic numbers
            import gzip
            f = gzip.open(self.filename, 'rb')
        else:
            f = open(self.filename, 'rb')
        self.tree = parse(f)
        self._parse_doc()

        # prepare all the patterns
        self.render_patterns()

        with DisplayListGenerator() as display_list:
            self.disp_list = display_list
            self.render()



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

        with CurrentTransform():
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

            self.disp_list()

    def render_patterns(self):
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        #clear out stencils
        if self.is_stencil_enabled():
            glStencilMask(0xFF)
            glClear(GL_STENCIL_BUFFER_BIT)

        print "preparing patterns"
        print self.patterns
        for pattern in self.patterns.values():
            print "rendering", pattern
            pattern.render()

    def render(self):
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        #clear out stencils
        if self.is_stencil_enabled():
            glStencilMask(0xFF)
            glClear(GL_STENCIL_BUFFER_BIT)
        for svg_path in self._paths:
            if not svg_path.is_pattern and not svg_path.is_pattern_part:
                svg_path.render()

    def _parse_doc(self):
        self._paths = []

        #get the height measurement... if it ends
        #with "cm" just sort of fake out some sort of
        #measurement (right now it adds a zero)
        wm = self.tree._root.get("width", '0')
        hm = self.tree._root.get("height", '0')
        if 'cm' in wm:
            wm = wm.replace('cm', '0')
        if 'cm' in hm:
            hm = hm.replace('cm', '0')

        self.width = parse_float(wm)
        self.height = parse_float(hm)
        #self.transform = Matrix([1, 0, 0, 1, 0, 0])

        if self.tree._root.get("viewBox"):
            x, y, w, h = (parse_float(x) for x in parse_list(self.tree._root.get("viewBox")))
            self.height = h
            self.width = w

        self.opacity = 1.0
        for e in self.tree._root.getchildren():
            try:
                self._parse_element(e)
            except Exception as ex:
                print 'Exception while parsing element', e
                raise

    def _is_path_tag(self, e):
        return e.tag.endswith('path')

    def _is_rect_tag(self, e):
        return e.tag.endswith('rect')

    def _parse_element(self, e, parent_scope=None):
        scope = _AttributeScope(e, parent_scope)

        #self.scope = scope
        #self.transform = self.transform * Matrix(e.get('transform'))

        if self._is_path_tag(e):
            path_data = e.get('d', '')
            path_data = re.findall("([A-Za-z]|-?[0-9]+\.?[0-9]*(?:e-?[0-9]*)?)", path_data)

            def next_point():
                return float(path_data.pop(0)), float(path_data.pop(0))

            self._new_path()
            opcode = ''
            while path_data:
                prev_opcode = opcode
                if path_data[0] in string.letters:
                    opcode = path_data.pop(0)
                else:
                    opcode = prev_opcode
                
                if opcode == 'M':
                    self._set_cursor_position(*next_point())
                elif opcode == 'm':
                    mx, my = next_point()
                    self._set_cursor_position(self.ctx_cursor_x + mx, self.ctx_cursor_y + my)
                elif opcode == 'Q':  # absolute quadratic curve
                    self._quadratic_curve_to(*(next_point() + next_point()))
                elif opcode == 'q':  # relative quadratic curve
                    ax, ay = next_point()
                    bx, by = next_point()
                    self._quadratic_curve_to(
                        ax + self.ctx_cursor_x, ay + self.ctx_cursor_y,
                        bx + self.ctx_cursor_x, by + self.ctx_cursor_y)

                elif opcode == 'T':
                    # quadratic curve with control point as reflection
                    mx = 2 * self.ctx_cursor_x - self.last_cx
                    my = 2 * self.ctx_cursor_y - self.last_cy
                    x,y = next_point()
                    self._quadratic_curve_to(mx, my, x, y)

                elif opcode == 't':
                    # relative quadratic curve with control point as reflection
                    mx = 2 * self.ctx_cursor_x - self.last_cx
                    my = 2 * self.ctx_cursor_y - self.last_cy
                    x,y = next_point()
                    self._quadratic_curve_to(
                        mx + self.ctx_cursor_x,
                        my + self.ctx_cursor_y,
                        x + self.ctx_cursor_x,
                        y + self.ctx_cursor_y)

                elif opcode == 'C':
                    self._curve_to(*(next_point() + next_point() + next_point()))
                elif opcode == 'c':
                    mx, my = self.ctx_cursor_x, self.ctx_cursor_y
                    x1, y1 = next_point()
                    x2, y2 = next_point()
                    x, y = next_point()
                    
                    self._curve_to(mx + x1, my + y1, mx + x2, my + y2, mx + x, my + y)
                elif opcode == 'S':
                    self._curve_to(2 * self.ctx_cursor_x - self.last_cx, 2 * self.ctx_cursor_y - self.last_cy,
                                   *(next_point() + next_point()))
                elif opcode == 's':
                    mx = self.ctx_cursor_x
                    my = self.ctx_cursor_y
                    x1, y1 = 2 * self.ctx_cursor_x - self.last_cx, 2 * self.ctx_cursor_y - self.last_cy
                    x2, y2 = next_point()
                    x, y = next_point()
                    
                    self._curve_to(x1, y1, mx + x2, my + y2, mx + x, my + y)
                elif opcode == 'A':
                    rx, ry = next_point()
                    phi = float(path_data.pop(0))
                    large_arc = int(path_data.pop(0))
                    sweep = int(path_data.pop(0))
                    x, y = next_point()
                    self._arc_to(rx, ry, phi, large_arc, sweep, x, y)
                elif opcode == 'a':  # relative arc
                    rx, ry = next_point()
                    phi = float(path_data.pop(0))
                    large_arc = int(path_data.pop(0))
                    sweep = int(path_data.pop(0))
                    x, y = next_point()
                    self._arc_to(rx,  ry, phi, large_arc, sweep, self.ctx_cursor_x + x, self.ctx_cursor_y + y)
                elif opcode in 'zZ':
                    self._close_path()
                elif opcode == 'L':
                    self._line_to(*next_point())
                elif opcode == 'l':
                    x, y = next_point()
                    self._line_to(self.ctx_cursor_x + x, self.ctx_cursor_y + y)
                elif opcode == 'H':
                    x = float(path_data.pop(0))
                    self._line_to(x, self.ctx_cursor_y)
                elif opcode == 'h':
                    x = float(path_data.pop(0))
                    self._line_to(self.ctx_cursor_x + x, self.ctx_cursor_y)
                elif opcode == 'V':
                    y = float(path_data.pop(0))
                    self._line_to(self.ctx_cursor_x, y)
                elif opcode == 'v':
                    y = float(path_data.pop(0))
                    self._line_to(self.ctx_cursor_x, self.ctx_cursor_y + y)
                else:
                    self._warn("Unrecognised opcode: " + opcode)
                    raise Exception("Unrecognised opcode: " + opcode)
            self._end_path(scope)
        elif self._is_rect_tag(e):
            x = float(e.get('x', 0))
            y = float(e.get('y', 0))
            h = float(e.get('height'))
            w = float(e.get('width'))
            self._new_path()
            self._set_cursor_position(x, y)
            self._line_to(x + w, y)
            self._line_to(x + w, y + h)
            self._line_to(x, y + h)
            self._line_to(x, y)
            self._end_path(scope)
        elif e.tag.endswith('polyline') or e.tag.endswith('polygon'):
            path_data = e.get('points')
            path_data = re.findall("(-?[0-9]+\.?[0-9]*(?:e-?[0-9]*)?)", path_data)

            def next_point():
                return float(path_data.pop(0)), float(path_data.pop(0))

            self._new_path()
            while path_data:
                self._line_to(*next_point())
            if e.tag.endswith('polygon'):
                self._close_path()
            self._end_path(scope)
        elif e.tag.endswith('line'):
            x1 = float(e.get('x1'))
            y1 = float(e.get('y1'))
            x2 = float(e.get('x2'))
            y2 = float(e.get('y2'))
            self._new_path()
            self._set_cursor_position(x1, y1)
            self._line_to(x2, y2)
            self._end_path(scope)
        elif e.tag.endswith('circle'):
            cx = float(e.get('cx'))
            cy = float(e.get('cy'))
            r = float(e.get('r'))
            self._new_path()
            for i in xrange(self._n_circle_points):
                theta = 2 * i * math.pi / self._n_circle_points
                self._line_to(cx + r * math.cos(theta), cy + r * math.sin(theta))
            self._close_path()
            self._end_path(scope)
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
            self._end_path(scope)
        elif e.tag.endswith("text"):
            self._warn("Text tag not supported")
        elif e.tag.endswith('linearGradient'):
            self._gradients[e.get('id')] = LinearGradient(e, self)
        elif e.tag.endswith('radialGradient'):
            self._gradients[e.get('id')] = RadialGradient(e, self)
        elif e.tag.endswith('pattern'):
            self.patterns[e.get('id')] = Pattern(e, self)
        for c in e.getchildren():
            try:
                self._parse_element(c, scope)
            except Exception, ex:
                print 'Exception while parsing element', c
                raise
        #self.transform = old_transform

    def _new_path(self):
        self.ctx_cursor_x = 0
        self.ctx_cursor_y = 0
        self.close_index = 0
        self.ctx_path = []
        self.ctx_loop = []

    def _close_path(self):
        self.ctx_loop.append(self.ctx_loop[0][:])
        self.ctx_path.append(self.ctx_loop)
        self.ctx_loop = []
        
    def _set_cursor_position(self, x, y):
        self.ctx_cursor_x = x
        self.ctx_cursor_y = y
        self.ctx_loop.append([x,y])
    
    def _arc_to(self, rx, ry, phi, large_arc, sweep, x, y):
        # This function is made out of magical fairy dust
        # http://www.w3.org/TR/2003/REC-SVG11-20030114/implnote.html#ArcImplementationNotes
        x1 = self.ctx_cursor_x
        y1 = self.ctx_cursor_y
        x2 = x
        y2 = y
        cp = math.cos(phi)
        sp = math.sin(phi)
        dx = .5 * (x1 - x2)
        dy = .5 * (y1 - y2)
        x_ = cp * dx + sp * dy
        y_ = -sp * dx + cp * dy
        r2 = (((rx * ry) ** 2 - (rx * y_) ** 2 - (ry * x_) ** 2) /
             ((rx * y_) ** 2 + (ry * x_) ** 2))
        if r2 < 0: r2 = 0
        r = math.sqrt(r2)
        if large_arc == sweep:
            r = -r
        cx_ = r * rx * y_ / ry
        cy_ = -r * ry * x_ / rx
        cx = cp * cx_ - sp * cy_ + .5 * (x1 + x2)
        cy = sp * cx_ + cp * cy_ + .5 * (y1 + y2)

        def angle(u, v):
            a = math.acos((u[0] * v[0] + u[1] * v[1]) / math.sqrt((u[0] ** 2 + u[1] ** 2) * (v[0] ** 2 + v[1] ** 2)))
            sgn = 1 if u[0] * v[1] > u[1] * v[0] else -1
            return sgn * a
        
        psi = angle((1, 0), ((x_ - cx_) / rx, (y_ - cy_) / ry))
        delta = angle(((x_ - cx_) / rx, (y_ - cy_) / ry),
                      ((-x_ - cx_) / rx, (-y_ - cy_) / ry))
        if sweep and delta < 0:
            delta += math.pi * 2
        if not sweep and delta > 0:
            delta -= math.pi * 2
        n_points = max(int(abs(self._n_circle_points * delta / (2 * math.pi))), 1)
        
        for i in xrange(n_points + 1):
            theta = psi + i * delta / n_points
            ct = math.cos(theta)
            st = math.sin(theta)
            self._line_to(cp * rx * ct - sp * ry * st + cx,
                          sp * rx * ct + cp * ry * st + cy)

    def _quadratic_curve_to(self, x1, y1, x2, y2):
        x0, y0 = self.ctx_cursor_x, self.ctx_cursor_y

        for i in xrange(self._n_bezier_points+1):
            t = float(i) / self._n_bezier_points
            q0x = (x1 - x0) * t + x0
            q0y = (y1 - y0) * t + y0

            q1x = (x2 - x1) * t + x1
            q1y = (y2 - y1) * t + y1

            bx = (q1x-q0x) * t + q0x
            by = (q1y-q0y) * t + q0y

            self.ctx_loop.append([bx, by])

        self.last_cx, self.last_cy = x1, y1
        self.ctx_cursor_x, self.ctx_cursor_y = x2, y2

    def _curve_to(self, x1, y1, x2, y2, x, y):
        if not self._bezier_coefficients:
            for i in xrange(self._n_bezier_points + 1):
                t = float(i) / self._n_bezier_points
                t0 = (1 - t) ** 3
                t1 = 3 * t * (1 - t) ** 2
                t2 = 3 * t ** 2 * (1 - t)
                t3 = t ** 3
                self._bezier_coefficients.append([t0, t1, t2, t3])
        self.last_cx = x2
        self.last_cy = y2
        for i, t in enumerate(self._bezier_coefficients):
            px = t[0] * self.ctx_cursor_x + t[1] * x1 + t[2] * x2 + t[3] * x
            py = t[0] * self.ctx_cursor_y + t[1] * y1 + t[2] * y2 + t[3] * y
            self.ctx_loop.append([px, py])

        self.ctx_cursor_x, self.ctx_cursor_y = px, py

    def _line_to(self, x, y):
        self._set_cursor_position(x, y)

    def _end_path(self, scope):
        self.ctx_path.append(self.ctx_loop)
        if self.ctx_path:
            path = []
            for orig_loop in self.ctx_path:
                if not orig_loop:
                    continue
                loop = [orig_loop[0]]
                for pt in orig_loop:
                    if (pt[0] - loop[-1][0])**2 + (pt[1] - loop[-1][1])**2 > TOLERANCE:
                        loop.append(pt)
                path.append(loop)
            path_object = SvgPath(self,
                                  scope,
                                  path if scope.stroke else None,
                                  self._triangulate(path, scope) if scope.fill else None)
            self._paths.append(path_object)
            self.path_lookup[scope.path_id] = path_object
        self.ctx_path = []

    def _triangulate(self, looplist, scope):
        t_list = []
        self.ctx_curr_shape = []
        spare_verts = []

        @set_tess_callback(GLU_TESS_VERTEX)
        def vertex_callback(vertex):
            self.ctx_curr_shape.append(list(vertex[0:2]))

        @set_tess_callback(GLU_TESS_BEGIN)
        def begin_callback(which):
            self.ctx_tess_style = which

        @set_tess_callback(GLU_TESS_END)
        def end_callback():
            if self.ctx_tess_style == GL_TRIANGLE_FAN:
                c = self.ctx_curr_shape.pop(0)
                p1 = self.ctx_curr_shape.pop(0)
                while self.ctx_curr_shape:
                    p2 = self.ctx_curr_shape.pop(0)
                    t_list.extend([c, p1, p2])
                    p1 = p2
            elif self.ctx_tess_style == GL_TRIANGLE_STRIP:
                p1 = self.ctx_curr_shape.pop(0)
                p2 = self.ctx_curr_shape.pop(0)
                while self.ctx_curr_shape:
                    p3 = self.ctx_curr_shape.pop(0)
                    t_list.extend([p1, p2, p3])
                    p1 = p2
                    p2 = p3
            elif self.ctx_tess_style == GL_TRIANGLES:
                t_list.extend(self.ctx_curr_shape)
            else:
                self._warn("Unrecognised tesselation style: %d" % (self.ctx_tess_style,))
            self.ctx_tess_style = None
            self.ctx_curr_shape = []

        @set_tess_callback(GLU_TESS_ERROR)
        def error_callback(code):
            ptr = gluErrorString(code)
            err = ''
            idx = 0
            while ptr[idx]: 
                err += chr(ptr[idx])
                idx += 1
            self._warn("GLU Tesselation Error: " + err)

        @set_tess_callback(GLU_TESS_COMBINE)
        def combine_callback(coords, vertex_data, weights):
            x, y, z = coords[0:3]
            dataOut = (x,y,z)
            spare_verts.append((x,y,z))
            return dataOut
        
        data_lists = []
        for vlist in looplist:
            d_list = []
            for x, y in vlist:
                v_data = (x, y, 0)
                d_list.append(v_data)
            data_lists.append(d_list)

        if scope.fill_rule == 'nonzero':
            gluTessProperty(tess, GLU_TESS_WINDING_RULE, GLU_TESS_WINDING_NONZERO)
        elif scope.fill_rule == 'evenodd':
            gluTessProperty(tess, GLU_TESS_WINDING_RULE, GLU_TESS_WINDING_ODD)

        gluTessBeginPolygon(tess, None)
        for d_list in data_lists:    
            gluTessBeginContour(tess)
            for v_data in d_list:
                gluTessVertex(tess, v_data, v_data)
            gluTessEndContour(tess)
        gluTessEndPolygon(tess)
        return t_list

    def _warn(self, message):
        print "Warning: SVG Parser (%s) - %s" % (self.filename, message)



tess = gluNewTess()
gluTessNormal(tess, 0, 0, 1)
gluTessProperty(tess, GLU_TESS_WINDING_RULE, GLU_TESS_WINDING_NONZERO)

def set_tess_callback(which):
    def set_call(func):
        gluTessCallback(tess, which, func)
    return set_call