from parser_utils import *
from OpenGL.GL import *


class Matrix(object):
    def __init__(self, string=None):
        self.values = [1, 0, 0, 1, 0, 0]
        if isinstance(string, str):
            string = string.strip()
            if string.startswith('matrix('):
                self.values = [float(x) for x in parse_list(string[7:-1])]
            elif string.startswith('translate('):
                x, y = [float(x) for x in parse_list(string[10:-1])]
                self.values = [1, 0, 0, 1, x, y]
            elif string.startswith('scale('):
                sx, sy = [float(x) for x in parse_list(string[6:-1])]
                self.values = [sx, 0, 0, sy, 0, 0]           
        elif string is not None:
            self.values = list(string)

    def __enter__(self):
        glPushMatrix()
        glMultMatrixf(self.to_mat4())
        return self

    def __exit__(self, type, value, traceback):
        glPopMatrix()

    def __call__(self, other):
        return (self.values[0] * other[0] + self.values[2] * other[1] + self.values[4],
                self.values[1] * other[0] + self.values[3] * other[1] + self.values[5])
    
    def __str__(self):
        return str(self.values)
    
    def to_mat4(self):
        v = self.values
        return [v[0], v[1], 0.0, 0.0,
                v[2], v[3], 0.0, 0.0,
                0.0,  0.0,  1.0, 0.0,
                v[4], v[5], 0.0, 1.0]
    
    def inverse(self):
        d = float(self.values[0] * self.values[3] - self.values[1] * self.values[2])
        return Matrix([self.values[3] / d, -self.values[1] / d, -self.values[2] / d, self.values[0] / d,
                       (self.values[2] * self.values[5] - self.values[3] * self.values[4]) / d,
                       (self.values[1] * self.values[4] - self.values[0] * self.values[5]) / d])

    def __mul__(self, other):
        a, b, c, d, e, f = self.values
        u, v, w, x, y, z = other.values
        return Matrix([
            a * u + c * v,
            b * u + d * v,
            a * w + c * x,
            b * w + d * x,
            a * y + c * z + e,
            b * y + d * z + f])


class CurrentTransform:
    def __enter__(self):
        glPushMatrix()
        return self

    def __exit__(self, type, value, traceback):
        glPopMatrix()


def svg_matrix_to_gl_matrix(matrix):
    v = matrix.values
    return [v[0], v[1], 0.0, v[2], v[3], 0.0, v[4], v[5], 1.0]
