#! usr/bin/env python 
import os
import pyglet
from pyglet.gl import *
import glsvg


class SVGWindow(pyglet.window.Window):

    def __init__(self, *args, **kwargs):
        super(SVGWindow, self).__init__(*args, **kwargs)
        self.filename = None
        self.svg = None

        self.filelist = [f for f in os.listdir('svgs')
                    if f.endswith('svg') or f.endswith('svgz')]

        glClearColor(1,1,1,1)
        glEnable(GL_LINE_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)

        self.keys = pyglet.window.key.KeyStateHandler()
        self.push_handlers(self.keys)
        self.switch_file(0)
        pyglet.clock.schedule_interval(self.tick, 1/60.0)

    def on_mouse_scroll(self, x, y, dx, dy):
        self.zoom -= dy/100.0

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        self.draw_x += dx
        self.draw_y -= dy

    def on_resize(self, width, height):
        # Override the default on_resize handler to create a 3D projection
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluOrtho2D(0.0, width, height, 0)
        glMatrixMode(GL_MODELVIEW)

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
        self.filename = os.path.join('svgs', self.filelist[next])
        print 'Parsing', self.filename
        self.svg = glsvg.SVG(self.filename)
        self.svg.anchor_x, self.svg.anchor_y = self.svg.width/2, self.svg.height/2

    def on_key_press(self, symbol, modifiers):
        if symbol == pyglet.window.key.RIGHT:
            self.switch_file(1)
        if symbol == pyglet.window.key.LEFT:
            self.switch_file(-1)

    def tick(self, dt):
        if self.keys[pyglet.window.key.W]:
            self.draw_y += 80*dt
        if self.keys[pyglet.window.key.S]:
            self.draw_y -= 80*dt
        if self.keys[pyglet.window.key.D]:
            self.draw_x -= 80*dt
        if self.keys[pyglet.window.key.A]:
            self.draw_x += 80*dt
        if self.keys[pyglet.window.key.UP]:
            self.zoom *= 1.1
        if self.keys[pyglet.window.key.DOWN]:
            self.zoom /= 1.1
        if self.keys[pyglet.window.key.Q]:
            self.angle -= 120*dt
        if self.keys[pyglet.window.key.E]:
            self.angle += 120*dt

    def on_draw(self):
        glClearColor(1, 1, 1, 1)
        self.clear()
        #glViewport(0, 0, 800, 600)
        #glMatrixMode(GL_PROJECTION)
        #glLoadIdentity()
        #gluOrtho2D(0.0, 800.0, 600, 0)
        #glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        self.svg.draw(self.draw_x, self.draw_y, scale=self.zoom, angle=self.angle)
        glPopMatrix()



def main():
    config = pyglet.gl.Config(sample_buffers=1, samples=4, double_buffer=True)
    w = SVGWindow(config=config, resizable=True)
    pyglet.app.run()

if __name__ == '__main__':
    main()
