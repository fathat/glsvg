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