__author__ = 'Ian'
import OpenGL.GL as gl


class Texture2D:

    def __init__(self, w, h, wrap=True):

        self.width = w
        self.height = h
        self.id = gl.glGenTextures(1)
        print "texture id", self.id

        self.bind()
        gl.glTexEnvf(gl.GL_TEXTURE_ENV, gl.GL_TEXTURE_ENV_MODE, gl.GL_MODULATE)

        gl.glTexParameterf(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
        gl.glTexParameterf(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)

        wrap_mode = gl.GL_REPEAT if wrap else gl.GL_CLAMP
        gl.glTexParameterf(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, wrap_mode)
        gl.glTexParameterf(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, wrap_mode)

        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, self.width, self.height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)

        print "Tex OK? ", gl.glGetError() == gl.GL_NO_ERROR
        self.unbind()

    def bind(self):
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.id)

    def unbind(self):
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)

    def __enter__(self):
        self.bind()
        return self

    def __exit__(self, type, value, traceback):
        self.unbind()
        pass


class RenderBufferObject:
    def __init__(self, w, h):
        self.id = gl.glGenRenderbuffers(1);
        self.width, self.height = w, h

        self.bind()
        gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_DEPTH24_STENCIL8, w, h)
        self.unbind()

    def bind(self):
        gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self.id)

    def unbind(self):
        gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, 0)


class RenderTarget:
    def __init__(self, w, h, depth_and_stencil=True):
        self.texture = Texture2D(w, h)
        self.id = gl.glGenFramebuffers(1)
        self.bind()
        self.depth_stencil = None
        if depth_and_stencil:
            self.depth_stencil = RenderBufferObject(w, h)

        gl.glFramebufferTexture2D(
            gl.GL_FRAMEBUFFER,
            gl.GL_COLOR_ATTACHMENT0,
            gl.GL_TEXTURE_2D,
            self.texture.id,
            0)

        self.ok = self.check_status()

        self.unbind()

    def check_status(self):
        status = gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)
        if status == gl.GL_FRAMEBUFFER_COMPLETE:
            print "Framebuffer complete"
            return True
        else:
            print "Render target error: " + str(status)
            return False

    def bind(self):
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.id)

    def unbind(self):
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)

    def __enter__(self):
        self.bind()
        return self

    def __exit__(self, type, value, traceback):
        self.unbind()
        pass