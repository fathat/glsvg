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
        self.fpslabel = pyglet.clock.ClockDisplay()
        self.statslabel = pyglet.text.Label("tris: N/A, lines: N/A", color=(0,0,0,255))
        self.statslabel.anchor_y = "top"

        self.instruction_label = pyglet.text.Label(
            "Scroll: WASD or Drag Mouse, Zoom: Mouse Wheel, Switch File: left/right arrow",
            color=(0,0,0,255))
        self.instruction_label.anchor_y = "top"

        self.filelist = [f for f in os.listdir('svgs')
                    if f.endswith('svg') or f.endswith('svgz')]

        glClearColor(1,1,1,1)
        glEnable(GL_LINE_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)

        self.show_wireframe = False
        self.keys = pyglet.window.key.KeyStateHandler()
        self.push_handlers(self.keys)
        self.switch_file(0)
        pyglet.clock.schedule_interval(self.tick, 1/60.0)

    def on_mouse_scroll(self, x, y, dx, dy):
        self.zoom += dy/20.0

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        self.draw_x += dx
        self.draw_y -= dy

    def on_resize(self, width, height):
        # Override the default on_resize handler to create a 3D projection
        glViewport(0, 0, width, height)


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
        self.statslabel.text = "tris: " + str(self.svg.n_tris) + ", lines: " + str(self.svg.n_lines)

    def on_key_press(self, symbol, modifiers):
        if symbol == pyglet.window.key.RIGHT:
            self.switch_file(1)
        if symbol == pyglet.window.key.LEFT:
            self.switch_file(-1)
        if symbol == pyglet.window.key.SPACE:
            self.show_wireframe = not self.show_wireframe

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
        glPushMatrix()

        if self.show_wireframe:
            glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)

        # set projection matrix to have top-left be (0,0), as
        # SVGs are defined in that way
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluOrtho2D(0.0, self.width, self.height, 0)
        glMatrixMode(GL_MODELVIEW)
        glDisable(GL_TEXTURE_2D)
        self.svg.draw(self.draw_x, self.draw_y, scale=self.zoom, angle=self.angle)

        #draw patterns
        i = 0
        for pattern in self.svg.patterns.values():
            glEnable(GL_TEXTURE_2D)
            pattern.bind_texture()
            glColor4f(1,1,1,1)
            glBegin(GL_QUADS)
            glTexCoord2f(0, 0)
            glVertex2f(0, 0)
            glTexCoord2f(1, 0)
            glVertex2f(128, 0)
            glTexCoord2f(1, 1)
            glVertex2f(128, 128)
            glTexCoord2f(0, 1)
            glVertex2f(0, 128)
            glEnd()
            pattern.unbind_texture()
            glTranslatef(128, 0, 0)
        glPopMatrix()

        glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)

        # reverse y projection for pyglet stats drawing
        # (because pyglet expects (0,0) to be bottom left
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluOrtho2D(0.0, self.width, 0, self.height)
        glMatrixMode(GL_MODELVIEW)

        self.instruction_label.y = self.height
        self.instruction_label.draw()
        self.statslabel.y = self.height-20
        self.statslabel.draw()
        self.fpslabel.draw()




def main():
    config = pyglet.gl.Config(sample_buffers=1, samples=4, stencil_size=8, double_buffer=True)
    w = SVGWindow(config=config, resizable=True)
    pyglet.app.run()

if __name__ == '__main__':
    main()
