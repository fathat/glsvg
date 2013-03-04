import math
import re
import string

import graphics
import lines
import traceback

from svg_path_builder import SVGPathBuilder
from glutils import DisplayListGenerator
import svg_style
from vector_math import Matrix
from svg_constants import XMLNS


class SVGRenderableElement(object):

    def __init__(self, svg, element, parent):
        #: The id of the element
        self.id = element.get('id', '')

        #: The parent element
        self.parent = parent

        #: Is this element a pattern?
        self.is_pattern = element.tag.endswith('pattern')

        #: Is this element a definition?
        self.is_def = False

        if parent:
            parent.add_child(self)
            self.is_def = parent.is_def

        #: The element style (possibly with inherited traits from parent style)
        self.style = svg_style.SVGStyle(parent.style if parent else None)
        self.style.from_element(element)

        #: Optional element title
        self.title = element.findtext('{%s}title' % (XMLNS,))

        #: Optional element description. Useful for embedding metadata.
        self.description = element.findtext('{%s}desc' % (XMLNS,))

        #construct a matrix for each transform
        t_acc = Matrix.identity()

        transform_str = element.get('transform', None)
        if transform_str:
            transforms = transform_str.strip().split(' ')

            for tstring in transforms:
                t_acc = t_acc * Matrix(tstring)

        #: Element transforms
        self.transform = t_acc

        #: Children elements
        self.children = []

        #: XML tag this was originally.
        self.tag_type = element.tag

    def add_child(self, child):
        """Add a child to this element class (usually children register with parent)"""
        self.children.append(child)

    @property
    def is_pattern_part(self):
        part = self
        while part:
            if part.is_pattern:
                return True
            part = part.parent
        return False


    @property
    def absolute_transform(self):
        """Return this transform, multiplied by chain of parents"""
        if self.parent:
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


XLINK_NS = "{http://www.w3.org/1999/xlink}"


class SVGUse(SVGRenderableElement):
    """Represents an SVG "use" directive, to reuse a predefined path"""

    def __init__(self, svg, element, parent):
        SVGRenderableElement.__init__(self, svg, element, parent)
        self.svg = svg
        self.target = element.get(XLINK_NS + "href", None)

        #clip off "#"
        if self.target:
            self.target = self.target[1:]

    def render(self):
        with self.absolute_transform:
            self.svg.defs[self.target].render()


class SVGDefs(SVGRenderableElement):
    """Represents an SVG "defs" directive, to define paths without drawing them"""

    def __init__(self, svg, element, parent):
        SVGRenderableElement.__init__(self, svg, element, parent)
        self.svg = svg
        self.is_def = True

    def add_child(self, child):
        self.svg.defs[child.id] = child
        self.children.append(child)


def flatten_list(l):
    new_list = []
    for x in l:
        new_list.extend(x)
    return new_list


class SVGPath(SVGRenderableElement):
    """
    Represents a single SVG path. This is usually
    a distinct shape with a fill pattern,
    an outline, or both.
    """

    def __init__(self, svg, element, parent):

        SVGRenderableElement.__init__(self, svg, element, parent)
        #: The original SVG file
        self.svg = svg

        if not self.is_pattern_part:
            self.config = svg.config
        else:
            self.config = svg.config.super_detailed()

        #: The actual path elements, as a list of vertices
        self.outline = None

        #: The triangles that comprise the inner fill
        self.triangles = None

        #: The base shape. Possible values: path, rect, circle, ellipse, line, polygon, polyline
        self.shape = None

        self.bb = None

        path_builder = SVGPathBuilder(
                        self,
                        element,
                        self.config)

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

        is_miter = self.style.stroke_linejoin == 'miter'

        miter_limit = self.style.stroke_miterlimit if is_miter else 0

        for loop in self.outline:
            self.svg.n_lines += len(loop) - 1
            loop_plus = []
            for i in xrange(len(loop) - 1):
                loop_plus += [loop[i], loop[i+1]]
            if isinstance(stroke, str):
                g = self.svg._gradients[stroke]
                strokes = [g.sample(x, self) for x in loop_plus]
            else:
                strokes = [stroke for x in loop_plus]
            if len(loop_plus) == 0:
                continue
            if len(self.style.stroke_dasharray):
                ls = lines.split_line_by_pattern(loop_plus, self.style.stroke_dasharray)

                if ls[0][0] == ls[-1][-1]:
                    #if the last line end point equals the first line start point,
                    #this is a "closed" line, so combine the first and the last line
                    combined_line = ls[-1] + ls[0]
                    ls[0] = combined_line
                    del ls[-1]

                for l in ls:
                    lines.draw_polyline(
                        l,
                        stroke_width,
                        color=strokes[0],
                        line_cap=self.style.stroke_linecap,
                        join_type=self.style.stroke_linejoin,
                        miter_limit=miter_limit)

            else:
                lines.draw_polyline(
                    loop_plus,
                    stroke_width,
                    color=strokes[0],
                    line_cap=self.style.stroke_linecap,
                    join_type=self.style.stroke_linejoin,
                    miter_limit=miter_limit)

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
        self.svg.n_tris += len(tris) / 3
        g = None
        if isinstance(fill, str):
            g = self.svg._gradients[fill]
            fills = [g.sample(x, self) for x in tris]
        else:
            fills = [fill] * len(tris)  # for x in tris]

        if g:
            g.apply_shader(self, self.transform, self.style.opacity * self.style.fill_opacity)

        graphics.draw_colored_triangles(
            flatten_list(tris),
            flatten_list(fills)
        )

        if g:
            g.unapply_shader()

    def bounding_box(self):
        '''
        returns a tuple describing the bounding box:

        (min_x, min_y, max_x, max_y)
        '''
        if not self.bb:

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
            self.bb = (min_x, min_y, max_x, max_y)
        return self.bb

    def _render_pattern_fill(self):
        fill = self.style.fill
        tris = self.triangles
        pattern = None
        if fill in self.svg.patterns:
            pattern = self.svg.patterns[fill]
            pattern.bind_texture()

        min_x, min_y, max_x, max_y = self.bounding_box()

        tex_coords = []

        for vtx in tris:
            tex_coords.append((vtx[0]-min_x)/(max_x-min_x)/pattern.width)
            tex_coords.append((vtx[1]-min_y)/(max_y-min_y)/pattern.width)

        graphics.draw_textured_triangles(
            flatten_list(tris),
            tex_coords
        )

        if pattern:
            pattern.unbind_texture()

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
        with self.absolute_transform:
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
