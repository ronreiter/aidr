#!/usr/bin/env python3
"""Build aidr.icns — a rounded brand tile with the ai;dr bubble glyph on it.

Rasterises with AppKit (which renders SVG natively), so the build needs no
separate SVG converter. From the repo root:

    poetry run python scripts/make_icon.py
"""

import os
import subprocess
import sys
import tempfile

from AppKit import (
    NSBezierPath,
    NSBitmapImageRep,
    NSColor,
    NSGraphicsContext,
    NSImage,
    NSPNGFileType,
)
from Foundation import NSData, NSMakeRect, NSMakeSize, NSZeroRect

# The bubble-text glyph (Tabler, MIT), filled white for the tile.
GLYPH = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white">'
    '<path d="M12.4 2l.253 .005a6.34 6.34 0 0 1 5.235 3.166l.089 .163l.178 .039'
    "a6.33 6.33 0 0 1 4.254 3.406l.105 .228a6.334 6.334 0 0 1 -5.74 8.865l-.144 -.002l-.037 .052"
    "a5.26 5.26 0 0 1 -5.458 1.926l-.186 -.051l-3.435 2.06a1 1 0 0 1 -1.508 -.743l-.006 -.114v-2.435"
    "l-.055 -.026a3.67 3.67 0 0 1 -1.554 -1.498l-.102 -.199a3.67 3.67 0 0 1 -.312 -2.14l.038 -.21"
    "l-.116 -.092a5.8 5.8 0 0 1 -1.887 -6.025l.071 -.238a5.8 5.8 0 0 1 5.42 -4.004h.157l.15 -.165"
    "a6.33 6.33 0 0 1 4.33 -1.963zm1.6 11h-5a1 1 0 0 0 0 2h5a1 1 0 0 0 0 -2m3 -4h-10a1 1 0 1 0 0 2"
    'h10a1 1 0 0 0 0 -2"/></svg>'
).encode()

# Brand blue, matching the site's --select and the wordmark's semicolon.
TILE = NSColor.colorWithSRGBRed_green_blue_alpha_(0x2E / 255, 0x62 / 255, 0xD9 / 255, 1.0)
SIZES = [16, 32, 64, 128, 256, 512, 1024]
NAMES = {
    16: ["icon_16x16.png"],
    32: ["icon_16x16@2x.png", "icon_32x32.png"],
    64: ["icon_32x32@2x.png"],
    128: ["icon_128x128.png"],
    256: ["icon_128x128@2x.png", "icon_256x256.png"],
    512: ["icon_256x256@2x.png", "icon_512x512.png"],
    1024: ["icon_512x512@2x.png"],
}


def glyph_image():
    data = NSData.dataWithBytes_length_(GLYPH, len(GLYPH))
    img = NSImage.alloc().initWithData_(data)
    if img is None or not img.isValid():
        sys.exit("could not load the glyph SVG")
    img.setSize_(NSMakeSize(1024, 1024))
    return img


def render(px, glyph):
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, px, px, 8, 4, True, False, "NSCalibratedRGBColorSpace", 0, 0
    )
    ctx = NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(ctx)

    inset = px * 0.085          # the usual macOS app-icon breathing room
    radius = px * 0.225
    TILE.setFill()
    NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        NSMakeRect(inset, inset, px - 2 * inset, px - 2 * inset), radius, radius
    ).fill()

    side = px * 0.52
    origin = (px - side) / 2
    glyph.drawInRect_fromRect_operation_fraction_(
        NSMakeRect(origin, origin, side, side), NSZeroRect, 2, 1.0
    )

    NSGraphicsContext.restoreGraphicsState()
    return rep.representationUsingType_properties_(NSPNGFileType, None)


def main():
    glyph = glyph_image()
    out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "aidr.icns")
    with tempfile.TemporaryDirectory() as tmp:
        iconset = os.path.join(tmp, "aidr.iconset")
        os.makedirs(iconset)
        for px, files in NAMES.items():
            png = render(px, glyph)
            for name in files:
                png.writeToFile_atomically_(os.path.join(iconset, name), True)
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", out], check=True)
    print(f"wrote {out} ({os.path.getsize(out) // 1024} KB)")


if __name__ == "__main__":
    main()
