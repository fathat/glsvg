from OpenGL.GL import *


class CurrentTransform:
    def __enter__(self):
        glPushMatrix()
        return self

    def __exit__(self, type, value, traceback):
        glPopMatrix()


class DisplayList:
    def __init__(self):
        self.display_list_id = glGenLists(1)

    def __call__(self):
        glCallList(self.display_list_id)

class DisplayListGenerator:
    def __enter__(self):
        dl = DisplayList()
        glNewList(dl.display_list_id, GL_COMPILE)
        return dl

    def __exit__(self, type, value, traceback):
        glEndList()

class ViewportAs:
    def __init__(self, w, h, viewport_w=None, viewport_h=None, invert_y=False):
        self.w = w
        self.h = h
        self.viewport_w = viewport_w if viewport_w else w
        self.viewport_h = viewport_h if viewport_h else h
        self.invert_y = False

    def __enter__(self):
        self.old_viewport = list(glGetFloatv(GL_VIEWPORT))

        glViewport(0, 0, self.viewport_w, self.viewport_h)
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        if not self.invert_y:
            glOrtho(0, self.w, 0, self.h, 0, 1)
        else:
            glOrtho(0, self.w, self.h, 0, 0, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        return self

    def __exit__(self, type, value, traceback):
        viewport = self.old_viewport
        glMatrixMode(GL_PROJECTION)

        glPopMatrix()
        glViewport(int(viewport[0]), int(viewport[1]), int(viewport[2]), int(viewport[3]))
        glMatrixMode(GL_MODELVIEW)