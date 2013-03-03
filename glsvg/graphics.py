import OpenGL.GL as gl
import math

def draw_triangle_strip(vertices, color):
    if color:
        gl.glColor4ub(*color)
    gl.glEnableClientState(gl.GL_VERTEX_ARRAY)
    #gl.glEnableClientState(gl.GL_COLOR_ARRAY)
    #gl.glColorPointer(4, gl.GL_UNSIGNED_BYTE, 0, colors)
    gl.glVertexPointer(2, gl.GL_FLOAT, 0, vertices)
    gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, len(vertices) / 2)
    gl.glDisableClientState(gl.GL_VERTEX_ARRAY)
    #gl.glDisableClientState(gl.GL_COLOR_ARRAY)


def draw_round_cap(center, radius, angle):
    gl.glBegin(gl.GL_TRIANGLE_FAN)
    gl.glVertex2f(center.x, center.y)
    for theta in xrange(-90, 91, 10):
        at = theta*(math.pi/180) + angle
        x = math.cos(at) * radius + center.x
        y = math.sin(at) * radius + center.y

        gl.glVertex2f(x, y)
    gl.glEnd()


def draw_colored_triangles(tris, colors):
    gl.glEnableClientState(gl.GL_VERTEX_ARRAY)
    gl.glEnableClientState(gl.GL_COLOR_ARRAY)
    gl.glColorPointer(4, gl.GL_UNSIGNED_BYTE, 0, colors)
    gl.glVertexPointer(2, gl.GL_FLOAT, 0, tris)
    gl.glDrawArrays(gl.GL_TRIANGLES, 0, len(tris) / 2)
    gl.glDisableClientState(gl.GL_VERTEX_ARRAY)
    gl.glDisableClientState(gl.GL_COLOR_ARRAY)


def draw_textured_triangles(tris, tex_coords):
    gl.glColor4f(1, 1, 1, 1)
    gl.glEnable(gl.GL_TEXTURE_2D)
    gl.glEnableClientState(gl.GL_VERTEX_ARRAY)
    gl.glEnableClientState(gl.GL_TEXTURE_COORD_ARRAY)

    gl.glVertexPointer(2, gl.GL_FLOAT, 0, tris)
    gl.glTexCoordPointer(2, gl.GL_FLOAT, 0, tex_coords)
    gl.glDrawArrays(gl.GL_TRIANGLES, 0, len(tris) / 2)
    gl.glDisableClientState(gl.GL_VERTEX_ARRAY)
    gl.glDisableClientState(gl.GL_TEXTURE_COORD_ARRAY)
    gl.glDisable(gl.GL_TEXTURE_2D)