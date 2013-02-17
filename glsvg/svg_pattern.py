from OpenGL.GL import *

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
            path.render()
        glMatrixMode(GL_PROJECTION)

        glPopMatrix()
        glViewport(int(viewport[0]), int(viewport[1]), int(viewport[2]), int(viewport[3]))
        glMatrixMode(GL_MODELVIEW)

        self.render_texture.unbind()
