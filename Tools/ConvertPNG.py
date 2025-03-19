#!/usr/bin/env python3

from PIL import Image
import sys
import os

def convert_png(source_path, dest_path=None, keep_alpha=True):
    """
    Convert a PNG file to a standard 8-bit RGB(A) format with no special profiles.
    :param source_path: Path to the source PNG
    :param dest_path:   Where to save the converted PNG (defaults to source + '_converted.png')
    :param keep_alpha:  Whether to keep alpha channel (RGBA) or strip it to RGB
    """
    print("""
    Convert a PNG file to a standard 8-bit RGB(A) format with no special profiles.
    :param source_path: Path to the source PNG
    :param dest_path:   Where to save the converted PNG (defaults to source + '_converted.png')
    :param keep_alpha:  Whether to keep alpha channel (RGBA) or strip it to RGB
    """)
    if not dest_path:
        root = os.path.splitext(source_path)[0]
        dest_path = f"{root}_converted.png"

    # 1) Load the source image
    img = Image.open(source_path)

    # 2) Convert to RGB or RGBA (8 bits per channel)
    if keep_alpha and "A" in img.getbands():
        # Convert to RGBA if original had an alpha channel
        img = img.convert("RGBA")
    else:
        # Otherwise use plain RGB
        img = img.convert("RGB")

    # 3) Remove ICC profile or other extra info if present
    if "icc_profile" in img.info:
        # Copy info except the ICC profile
        info = {k: v for k, v in img.info.items() if k != "icc_profile"}
        img.info = info

    # 4) Save the image in standard PNG format
    img.save(dest_path, format="PNG")

    print(f"[OK] Converted: {source_path} -> {dest_path}")



if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python convert_png.py <source_png> [destination_png] [--no-alpha]")
        sys.exit(1)

    source_png = sys.argv[1]
    dest_png = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None
    keep_alpha = "--no-alpha" not in sys.argv

    convert_png(source_png, dest_png, keep_alpha)
    