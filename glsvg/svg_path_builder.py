import math
import re
import string

from OpenGL.GL import *
from OpenGL.GLU import *
from svg_constants import *
from parser_utils import *
from vector_math import Matrix

POINT_RE = re.compile("(-?[0-9]+\.?[0-9]*(?:e-?[0-9]*)?)")
PATH_CMD_RE = re.compile("([A-Za-z]|-?[0-9]+\.?[0-9]*(?:e-?[0-9]*)?)")


class SvgElementScope:
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


class SvgPathBuilder(object):
    def __init__(self, path, scope, element, config):
        self._bezier_coefficients = []
        self.ctx_cursor_x = 0
        self.ctx_cursor_y = 0
        self.close_index = 0
        self.ctx_path = []
        self.ctx_loop = []
        self.scope = scope
        self.config = config

        e = element
        if e.tag.endswith('path'):
            path.shape = 'path'
            self._read_path_commands(e, scope)
        elif e.tag.endswith('rect'):
            path.shape = 'rect'
            x = float(e.get('x', 0))
            y = float(e.get('y', 0))
            h = float(e.get('height'))
            w = float(e.get('width'))
            path.x, path.y, path.w, path.h = x, y, w, h
            self._set_cursor_position(x, y)
            self._line_to(x + w, y)
            self._line_to(x + w, y + h)
            self._line_to(x, y + h)
            self._line_to(x, y)
            self._end_path()
        elif e.tag.endswith('polyline') or e.tag.endswith('polygon'):
            path.shape = 'polygon'
            path_data = e.get('points')
            path_data = POINT_RE.findall(path_data)

            def next_point():
                return float(path_data.pop(0)), float(path_data.pop(0))
            while path_data:
                self._line_to(*next_point())
            if e.tag.endswith('polygon'):
                self._close_path()
            self._end_path()
        elif e.tag.endswith('line'):
            path.shape = 'line'
            x1 = float(e.get('x1'))
            y1 = float(e.get('y1'))
            x2 = float(e.get('x2'))
            y2 = float(e.get('y2'))
            path.x1, path.x1, path.x2, path.y2 = x1, y1, x2, y2
            self._set_cursor_position(x1, y1)
            self._line_to(x2, y2)
            self._end_path()
        elif e.tag.endswith('circle'):
            path.shape = 'circle'
            cx = float(e.get('cx'))
            cy = float(e.get('cy'))
            r = float(e.get('r'))
            path.cx, path.cy, path.r = cx, cy, r
            for i in xrange(config.circle_points):
                theta = 2 * i * math.pi / config.circle_points
                self._line_to(cx + r * math.cos(theta), cy + r * math.sin(theta))
            self._close_path()
            self._end_path()
        elif e.tag.endswith('ellipse'):
            path.shape = 'ellipse'
            cx = float(e.get('cx'))
            cy = float(e.get('cy'))
            rx = float(e.get('rx'))
            ry = float(e.get('ry'))
            path.cx, path.cy, path.rx, path.ry = cx, cy, rx, ry
            for i in xrange(config.circle_points):
                theta = 2 * i * math.pi / config.circle_points
                self._line_to(cx + rx * math.cos(theta), cy + ry * math.sin(theta))
            self._close_path()
            self._end_path()

    def _close_path(self):
        self.ctx_loop.append(self.ctx_loop[0][:])
        self.ctx_path.append(self.ctx_loop)
        self.ctx_loop = []

    def _set_cursor_position(self, x, y):
        self.ctx_cursor_x = x
        self.ctx_cursor_y = y
        self.ctx_loop.append([x, y])

    def _read_path_commands(self, e, scope):
        path_data = e.get('d', '')
        path_data = PATH_CMD_RE.findall(path_data)

        def next_point():
            return float(path_data.pop(0)), float(path_data.pop(0))

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
        self._end_path()

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

    def _end_path(self):
        scope = self.scope
        self.ctx_path.append(self.ctx_loop)
        if self.ctx_path:
            path = []
            for orig_loop in self.ctx_path:
                if not orig_loop:
                    continue
                loop = [orig_loop[0]]
                for pt in orig_loop:
                    if (pt[0] - loop[-1][0])**2 + (pt[1] - loop[-1][1])**2 > self.config.tolerance:
                        loop.append(pt)
                path.append(loop)

            self.path = path if scope.stroke else None
            self.polygon = self._triangulate(path, scope) if scope.fill else None
        self.ctx_path = []

    def _triangulate(self, looplist, scope):
        t_list = []
        self.ctx_curr_shape = []
        spare_verts = []
        tess = gluNewTess()
        gluTessNormal(tess, 0, 0, 1)
        gluTessProperty(tess, GLU_TESS_WINDING_RULE, GLU_TESS_WINDING_NONZERO)

        def set_tess_callback(which):
            def set_call(func):
                gluTessCallback(tess, which, func)
            return set_call

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
        print "Warning: SVG Parser - %s" % (message,)



