from OpenGL.GL import *
from OpenGL.GL.ARB import *

activeShader = None

class Shader(object):
    """An OpenGL shader object"""
    def __init__( self, shader_type, src=None, name="(unnamed shader)" ):
        self.shaderObject = glCreateShader( shader_type )
        self.name = name
        self.program = None

        if src:
            self.source(src)
            self.compile()
    
    def __del__ (self ):
        if self.program:
            self.program.detach( self )
            self.program = None
        glDeleteShader( self.shaderObject )
    
    def source( self, source_string ):
        glShaderSource(self.shaderObject, source_string)
    
    def compile( self ):
        glCompileShader( self.shaderObject )
        rval = glGetShaderiv( self.shaderObject, GL_COMPILE_STATUS)

        if rval:
            print "%s compiled successfuly." % (self.name)
        else:
            print "Compile failed on shader %s: " % (self.name)
            self.print_info_log( )
    

    def info_log( self ):
        glGetProgramInfoLog(self.shaderObject)

    def print_info_log( self ):
        print self.info_log()

class UniformVar(object):
    def __init__(self, set_function, name, *args ):
        self.setFunction = set_function
        self.name = name
        self.values = args
    
    def set(self):
        self.setFunction( self.name, *self.values )

class Program( object ):
    """An OpenGL shader program"""
    def __init__(self, shaders=None):
        self.programObject = glCreateProgram()
        self.shaders = []
        self.uniformVars = {}

        if shaders:
            for s in shaders:
                self.attach(s)
            self.link()
            self.use()
            self.stop()
    
    def __del__(self):
        glDeleteProgram( self.programObject)
    
    def attach( self, shader ):
        self.shaders.append( shader )
        shader.program = self
        glAttachShader( self.programObject, shader.shaderObject )
    
    def detach( self, shader ):
        self.shaders.remove( shader )
        glDetachShader( self.programObject, shader.shaderObject )
        print "Shader detached"
    
    def link( self ):
        glLinkProgram( self.programObject )
    
    def use( self ):
        global activeShader
        activeShader = self
        glUseProgram( self.programObject )
        self.set_vars()

    def stop(self):
        global activeShader
        glUseProgram( 0 )
        activeShader = None

    def uniformi( self, name, *args ):
        argf = {1 : glUniform1i,
                2 : glUniform2i,
                3 : glUniform3i,
                4 : glUniform4i}
        f = argf[len(args)]
        def _set_uniform( name, *args ):
            location = glGetUniformLocation( self.programObject, name )
            f(location, *args)
        self.uniformVars[name] = UniformVar(_set_uniform, name, *args )
        if self == activeShader:
            self.uniformVars[name].set()      
    
    def uniformf( self, name, *args ):
        argf = {1 : glUniform1f,
                2 : glUniform2f,
                3 : glUniform3f,
                4 : glUniform4f}
        f = argf[len(args)]
        def _set_uniform( name, *args ):
            location = glGetUniformLocation( self.programObject, name )
            f(location, *args)
        self.uniformVars[name] = UniformVar(_set_uniform, name, *args )
        if self == activeShader:
            self.uniformVars[name].set()
    
    def uniform_matrixf(self, name, transpose, values):
        argf = {4 : glUniformMatrix2fv,
                9 : glUniformMatrix3fv,
                16 : glUniformMatrix4fv}
        f = argf[len(values)]
        def _set_uniform( name, values ):
            location = glGetUniformLocation( self.programObject, name )
            #matrix_type = ctypes.c_float * len(values)
            #matrix = matrix_type(*values)
            f(location, 1, transpose, values)
        self.uniformVars[name] = UniformVar(_set_uniform, name, values )
        if self == activeShader:
            self.uniformVars[name].set()
    
    def set_vars(self):
        for name, var in self.uniformVars.iteritems():
            var.set()
    
    def print_info_log( self ):
        print glGetInfoLog (self.programObject )

def make_ps_from_src (name, src ):
    return make_shader_from_src(name, src, GL_FRAGMENT_SHADER )

def make_vs_from_src (name, src ):
    return make_shader_from_src(name, src, GL_VERTEX_SHADER )

def make_shader_from_src(name, src, shader_type ):
    return Shader( shader_type, src=src, name=name )

def make_program_from_src_files( vertex_shader_name, pixel_shader_name ):
    with open( vertex_shader_name, "r") as file:
        vs_src = file.tostring()
    with open( pixel_shader_name, "r") as file:
        ps_src = file.tostring()
    return make_program_from_src( vs_src, ps_src )

def make_program_from_src(vsname, psname, vertex_shader_src, pixel_shader_src ):
    vs = make_vs_from_src(vsname, vertex_shader_src )
    ps = make_ps_from_src(psname, pixel_shader_src )
    p = Program([vs, ps])
    return p

def disable_shaders():
    global activeShader 
    glUseProgram( 0 )
    activeShader = None
