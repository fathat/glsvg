import math
import re
import string

from OpenGL.GL import *
from OpenGL.GLU import *
from svg_constants import *

import lines
import traceback

class SvgPath(object):
    """

    """

    def __init__(self, svg, scope, element):
        self.svg = svg
        self.config = svg.config
        self.scope = scope
        self.transform = scope.transform
        self.fill = scope.fill
        self.stroke = scope.stroke
        self.stroke_width = scope.stroke_width
        self.path = None
        self.polygon = None
        self.id = scope.path_id
        self.title = scope.path_title
        self.description = scope.path_description
        self.shape = None
        self.is_pattern = scope.is_pattern
        self.is_pattern_part = scope.is_pattern_part
        self._bezier_coefficients = []

        if self.is_pattern_part:
            svg.register_pattern_part(scope.parent.path_id, self)

        self.parse_element(element)

    def parse_element(self, e):
        path = self
        scope = self.scope
        if e.tag.endswith('path'):
            self.shape = 'path'
            path._read_path(e, scope)
        elif e.tag.endswith('rect'):
            self.shape = 'rect'
            x = float(e.get('x', 0))
            y = float(e.get('y', 0))
            h = float(e.get('height'))
            w = float(e.get('width'))
            self.x, self.y, self.w, self.h = x, y, w, h
            path._start_path()
            path._set_cursor_position(x, y)
            path._line_to(x + w, y)
            path._line_to(x + w, y + h)
            path._line_to(x, y + h)
            path._line_to(x, y)
            path._end_path(scope)
        elif e.tag.endswith('polyline') or e.tag.endswith('polygon'):
            self.shape = 'polygon'
            path_data = e.get('points')
            path_data = re.findall("(-?[0-9]+\.?[0-9]*(?:e-?[0-9]*)?)", path_data)

            def next_point():
                return float(path_data.pop(0)), float(path_data.pop(0))
            path._start_path()
            while path_data:
                path._line_to(*next_point())
            if e.tag.endswith('polygon'):
                path._close_path()
            path._end_path(scope)
        elif e.tag.endswith('line'):
            self.shape = 'line'
            x1 = float(e.get('x1'))
            y1 = float(e.get('y1'))
            x2 = float(e.get('x2'))
            y2 = float(e.get('y2'))
            self.x1, self.x1, self.x2, self.y2 = x1, y1, x2, y2
            path._start_path()
            path._set_cursor_position(x1, y1)
            path._line_to(x2, y2)
            path._end_path(scope)
        elif e.tag.endswith('circle'):
            self.shape = 'circle'
            cx = float(e.get('cx'))
            cy = float(e.get('cy'))
            r = float(e.get('r'))
            self.cx, self.cy, self.r = cx, cy, r
            path._start_path()
            for i in xrange(self.config.circle_points):
                theta = 2 * i * math.pi / self.config.circle_points
                path._line_to(cx + r * math.cos(theta), cy + r * math.sin(theta))
            path._close_path()
            path._end_path(scope)
        elif e.tag.endswith('ellipse'):
            self.shape = 'ellipse'
            cx = float(e.get('cx'))
            cy = float(e.get('cy'))
            rx = float(e.get('rx'))
            ry = float(e.get('ry'))
            self.cx, self.cy, self.rx, self.ry = cx, cy, rx, ry
            path._start_path()
            for i in xrange(self.config.circle_points):
                theta = 2 * i * math.pi / self.config.circle_points
                path._line_to(cx + rx * math.cos(theta), cy + ry * math.sin(theta))
            path._close_path()
            path._end_path(scope)

    def _start_path(self):
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

    def _read_path(self, e, scope):
        path_data = e.get('d', '')
        path_data = re.findall("([A-Za-z]|-?[0-9]+\.?[0-9]*(?:e-?[0-9]*)?)", path_data)

        def next_point():
            return float(path_data.pop(0)), float(path_data.pop(0))

        self._start_path()
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
                x, y = next_point()
                self._quadratic_curve_to(mx, my, x, y)

            elif opcode == 't':
                # relative quadratic curve with control point as reflection
                mx = 2 * self.ctx_cursor_x - self.last_cx
                my = 2 * self.ctx_cursor_y - self.last_cy
                x, y = next_point()
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
                self._arc_to(rx, ry, phi, large_arc, sweep, self.ctx_cursor_x + x, self.ctx_cursor_y + y)
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
        n_points = max(int(abs(self.config.circle_points * delta / (2 * math.pi))), 1)

        for i in xrange(n_points + 1):
            theta = psi + i * delta / n_points
            ct = math.cos(theta)
            st = math.sin(theta)
            self._line_to(cp * rx * ct - sp * ry * st + cx,
                          sp * rx * ct + cp * ry * st + cy)

    def _quadratic_curve_to(self, x1, y1, x2, y2):
        x0, y0 = self.ctx_cursor_x, self.ctx_cursor_y
        n_bezier_points = self.config.bezier_points
        for i in xrange(n_bezier_points+1):
            t = float(i) / n_bezier_points
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
        n_bezier_points = self.config.bezier_points
        if not self._bezier_coefficients:
            for i in xrange(n_bezier_points + 1):
                t = float(i) / n_bezier_points
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

            self.path = path if scope.stroke else None
            self.polygon = self._triangulate(path, scope) if scope.fill else None
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
        if not self.path: return
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

tess = gluNewTess()
gluTessNormal(tess, 0, 0, 1)
gluTessProperty(tess, GLU_TESS_WINDING_RULE, GLU_TESS_WINDING_NONZERO)

def set_tess_callback(which):
    def set_call(func):
        gluTessCallback(tess, which, func)
    return set_call