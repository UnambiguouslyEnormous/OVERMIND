#!/usr/bin/env python3
"""Regenerate original Stanley contact sheet from the MIT vector source. No display needed.
Usage: python3 tools/render_stanley.py /tmp/stanley.png (or .svg)
The runtime draws vectors directly and needs no generated asset file.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from overmind.stanley import STATES, stanley_svg
from gi.repository import GdkPixbuf

path=Path(sys.argv[1] if len(sys.argv)>1 else '/tmp/stanley.png')
parts=['<svg xmlns="http://www.w3.org/2000/svg" width="880" height="370"><rect width="880" height="370" fill="#171f24"/>']
for i,state in enumerate(sorted(STATES)):
    scene=stanley_svg(state,.38)
    parts.append(f'<g transform="translate({(i%4)*220},{(i//4)*185})">{scene}<text x="65" y="173" fill="#cce5d9" font-family="sans-serif" font-size="15">{state}</text></g>')
parts.append('</svg>');svg=''.join(parts)
if path.suffix=='.svg':path.write_text(svg)
else:
    loader=GdkPixbuf.PixbufLoader.new_with_type('svg');loader.write(svg.encode());loader.close();loader.get_pixbuf().savev(str(path),'png',[],[])
print(path)
