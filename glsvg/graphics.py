import OpenGL.GL as gl


def draw_triangle_strip(vertices, colors, tex_coord_1d=None):
    gl.glEnableClientState(gl.GL_VERTEX_ARRAY)
    gl.glEnableClientState(gl.GL_COLOR_ARRAY)
    gl.glColorPointer(4, gl.GL_UNSIGNED_BYTE, 0, colors)
    gl.glVertexPointer(2, gl.GL_FLOAT, 0, vertices)
    if tex_coord_1d:
        gl.glEnableClientState(gl.GL_TEXTURE_COORD_ARRAY)
        gl.glTexCoordPointer(1, gl.GL_FLOAT, 0, tex_coord_1d)
    gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, len(vertices) / 2)
    gl.glDisableClientState(gl.GL_VERTEX_ARRAY)
    gl.glDisableClientState(gl.GL_COLOR_ARRAY)
    gl.glDisableClientState(gl.GL_TEXTURE_COORD_ARRAY)


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