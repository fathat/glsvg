import math
import re
import string

from OpenGL.GL import *
import lines
import traceback

from svg_path_builder import SvgPathBuilder

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

        if self.is_pattern_part:
            svg.register_pattern_part(scope.parent.path_id, self)

        path_builder = SvgPathBuilder(self, scope, element, svg.config)
        self.path = path_builder.path
        self.polygon = path_builder.polygon

    def render_stroke(self):
        stroke = self.stroke
        stroke_width = self.stroke_width
        for loop in self.path:
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
