GLSVG TODO LIST
============================

DONE:
 - [x] Path
 - [x] Rect
 - [x] Ellipse
 - [x] Circle
 - [x] Line
 - [x] Polyline
 - [x] Fill-rule (nonzero & evenodd)
 - [x] Move style to own class

Partially done:
 - [*] Patterns

TODO:
 - [ ] Support the "use" element
 - [ ] Support creating a texture from SVG file
 - [ ] Support moving interior SVG path transforms
 - [ ] Support rendering interior SVG path transforms separately
 - [ ] Support stroke-dasharray
 - [ ] Draw lines as triangle strip (instead of triangle fan)
 - [ ] Clipping paths
 - [ ] Masking

MAYBE:
 - [ ] Text tag. Would need some sort of good font library to do this.
 - [ ] Marker tag. Useful?
 - [ ] color-rendering tag for optimization. (Maybe fall back to vertex coloring on optimize for speed?)
 - [ ] Raster images. Useful?