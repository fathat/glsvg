__author__ = 'Ian'
from OpenGL.GL import *


class Texture2D:

    def __init__(self, w, h, wrap=True):

        self.width = w
        self.height = h
        self.id = glGenTextures(1)
        print "texture id", self.id

        self.bind()
        glTexEnvf( GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE)

        glTexParameterf( GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameterf( GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)

        wrap_mode = GL_REPEAT if wrap else GL_CLAMP
        glTexParameterf( GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, wrap_mode)
        glTexParameterf( GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, wrap_mode)

        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, self.width, self.height, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)

        print "Tex OK? ", glGetError() == GL_NO_ERROR
        self.unbind()

    def bind(self):
        glBindTexture(GL_TEXTURE_2D, self.id)

    def unbind(self):
        glBindTexture(GL_TEXTURE_2D, 0)

    def __enter__(self):
        self.bind()
        return self

    def __exit__(self, type, value, traceback):
        self.unbind()
        pass


class RenderBufferObject:
    def __init__(self, w, h):
        self.id = glGenRenderbuffers(1);
        self.width, self.height = w, h

        self.bind()
        glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH24_STENCIL8, w, h)
        self.unbind()

    def bind(self):
        glBindRenderbuffer(GL_RENDERBUFFER, self.id)

    def unbind(self):
        glBindRenderbuffer(GL_RENDERBUFFER, 0)


class RenderTarget:
    def __init__(self, w, h, depth_and_stencil=True):
        self.texture = Texture2D(w, h)
        self.id = glGenFramebuffers(1)
        self.bind()
        self.depth_stencil = None
        if depth_and_stencil:
            self.depth_stencil = RenderBufferObject(w, h)

        glFramebufferTexture2D(
            GL_FRAMEBUFFER,
            GL_COLOR_ATTACHMENT0,
            GL_TEXTURE_2D,
            self.texture.id,
            0)

        self.ok = self.check_status()

        self.unbind()

    def check_status(self):
        status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
        if status == GL_FRAMEBUFFER_COMPLETE:
            print "Framebuffer complete"
            return True
        else:
            print "Render target error: " + str(status)
            return False

    def bind(self):
        glBindFramebuffer(GL_FRAMEBUFFER, self.id)

    def unbind(self):
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

    def __enter__(self):
        self.bind()
        return self

    def __exit__(self, type, value, traceback):
        self.unbind()
        pass