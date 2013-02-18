glsvg
===============================================

A python library for parsing and displaying SVG files
using opengl, with a focus on being usable for games.

-----------------------------------------------
Usage
-----------------------------------------------
```python
    import glsvg

    # initialize opengl context
    # ...

    # load svg file
    svg_doc = glsvg.SVG(filename)

    # draw svg file
    svg_doc.draw(x,y)
```

-----------------------------------------------
Status
-----------------------------------------------

Requires:
 - PyOpenGL

Supported game libraries:
 - PyGame
 - Pyglet

Supported SVG features:
 - All SVG path commands (arc/curves/lines/etc.)
 - Basic SVG shapes (rectangle, ellipse)
 - Per-Pixel Linear and Radial Gradients
 - Parsable color names
 - Variable line widths and miter/bevel joints

SVG Features In Progress:
 - SVG patterns
 - SVG effects (Drop shadow, blur, etc.)
 - More sophisticated line effects (patterns, arc joints, etc.)

Likely to be not supported:
 - Animation
 - Text (this would be likely to require too many extra dependencies for fonts, but an easy workaround is to convert text
objects to paths in your editor, ie Inkscape or Illustrator)
 - CSS based style tags

-----------------------------------------------
Credits:
-----------------------------------------------

Based on the squirtle mini-library by Martin O'Leary:

 http://www.pyweek.org/d/1783/

