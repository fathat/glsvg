Intro
=====

glSVG is a lightweight python library for reading and rendering SVG files
in OpenGL.

Usage
-----

A really simple example ::

    import glsvg

    # initialize opengl context
    # ...

    # load svg file
    svg_doc = glsvg.SVGDoc(filename)

    # draw svg file
    svg_doc.draw(x,y)

Requirements
------------

 - PyOpenGL
