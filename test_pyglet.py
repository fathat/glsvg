#! usr/bin/env python 
import os
import sys
import pyglet
from pyglet.gl import *


import glsvg
import glsvg.lines

from glsvg.lines import vec2

config = pyglet.gl.Config(sample_buffers=1, samples=4)
w = pyglet.window.Window(config=config, resizable=True)

keys = pyglet.window.key.KeyStateHandler()
w.push_handlers(keys)

glClearColor(1,1,1,1)
glEnable(GL_LINE_SMOOTH)
glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)
glLineWidth(2)

glsvg.setup_gl()

filelist = [f for f in os.listdir('svgs')
            if f.endswith('svg') or f.endswith('svgz')]
filename = None
svgObj = None

def next_file():
    global filename, svgObj
    if not filename:
        next = 0
    else:
        prevFile = os.path.basename(filename)
        next = filelist.index(prevFile)+1
        next %= len(filelist)
    filename = os.path.join('svgs', filelist[next])
    print 'Parsing', filename
    svgObj = glsvg.SVG(filename)
    svgObj.anchor_x, svgObj.anchor_y = svgObj.width/2, svgObj.height/2

next_file()

zoom = 1
angle = 0
draw_x = 400
draw_y = 300

def tick(dt):
    global zoom, angle, draw_x, draw_y
    if keys[pyglet.window.key.W]:
        draw_y += 80*dt
    if keys[pyglet.window.key.S]:
        draw_y -= 80*dt
    if keys[pyglet.window.key.D]:
        draw_x -= 80*dt
    if keys[pyglet.window.key.A]:
        draw_x += 80*dt
    if keys[pyglet.window.key.UP]:
        zoom *= 1.1
    if keys[pyglet.window.key.DOWN]:
        zoom /= 1.1
    if keys[pyglet.window.key.Q]:
        angle -= 120*dt
    if keys[pyglet.window.key.E]:
        angle += 120*dt
        
def on_key_press(symbol, modifiers):
    if symbol == pyglet.window.key.SPACE:
        next_file()
w.push_handlers(on_key_press)

pyglet.clock.schedule_interval(tick, 1/60.0)

@w.event
def on_draw():
    w.clear()
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluOrtho2D(0.0, 800.0, 600, 0)
    glMatrixMode(GL_MODELVIEW)
    svgObj.draw(draw_x, draw_y, scale=zoom, angle=angle)
    #glColor3f(0, 0, 0)
    #glsvg.lines.draw_polyline([[40, 40], [1200, 40]], 1)
    #glsvg.lines.draw_polyline(
    #    [vec2(40, 100),
    #     vec2(500, 150),
    #     vec2(500, 300),
    #     vec2(40, 200)],
    #    8.0,
    #    closed=True
    #)


    
pyglet.app.run()
