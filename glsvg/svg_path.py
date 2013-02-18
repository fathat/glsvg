import math
import re
import string

from OpenGL.GL import *
import lines
import traceback

from svg_path_builder import SVGPathBuilder
from glutils import DisplayListGenerator
import svg_style
from vector_math import Matrix
from svg_constants import XMLNS


class SVGRenderableElement(object):

    def __init__(self, svg, element, parent):

        self.id = element.get('id', '')
        self.parent = parent
        if parent:
            parent.add_child(self)

        self.is_pattern = element.tag.endswith('pattern')
        self.is_def = element.tag.endswith("defs")

        self.style = svg_style.SVGStyle(parent.style if parent else None)
        self.style.from_element(element)

        self.title = element.findtext('{%s}title' % (XMLNS,))
        self.description = element.findtext('{%s}desc' % (XMLNS,))

        self.transform = Matrix(element.get('transform', None))
        if not self.transform:
            self.transform = Matrix([1, 0, 0, 1, 0, 0])

        self.children = []
        self.tag_type = element.tag

    def add_child(self, child):
        self.children.append(child)

    @property
    def absolute_transform(self):
        if self.parent.transform:
            return self.parent.absolute_transform * self.transform
        return self.transform

    def on_render(self):
        pass

    def render(self):
        self.on_render()

        for c in self.children:
            c.render()


class SVGGroup(SVGRenderableElement):
    pass


class SVGPath(SVGRenderableElement):
    """
    Represents a single SVG path. This is usually
    a distinct shape with a fill pattern,
    an outline, or both.
    """

    def __init__(self, svg, element, parent):

        SVGRenderableElement.__init__(self, svg, element, parent)

        self.svg = svg
        self.config = svg.config

        #: The actual path elements, as a list of vertices
        self.outline = None

        #: The triangles that comprise the inner fill
        self.triangles = None

        #: The base shape. Possible values: path, rect, circle, ellipse, line, polygon, polyline
        self.shape = None

        path_builder = SVGPathBuilder(
                        self,
                        element,
                        svg.config)

        self.outline = path_builder.path

        self.triangles = path_builder.polygon

        self.display_list = None

    def _generate_display_list(self):
        with DisplayListGenerator() as dl:
            self.render()
            self.display_list = dl

    def _render_stroke(self):
        stroke = self.style.stroke
        stroke_width = self.style.stroke_width
        for loop in self.outline:
            self.svg.n_lines += len(loop) - 1
            loop_plus = []
            for i in xrange(len(loop) - 1):
                loop_plus += [loop[i], loop[i+1]]
            if isinstance(stroke, str):
                g = self.svg._gradients[stroke]
                strokes = [g.sample(x) for x in loop_plus]
            else:
                strokes = [stroke for x in loop_plus]
            lines.draw_polyline(loop_plus, stroke_width, colors=strokes)

    def _render_stroke_stencil(self):
        if not self.outline:
            return
        stroke_width = self.style.stroke_width
        for loop in self.outline:
            loop_plus = []
            for i in xrange(len(loop) - 1):
                loop_plus += [loop[i], loop[i+1]]
            lines.draw_polyline(loop_plus, stroke_width)

    def _render_gradient_fill(self):
        fill = self.style.fill
        tris = self.triangles
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

    def bounding_box(self):
        '''
        returns a tuple describing the bounding box:

        (min_x, min_y, max_x, max_y)
        '''
        min_x = None
        max_x = None
        min_y = None
        max_y = None

        if self.triangles:
            for vtx in self.triangles:
                x, y = vtx
                if min_x is None or x < min_x:
                    min_x = x
                if min_y is None or y < min_y:
                    min_y = y
                if max_x is None or x > max_x:
                    max_x = x
                if max_y is None or y > max_y:
                    max_y = y
        if self.outline:
            for p in self.outline:
                for vtx in p:
                    x, y = vtx
                    if min_x is None or x < min_x:
                        min_x = x
                    if min_y is None or y < min_y:
                        min_y = y
                    if max_x is None or x > max_x:
                        max_x = x
                    if max_y is None or y > max_y:
                        max_y = y
        return (min_x, min_y, max_x, max_y)

    def _render_pattern_fill(self):
        fill = self.style.fill
        tris = self.triangles
        pattern = None
        if fill in self.svg.patterns:
            pattern = self.svg.patterns[fill]
            glEnable(GL_TEXTURE_2D)
            pattern.bind_texture()

        min_x, min_y, max_x, max_y = self.bounding_box()

        glBegin(GL_TRIANGLES)
        for vtx in tris:
            glColor4f(1, 1, 1, 1)
            glTexCoord2f((vtx[0]-min_x)/(max_x-min_x)/pattern.width, (vtx[1]-min_y)/(max_y-min_y)/pattern.width)
            glVertex3f(vtx[0], vtx[1], 0)
        glEnd()

        if not pattern:
            pattern.unbind_texture()

        glDisable(GL_TEXTURE_2D)

    def _render_stenciled(self):
        with self.transform:
            if self.triangles:
                try:
                    #if stencil is on
                    if self.svg.is_stencil_enabled():
                        glEnable(GL_STENCIL_TEST)
                        mask = self.svg._next_stencil_mask()
                        glStencilFunc(GL_NEVER, mask, 0xFF)
                        glStencilOp(GL_REPLACE, GL_KEEP, GL_KEEP)  # draw mask id on test fail (always)
                        glStencilMask(mask)
                        self._render_stroke_stencil()

                        #draw where stencil hasn't masked out
                        glStencilFunc(GL_NOTEQUAL, mask, 0xFF)

                    #stencil fill
                    if isinstance(self.style.fill, str) and self.style.fill in self.svg.patterns:
                        self._render_pattern_fill()
                    else:
                        self._render_gradient_fill()

                except Exception as exception:
                    traceback.print_exc(exception)
                finally:
                    if self.svg.is_stencil_enabled():
                        glDisable(GL_STENCIL_TEST)
            if self.outline:
                self._render_stroke()

    def on_render(self):
        """Render immediately to screen (no display list). Slow! Consider
        using SVG.draw(...) instead."""
        with self.transform:
            if self.triangles:
                try:
                    if isinstance(self.style.fill, str) and self.style.fill in self.svg.patterns:
                        self._render_pattern_fill()
                    else:
                        self._render_gradient_fill()
                except Exception as exception:
                    traceback.print_exc(exception)
            if self.outline:
                self._render_stroke()


    def __repr__(self):
        return "<SVGPath id=%s title='%s' description='%s' transform=%s>" % (
            self.id, self.title, self.description, self.transform
        )
