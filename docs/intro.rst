Intro
==============

glSVG is a lightweight python library for reading and rendering SVG files
in OpenGL.

Usage
------------------

A really simple example ::

    import glsvg

    # initialize opengl context
    # ...

    # load svg file
    svgObj = glsvg.SVG(filename)

    # draw svg file
    svgObj.draw(x,y)





Requirements
---------
 - PyOpenGL


