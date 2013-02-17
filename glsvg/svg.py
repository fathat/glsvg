"""GLSVG library for SVG rendering in PyOpenGL.

Example usage:
    $ import glsvg
    $ my_svg = glsvg.SVG('filename.svg')
    $ my_svg.draw(100, 200, angle=15)
    
"""

from OpenGL.GL import *

try:
    import xml.etree.ElementTree
    from xml.etree.cElementTree import parse
except:
    import elementtree.ElementTree
    from elementtree.ElementTree import parse

import re
import math
import string
import traceback

from svg_constants import *

from glutils import *
from matrix import *
from parser_utils import parse_color, parse_float, parse_style, parse_list
from gradient import *
from svg_path import SvgPath
from svg_pattern import *


class SVGConfig:
    def __init__(self):
        self.stencil_bits = glGetInteger(GL_STENCIL_BITS)
        self.has_framebuffer_objects = True
        self.allow_stencil = self.stencil_bits > 0
        self.bezier_points = BEZIER_POINTS
        self.circle_points = CIRCLE_POINTS

    def __repr__(self):
        return "<SVGConfig stencil_bits={0} fbo={1} circle_points={2} bezier_points={3}>".format(
            self.stencil_bits,
            self.has_framebuffer_objects,
            self.circle_points,
            self.bezier_points
        )


class SVG(object):
    """
    Opaque SVG image object.
    
    Users should instantiate this object once for each SVG file they wish to 
    render.
    
    """

    def __init__(self, filename, anchor_x=0, anchor_y=0, config=None):
        """Creates an SVG object from a .svg or .svgz file.
        
            `filename`: str
                The name of the file to be loaded.
            `anchor_x`: float
                The horizontal anchor position for scaling and rotations. Defaults to 0. The symbolic 
                values 'left', 'center' and 'right' are also accepted.
            `anchor_y`: float
                The vertical anchor position for scaling and rotations. Defaults to 0. The symbolic 
                values 'bottom', 'center' and 'top' are also accepted.
            `bezier_points`: int
                The number of line segments into which to subdivide Bezier splines. Defaults to 10.
            `circle_points`: int
                The number of line segments into which to subdivide circular and elliptic arcs. 
                Defaults to 10.
                
        """
        if not config:
            self.config = SVGConfig()
        else:
            self.config = config
        self.stencil_mask = 0
        self.n_tris = 0
        self.n_lines = 0
        self.path_lookup = {}
        self._paths = []
        self.patterns = {}
        self.filename = filename
        self._gradients = GradientContainer()
        self._generate_disp_list()
        self._anchor_x = anchor_x
        self._anchor_y = anchor_y

    def test_capabilities(self):
        return None

    def next_stencil_mask(self):
        self.stencil_mask += 1

        # if we run out of unique bits in stencil buffer,
        # clear stencils and restart
        if self.stencil_mask > (2**self.config.stencil_bits-1):
            self.stencil_mask = 1
            glStencilMask(0xFF)
            glClear(GL_STENCIL_BUFFER_BIT)

        return self.stencil_mask

    def is_stencil_enabled(self):
        return self.config.allow_stencil

    def register_pattern_part(self, pattern_id, pattern_svg_path):
        print "registering pattern"
        self.patterns[pattern_id].paths.append(pattern_svg_path)

    def _set_anchor_x(self, anchor_x):
        self._anchor_x = anchor_x
        if self._anchor_x == 'left':
            self._a_x = 0
        elif self._anchor_x == 'center':
            self._a_x = self.width * .5
        elif self._anchor_x == 'right':
            self._a_x = self.width
        else:
            self._a_x = self._anchor_x
    
    def _get_anchor_x(self):
        return self._anchor_x
    
    anchor_x = property(_get_anchor_x, _set_anchor_x)
    
    def _set_anchor_y(self, anchor_y):
        self._anchor_y = anchor_y
        if self._anchor_y == 'bottom':
            self._a_y = 0
        elif self._anchor_y == 'center':
            self._a_y = self.height * .5
        elif self._anchor_y == 'top':
            self._a_y = self.height
        else:
            self._a_y = self.anchor_y

    def _get_anchor_y(self):
        return self._anchor_y
        
    anchor_y = property(_get_anchor_y, _set_anchor_y)
    
    def _generate_disp_list(self):
        if open(self.filename, 'rb').read(3) == '\x1f\x8b\x08':  # gzip magic numbers
            import gzip
            f = gzip.open(self.filename, 'rb')
        else:
            f = open(self.filename, 'rb')
        self.tree = parse(f)
        self._parse_doc()

        # prepare all the patterns
        self.render_patterns()

        with DisplayListGenerator() as display_list:
            self.disp_list = display_list
            self.render()

    def draw(self, x, y, z=0, angle=0, scale=1):
        """Draws the SVG to screen.
        
        :Parameters
            `x` : float
                The x-coordinate at which to draw.
            `y` : float
                The y-coordinate at which to draw.
            `z` : float
                The z-coordinate at which to draw. Defaults to 0. Note that z-ordering may not 
                give expected results when transparency is used.
            `angle` : float
                The angle by which the image should be rotated (in degrees). Defaults to 0.
            `scale` : float
                The amount by which the image should be scaled, either as a float, or a tuple 
                of two floats (xscale, yscale).

        """

        with CurrentTransform():
            glTranslatef(x, y, z)
            if angle:
                glRotatef(angle, 0, 0, 1)
            if scale != 1:
                try:
                    glScalef(scale[0], scale[1], 1)
                except TypeError:
                    glScalef(scale, scale, 1)
            if self._a_x or self._a_y:
                glTranslatef(-self._a_x, -self._a_y, 0)

            self.disp_list()

    def render_patterns(self):
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        #clear out stencils
        if self.is_stencil_enabled():
            glStencilMask(0xFF)
            glClear(GL_STENCIL_BUFFER_BIT)

        for pattern in self.patterns.values():
            pattern.render()

    def _clear_stencils(self):
        glStencilMask(0xFF)
        glClear(GL_STENCIL_BUFFER_BIT)

    def render(self):
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        #clear out stencils
        if self.is_stencil_enabled():
            self._clear_stencils()
        for svg_path in self._paths:
            if not svg_path.is_pattern and not svg_path.is_pattern_part:
                svg_path.render()

    def _parse_doc(self):
        self._paths = []

        #get the height measurement... if it ends
        #with "cm" just sort of fake out some sort of
        #measurement (right now it adds a zero)
        wm = self.tree._root.get("width", '0')
        hm = self.tree._root.get("height", '0')
        if 'cm' in wm:
            wm = wm.replace('cm', '0')
        if 'cm' in hm:
            hm = hm.replace('cm', '0')

        self.width = parse_float(wm)
        self.height = parse_float(hm)
        #self.transform = Matrix([1, 0, 0, 1, 0, 0])

        if self.tree._root.get("viewBox"):
            x, y, w, h = (parse_float(x) for x in parse_list(self.tree._root.get("viewBox")))
            self.height = h
            self.width = w

        self.opacity = 1.0
        for e in self.tree._root.getchildren():
            try:
                self._parse_element(e)
            except Exception as ex:
                print 'Exception while parsing element', e
                raise

    def _is_path_tag(self, e):
        return (e.tag.endswith('path')
                or e.tag.endswith('rect')
                or e.tag.endswith('polyline') or e.tag.endswith('polygon')
                or e.tag.endswith('line')
                or e.tag.endswith('circle') or e.tag.endswith('ellipse'))

    def _is_rect_tag(self, e):
        return e.tag.endswith('rect')

    def _parse_element(self, e, parent_scope=None):
        scope = _AttributeScope(e, parent_scope)

        if self._is_path_tag(e):
            path = SvgPath(self, scope, e)
            self._paths.append(path)
            self.path_lookup[scope.path_id] = path
        elif e.tag.endswith("text"):
            self._warn("Text tag not supported")
        elif e.tag.endswith('linearGradient'):
            self._gradients[e.get('id')] = LinearGradient(e, self)
        elif e.tag.endswith('radialGradient'):
            self._gradients[e.get('id')] = RadialGradient(e, self)
        elif e.tag.endswith('pattern'):
            self.patterns[e.get('id')] = Pattern(e, self)
        for c in e.getchildren():
            try:
                self._parse_element(c, scope)
            except Exception, ex:
                print 'Exception while parsing element', c
                raise

    def _warn(self, message):
        print "Warning: SVG Parser (%s) - %s" % (self.filename, message)



class _AttributeScope:
    def __init__(self, element, parent):
        self.parent = parent
        self.is_pattern = element.tag.endswith("pattern")
        self.is_pattern_part = False

        if parent:
            self.fill = parent.fill
            self.stroke = parent.stroke

            if parent.is_pattern:
                self.is_pattern_part = True
        else:
            self.fill = DEFAULT_FILL
            self.stroke = DEFAULT_STROKE
        self.stroke_width = None

        if parent:
            self.transform = parent.transform * Matrix(element.get('transform'))
        else:
            self.transform = Matrix(element.get('transform', None))

            if not self.transform:
                self.transform = Matrix([1, 0, 0, 1, 0, 0])

        self.opacity = 1.0

        self.tag_type = element.tag

        self.fill = parse_color(element.get('fill'), self.fill)
        self.fill_rule = 'nonzero'

        self.stroke = parse_color(element.get('stroke'), self.stroke)
        self.stroke_width = float(element.get('stroke-width', 1.0))

        self.opacity *= float(element.get('opacity', 1))
        fill_opacity = float(element.get('fill-opacity', 1))
        stroke_opacity = float(element.get('stroke-opacity', 1))
        self.path_id = element.get('id', '')
        self.path_title = element.findtext('{%s}title' % (XMLNS,))
        self.path_description = element.findtext('{%s}desc' % (XMLNS,))

        style = element.get('style')
        if style:
            style_dict = parse_style(style)
            if 'fill' in style_dict:
                self.fill = parse_color(style_dict['fill'])
            if 'fill-opacity' in style_dict:
                fill_opacity *= float(style_dict['fill-opacity'])
            if 'stroke' in style_dict:
                self.stroke = parse_color(style_dict['stroke'])
            if 'stroke-opacity' in style_dict:
                stroke_opacity *= float(style_dict['stroke-opacity'])
            if 'stroke-width' in style_dict:
                sw = style_dict['stroke-width']
                self.stroke_width = parse_float(sw)
            if 'opacity' in style_dict:
                fill_opacity *= float(style_dict['opacity'])
                stroke_opacity *= float(style_dict['opacity'])
            if 'fill-rule' in style_dict:
                self.fill_rule = style_dict['fill-rule']
        if isinstance(self.stroke, list):
            self.stroke[3] = int(self.opacity * stroke_opacity * self.stroke[3])
        if isinstance(self.fill, list):
            self.fill[3] = int(self.opacity * fill_opacity * self.fill[3])
