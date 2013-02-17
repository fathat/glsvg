from OpenGL.GL import *

from glutils import ViewportAs

import render_target

from parser_utils import *
from svg_constants import *

class Pattern(object):

    def __init__(self, element, svg):
        self.svg = svg
        self.id = element.get('id')
        self.units = element.get('patternContentUnits', 'objectBoundingBox')
        self.width = parse_float(element.get('width', '1.0'))
        self.height = parse_float(element.get('height', '1.0'))
        self.render_texture = None
        self.paths = []
        self.render_texture = render_target.RenderTarget(PATTERN_TEX_SIZE, PATTERN_TEX_SIZE)

    def bind_texture(self):
        if not self.render_texture:
            return
        self.render_texture.texture.bind()

    def unbind_texture(self):
        if not self.render_texture:
            return
        self.render_texture.texture.unbind()

    def render(self):
        #setup projection matrix..
        with self.render_texture:
            with ViewportAs(self.width, self.height, PATTERN_TEX_SIZE, PATTERN_TEX_SIZE):
                glClearColor(0.0, 0.5, 1.0, 1.0)
                glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
                for path in self.paths:
                    path.render()

