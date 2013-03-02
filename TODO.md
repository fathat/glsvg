GLSVG TODO LIST
============================

Features:
 - [x] Path
 - [x] Rect
 - [x] Ellipse
 - [x] Circle
 - [x] Line
 - [x] Polyline
 - [x] Fill-rule (nonzero & evenodd)
 - [x] Inherited styles
 - [x] "use" element
 - [x] stroke-dasharray
 - [ ] stroke-linecap ("butt", "round", "square")
 - [ ] stroke-linejoin
 - [x] Draw lines as triangle strip (instead of triangle fan)


 - [*] Patterns
   - [ ] userSpaceOnUse
   - [x] objectBoundingBox

TODO:
 - [ ] Support creating a texture from SVG file
 - [ ] Support moving interior SVG path transforms
 - [ ] Support rendering interior SVG path transforms separately
 - [ ] Rounded rectangles
 - [ ] Clipping paths
 - [ ] Masking
 - [ ] Radial gradient focal points

MAYBE:
 - [ ] Text tag. Would need some sort of good font library to do this.
 - [ ] Marker tag. Useful?
 - [ ] color-rendering tag for optimization. (Maybe fall back to vertex coloring on optimize for speed?)
 - [ ] Raster images. Useful?