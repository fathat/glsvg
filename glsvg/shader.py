from OpenGL.GL import *
from OpenGL.GL.ARB import *

active_shader = None


class Shader(object):

    """An OpenGL shader object"""
    def __init__(self, shader_type, src=None, name="(unnamed shader)"):
        self.shader_object = glCreateShader(shader_type)
        self.name = name
        self.program = None

        if src:
            self.source(src)
            self.compile()
    
    def __del__(self):
        if self.program:
            self.program.detach(self)
            self.program = None
        glDeleteShader(self.shader_object)
    
    def source(self, source_string):
        glShaderSource(self.shader_object, source_string)
    
    def compile(self):
        glCompileShader(self.shader_object)
        return_val = glGetShaderiv(self.shader_object, GL_COMPILE_STATUS)

        if return_val:
            print "%s compiled successfuly." % (self.name)
        else:
            print "Compile failed on shader %s: " % (self.name)
            self.print_info_log()

    def info_log(self):
        glGetProgramInfoLog(self.shader_object)

    def print_info_log(self):
        print self.info_log()


class UniformVar(object):
    def __init__(self, set_function, name, *args ):
        self.set_function = set_function
        self.name = name
        self.values = args
    
    def set(self):
        self.set_function( self.name, *self.values )


class Program(object):
    """An OpenGL shader program"""
    def __init__(self, shaders=None):
        self.program_object = glCreateProgram()
        self.shaders = []
        self.uniform_vars = {}

        if shaders:
            for s in shaders:
                self.attach(s)
            self.link()
            self.use()
            self.stop()
    
    def __del__(self):
        glDeleteProgram( self.program_object)
    
    def attach(self, shader):
        self.shaders.append(shader)
        shader.program = self
        glAttachShader(self.program_object, shader.shader_object)
    
    def detach(self, shader):
        self.shaders.remove(shader)
        glDetachShader(self.program_object, shader.shader_object)
        print "Shader detached"
    
    def link(self):
        glLinkProgram(self.program_object)
    
    def use(self):
        global active_shader
        active_shader = self
        glUseProgram( self.program_object )
        self.set_vars()

    def stop(self):
        global active_shader
        glUseProgram( 0 )
        active_shader = None

    def uniformi( self, name, *args ):
        argf = {1: glUniform1i,
                2: glUniform2i,
                3: glUniform3i,
                4: glUniform4i}
        f = argf[len(args)]

        def _set_uniform(name, *args):
            location = glGetUniformLocation(self.program_object, name)
            f(location, *args)

        self.uniform_vars[name] = UniformVar(_set_uniform, name, *args)
        if self == active_shader:
            self.uniform_vars[name].set()
    
    def uniformf(self, name, *args):
        argf = {1: glUniform1f,
                2: glUniform2f,
                3: glUniform3f,
                4: glUniform4f}
        f = argf[len(args)]

        def _set_uniform(name, *args):
            location = glGetUniformLocation(self.program_object, name)
            f(location, *args)

        self.uniform_vars[name] = UniformVar(_set_uniform, name, *args)
        if self == active_shader:
            self.uniform_vars[name].set()
    
    def uniform_matrixf(self, name, transpose, values):
        argf = {4: glUniformMatrix2fv,
                9: glUniformMatrix3fv,
                16: glUniformMatrix4fv}
        f = argf[len(values)]

        def _set_uniform(name, values):
            location = glGetUniformLocation(self.program_object, name)
            f(location, 1, transpose, values)

        self.uniform_vars[name] = UniformVar(_set_uniform, name, values)
        if self == active_shader:
            self.uniform_vars[name].set()
    
    def set_vars(self):
        for name, var in self.uniform_vars.iteritems():
            var.set()
    
    def print_info_log(self):
        print glGetInfoLog(self.program_object)


def make_ps_from_src(name, src):
    return make_shader_from_src(name, src, GL_FRAGMENT_SHADER)


def make_vs_from_src(name, src):
    return make_shader_from_src(name, src, GL_VERTEX_SHADER)


def make_shader_from_src(name, src, shader_type):
    return Shader(shader_type, src=src, name=name)


def make_program_from_src_files(vertex_shader_name, pixel_shader_name):
    with open(vertex_shader_name, "r") as f:
        vs_src = f.tostring()
    with open(pixel_shader_name, "r") as f:
        ps_src = f.tostring()
    return make_program_from_src(vertex_shader_name, pixel_shader_name, vs_src, ps_src)


def make_program_from_src(vs_name, ps_name, vertex_shader_src, pixel_shader_src):
    vs = make_vs_from_src(vs_name, vertex_shader_src)
    ps = make_ps_from_src(ps_name, pixel_shader_src)
    p = Program([vs, ps])
    return p


def disable_shaders():
    global active_shader
    glUseProgram(0)
    active_shader = None
