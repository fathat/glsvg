#! usr/bin/env python 
import os
import sys
import pyglet
from pyglet.gl import *
import glsvg


class SVGWindow(pyglet.window.Window):

    def __init__(self, *args, **kwargs):
        super(SVGWindow, self).__init__(*args, **kwargs)
        self.filename = None
        self.svgObj = None

        self.filelist = [f for f in os.listdir('svgs')
                    if f.endswith('svg') or f.endswith('svgz')]

        glClearColor(1,1,1,1)
        glEnable(GL_LINE_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)
        glLineWidth(2)

        glsvg.setup_gl()
        self.keys = pyglet.window.key.KeyStateHandler()
        self.push_handlers(self.keys)
        self.next_file()
        pyglet.clock.schedule_interval(self.tick, 1/60.0)


    def reset_camera(self):
        self.zoom = 1
        self.angle = 0
        self.draw_x = 400
        self.draw_y = 300

    def next_file(self):
        self.reset_camera()
        if not self.filename:
            next = 0
        else:
            prevFile = os.path.basename(self.filename)
            next = self.filelist.index(prevFile)+1
            next %= len(self.filelist)
        self.filename = os.path.join('svgs', self.filelist[next])
        print 'Parsing', self.filename
        self.svgObj = glsvg.SVG(self.filename)
        self.svgObj.anchor_x, self.svgObj.anchor_y = self.svgObj.width/2, self.svgObj.height/2

    def on_key_press(self, symbol, modifiers):
        if symbol == pyglet.window.key.SPACE:
            self.next_file()

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
        self.clear()
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluOrtho2D(0.0, 800.0, 600, 0)
        glMatrixMode(GL_MODELVIEW)
        self.svgObj.draw(self.draw_x, self.draw_y, scale=self.zoom, angle=self.angle)



def main():
    config = pyglet.gl.Config(sample_buffers=1, samples=4)
    w = SVGWindow(config=config, resizable=True)
    pyglet.app.run()

if __name__ == '__main__':
    main()
