from parser_utils import *
from matrix import *
import shader
import shaders


class GradientShaders:

    def __init__(self):
        self._radial_shader = None
        self._linear_shader = None

    @property
    def radial_shader(self):
        if not self._radial_shader:
            self._radial_shader = shader.make_program_from_src(
                                    "vs", "radial_ps",
                                    shaders.vertex, shaders.radial)
        return self._radial_shader

    @property
    def linear_shader(self):
        if not self._linear_shader:
            self._linear_shader = shader.make_program_from_src(
                                    "vs", "linear_ps",
                                    shaders.vertex, shaders.linear)
        return self._linear_shader

gradient_shaders = GradientShaders()


class GradientContainer(dict):
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.callback_dict = {}

    def call_me_on_add(self, callback, grad_id):
        '''
        The client wants to know when the gradient with id grad_id gets
        added.  So store this callback for when that happens.
        When the desired gradient is added, the callback will be called
        with the gradient as the first and only argument.
        '''
        cblist = self.callback_dict.get(grad_id, None)
        if cblist == None:
            cblist = [callback]
            self.callback_dict[grad_id] = cblist
            return
        cblist.append(callback)

    def update(self, *args, **kwargs):
        raise NotImplementedError('update not done for GradientContainer')

    def __setitem__(self, key, val):
        dict.__setitem__(self, key, val)
        callbacks = self.callback_dict.get(key, [])
        for callback in callbacks:
            callback(val)
        
    
class Gradient(object):
    def __init__(self, element, svg):
        self.element = element
        self.stops = {}
        for e in element.getiterator():
            if e.tag.endswith('stop'):
                style = parse_style(e.get('style', ''))
                color = parse_color(e.get('stop-color'))
                if 'stop-color' in style:
                    color = parse_color(style['stop-color'])
                color[3] = int(float(e.get('stop-opacity', '1')) * 255)
                if 'stop-opacity' in style:
                    color[3] = int(float(style['stop-opacity']) * 255)
                self.stops[float(e.get('offset'))] = color
        self.stops = sorted(self.stops.items())
        self.svg = svg
        self.grad_transform = Matrix(element.get('gradientTransform'))
        self.inv_transform = Matrix(element.get('gradientTransform')).inverse()

        inherit = self.element.get('{http://www.w3.org/1999/xlink}href')
        parent = None
        delay_params = False
        if inherit:
            parent_id = inherit[1:]
            parent = self.svg._gradients.get(parent_id, None)
            if parent == None:
                self.svg._gradients.call_me_on_add(self.tardy_gradient_parsed, parent_id)
                delay_params = True
                return
        if not delay_params:
            self.get_params(parent)

    def sample(self, pt):
        if not self.stops: return [255, 0, 255, 255]
        t = self.grad_value(self.inv_transform(pt))
        if t < self.stops[0][0]:
            return self.stops[0][1]
        for n, top in enumerate(self.stops[1:]):
            bottom = self.stops[n]
            if t <= top[0]:
                u = bottom[0]
                v = top[0]
                alpha = (t - u)/(v - u)
                return [int(x[0] * (1 - alpha) + x[1] * alpha) for x in zip(bottom[1], top[1])]
        return self.stops[-1][1]

    def get_params(self, parent):
        for param in self.params:
            v = None
            if parent:
                v = getattr(parent, param, None)
            my_v = self.element.get(param)
            if my_v:
                v = float(my_v)
            if v:
                setattr(self, param, v)

    def tardy_gradient_parsed(self, gradient):
        self.get_params(gradient)
        
    def apply_shader(self, transform):
        pass
    
    def unapply_shader(self):
        pass


class LinearGradient(Gradient):
    params = ['x1', 'x2', 'y1', 'y2', 'stops']

    def grad_value(self, pt):
        return ((pt[0] - self.x1) * (self.x2 - self.x1) + (pt[1] - self.y1) * (self.y2 - self.y1)) \
            / ((self.x1 - self.x2) ** 2 + (self.y1 - self.y2) ** 2)
    
    def apply_shader(self, transform):
        if not self.stops: return
        gradient_shaders.linear_shader.use()
        gradient_shaders.linear_shader.uniformf("start", self.x1, self.y1)
        gradient_shaders.linear_shader.uniformf("end", self.x2, self.y2)
        gradient_shaders.linear_shader.uniform_matrixf("worldTransform", False, svg_matrix_to_gl_matrix(transform))
        gradient_shaders.linear_shader.uniform_matrixf("gradientTransform",
                                     False,
                                     svg_matrix_to_gl_matrix(self.grad_transform))
        stop_points = []
        for stop in self.stops:
            stop_point, color = stop
            stop_points.append(stop_point)
        while len(stop_points) < 5:
            stop_points.append(0.0)
        
        #can't support more than 5 of these bad boys..
        if len(stop_points) > 5:
            stop_points = stop_points[:5]

        gradient_shaders.linear_shader.uniformf("stops", *(stop_points[1:]))
        
        def get_stop(i):
            return self.stops[i] if i < len(self.stops) else (1.0, [0.0, 0.0, 0.0, 0.0])
        
        for i in xrange(len(stop_points)):
            stop_point, color = get_stop(i)
            color = tuple(float(x)/255.0 for x in color)
            gradient_shaders.linear_shader.uniformf("stop" + str(i), *color)
    
    def unapply_shader(self):
        if not self.stops: return
        gradient_shaders.linear_shader.stop()


class RadialGradient(Gradient):
    params = ['cx', 'cy', 'r', 'stops']

    def grad_value(self, pt):
        return math.sqrt((pt[0] - self.cx) ** 2 + (pt[1] - self.cy) ** 2)/self.r
        
    def apply_shader(self, transform):
        if not self.stops: return
        gradient_shaders.radial_shader.use()
        gradient_shaders.radial_shader.uniformf("radius", self.r)
        gradient_shaders.radial_shader.uniformf("center", self.cx, self.cy)
        gradient_shaders.radial_shader.uniform_matrixf("worldTransform", False, svg_matrix_to_gl_matrix(transform))
        gradient_shaders.radial_shader.uniform_matrixf("gradientTransform",
                                     False,
                                     svg_matrix_to_gl_matrix(self.grad_transform))
        gradient_shaders.radial_shader.uniform_matrixf("invGradientTransform",
                                     False,
                                     svg_matrix_to_gl_matrix(self.inv_transform))
        stop_points = []
        for stop in self.stops:
            stop_point, color = stop
            stop_points.append(stop_point)
        
        while len(stop_points) < 5:
            stop_points.append(0.0)
        
        #can't support more than 4 of these bad boys..
        if len(stop_points) > 5:
            stop_points = stop_points[:5]

        gradient_shaders.radial_shader.uniformf("stops", *(stop_points[1:]))
        
        def get_stop(i):
            return self.stops[i] if i < len(self.stops) else (1.0, [0.0, 0.0, 0.0, 0.0])
        
        for i in xrange(len(stop_points)):
            stop_point, color = get_stop(i)
            color = tuple(float(x)/255.0 for x in color)
            gradient_shaders.radial_shader.uniformf("stop" + str(i), *color)
    
    def unapply_shader(self):
        if not self.stops: return
        gradient_shaders.radial_shader.stop()
