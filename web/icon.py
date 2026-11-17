#!/usr/bin/env python3
"""The web page's icon: the game's 15x15 phone icon, with a black border around the spider except at the top (where
its thread hangs from), scaled up with crisp pixels by a whole number to about 80% of 256x256 (as large as the other
games' square icons look on the page), with smoothly rounded corners.

    web/icon.py <icon.png> <out.png>
"""

import sys

from PIL import Image, ImageDraw

SIZE = 256
icon = Image.open(sys.argv[1]).convert("RGBA")
# 1 pixel on the left and right and 2 at the bottom, so that it stays square
padded = Image.new("RGBA", (icon.width + 2, icon.height + 2), (0, 0, 0, 255))
padded.paste(icon, (1, 0))
icon = padded
scale = round(SIZE * 0.82 / max(icon.size))
icon = icon.resize((icon.width * scale, icon.height * scale), Image.NEAREST)

# Rounded corners, antialiased: the mask is drawn 4 times larger, then scaled down
radius = round(min(icon.size) * 0.2)
big = Image.new("L", (icon.width * 4, icon.height * 4))
ImageDraw.Draw(big).rounded_rectangle((0, 0, big.width - 1, big.height - 1), radius=radius * 4, fill=255)
mask = big.resize(icon.size, Image.LANCZOS)
icon.putalpha(Image.composite(icon.getchannel("A"), Image.new("L", icon.size), mask))

out = Image.new("RGBA", (SIZE, SIZE))
out.paste(icon, ((SIZE - icon.width) // 2, (SIZE - icon.height) // 2))
out.save(sys.argv[2])
