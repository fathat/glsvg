import pygame
import sys
import os
sys.path.append(os.path.abspath('../'))
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import glsvg

class App:
    def __init__(self):
        self._running = True
        self._display_surf = None
        self.size = self.width, self.height = 800, 600

    def reset_camera(self):
        self.zoom = 1
        self.angle = 0
        self.draw_x = 400
        self.draw_y = 300

    def switch_file(self, dir=0):
        self.reset_camera()
        if not self.filename:
            next = 0
        else:
            prevFile = os.path.basename(self.filename)
            next = self.filelist.index(prevFile)+dir
            next %= len(self.filelist)
        self.filename = os.path.join('../svgs', self.filelist[next])
        print 'Parsing', self.filename
        self.svg = glsvg.SVGDoc(self.filename)
        self.svg.anchor_x, self.svg.anchor_y = self.svg.width/2, self.svg.height/2

    def on_init(self):
        pygame.init()
        self._display_surf = pygame.display.set_mode(self.size, pygame.HWSURFACE|pygame.OPENGL|pygame.DOUBLEBUF)
        self._running = True
        self.filelist = [f for f in os.listdir('../svgs')
                             if f.endswith('svg') or f.endswith('svgz')]
        self.filename = None
        self.svg = None
        self.switch_file()

    def on_event(self, event):
        if event.type == pygame.QUIT:
            self._running = False
        if event.type == pygame.KEYUP:
            if event.key == pygame.K_RIGHT:
                self.switch_file(1)
            if event.key == pygame.K_LEFT:
                self.switch_file(-1)

    def on_loop(self):
        pass

    def on_render(self):
        glClearColor(1, 1, 1, 1)
        glStencilMask(0xFF)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glViewport(0, 0, self.width, self.height)
        gluOrtho2D(0.0, self.width, self.height, 0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        self.svg.draw(self.draw_x, self.draw_y, scale=self.zoom, angle=self.angle)

    def on_cleanup(self):
        pygame.quit()

    def on_execute(self):
        self.on_init()

        while( self._running ):
            for event in pygame.event.get():
                self.on_event(event)
            self.on_loop()
            self.on_render()

            pygame.display.flip()

        self.on_cleanup()

def main():
    app = App()
    app.on_execute()

if __name__ == "__main__" :
    main()