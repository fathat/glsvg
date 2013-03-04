import re
import svg_constants

re_list_parser = re.compile("([A-Za-z]|-?[0-9]+\.?[0-9]*(?:e-?[0-9]*)?)")

def parse_list(string):
    return re_list_parser.findall(string)

def parse_style(string):
    s_dict = {}
    for item in string.split(';'):
        if ':' in item:
            key, value = item.split(':')
            s_dict[key.strip()] = value.strip()
    return s_dict

def parse_float(txt):
    if txt.endswith('%'):
        pct = float(txt[:-1])/100.0
        return pct
    elif txt.endswith('px') or txt.endswith('pt'):
        return float(txt[:-2])
    else:
        return float(txt)

def parse_transform(txt):
    pass

def parse_color(c, default=None):
    if not c:
        return default
    if c == 'none':
        return None

    c = c.strip()

    if c in svg_constants.named_colors:
        c = svg_constants.named_colors[c]

    if c.startswith('rgb'):
        start = c.index('(')
        end = c.index(')')
        parts = c[start+1:end].split(',')
        r, g, b = tuple(int(p.strip()) for p in parts)
        return [r,g,b,255]

    if c[0] == '#': c = c[1:]
    if c.startswith('url(#'):
        return c[5:-1]
    try:
        a=255
        if len(c) == 8:
            r = int(c[0:2], 16)
            g = int(c[2:4], 16)
            b = int(c[4:6], 16)
            a = int(c[6:8], 16)
        elif len(c) == 6:
            r = int(c[0:2], 16)
            g = int(c[2:4], 16)
            b = int(c[4:6], 16)
        elif len(c) == 3:
            r = int(c[0], 16) * 17
            g = int(c[1], 16) * 17
            b = int(c[2], 16) * 17
        else:
            raise Exception("Incorrect length for color " + str(c) + " length " + str(len(c)))
        return [r,g,b,a]
    except Exception, ex:
        print 'Exception parsing color', ex
        return None
        