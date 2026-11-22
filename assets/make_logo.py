"""Draws the CreatorOS logo (neo-brutalist): a yellow tile with a thick black border and hard
shadow, a bold black "C" and a pink spark. Run: python assets/make_logo.py

Outputs (in assets/): logo-1024.png (app icon source), logo-256.png, favicon.png, logo.svg
"""

from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).parent
INK, YELLOW, PINK, WHITE = (17, 17, 17, 255), (255, 210, 63, 255), (255, 107, 157, 255), (255, 255, 255, 255)


def draw(size: int = 1024) -> Image.Image:
    s = size / 1024
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = int(150 * s)
    # hard shadow
    d.rounded_rectangle([int(150 * s), int(150 * s), int(950 * s), int(950 * s)], r, fill=INK)
    # tile with thick border
    d.rounded_rectangle([int(74 * s), int(74 * s), int(874 * s), int(874 * s)], r, fill=YELLOW,
                        outline=INK, width=int(44 * s))
    # bold "C": a thick arc opening to the right
    cx, cy, rad, w = 455 * s, 474 * s, 236 * s, 118 * s
    d.arc([cx - rad, cy - rad, cx + rad, cy + rad], start=42, end=318, fill=INK, width=int(w))
    # rounded ends of the C
    import math
    for ang in (42, 318):
        ex = cx + (rad - w / 2) * math.cos(math.radians(ang))
        ey = cy + (rad - w / 2) * math.sin(math.radians(ang))
        d.ellipse([ex - w / 2, ey - w / 2, ex + w / 2, ey + w / 2], fill=INK)
    # pink spark (the "creative" dot) with black outline and its own small shadow
    px, py, pr = 690 * s, 474 * s, 74 * s
    off = 16 * s
    d.ellipse([px - pr + off, py - pr + off, px + pr + off, py + pr + off], fill=INK)
    d.ellipse([px - pr, py - pr, px + pr, py + pr], fill=PINK, outline=INK, width=int(22 * s))
    # white glint
    g = 20 * s
    d.ellipse([px - pr * 0.45 - g, py - pr * 0.45 - g, px - pr * 0.45 + g, py - pr * 0.45 + g], fill=WHITE)
    return img


SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" width="1024" height="1024">
  <rect x="150" y="150" width="800" height="800" rx="150" fill="#111"/>
  <rect x="96" y="96" width="756" height="756" rx="128" fill="#ffd23f" stroke="#111" stroke-width="44"/>
  <path d="M {x1:.1f} {y1:.1f} A 177 177 0 1 0 {x2:.1f} {y2:.1f}" fill="none" stroke="#111" stroke-width="118" stroke-linecap="round"/>
  <circle cx="706" cy="490" r="74" fill="#111"/>
  <circle cx="690" cy="474" r="63" fill="#ff6b9d" stroke="#111" stroke-width="22"/>
  <circle cx="657" cy="441" r="20" fill="#fff"/>
</svg>
"""


def svg() -> str:
    import math
    cx, cy, rr = 455, 474, 177  # centre-line radius of the stroke (236 - 118/2)
    a1, a2 = math.radians(42), math.radians(318)
    return SVG.format(x1=cx + rr * math.cos(a1), y1=cy + rr * math.sin(a1),
                      x2=cx + rr * math.cos(a2), y2=cy + rr * math.sin(a2))


if __name__ == "__main__":
    big = draw(1024)
    big.save(HERE / "logo-1024.png")
    big.resize((256, 256), Image.LANCZOS).save(HERE / "logo-256.png")
    big.resize((64, 64), Image.LANCZOS).save(HERE / "favicon.png")
    (HERE / "logo.svg").write_text(svg(), encoding="utf-8")
    static = HERE.parent / "creatoros" / "dashboard" / "static"
    big.resize((256, 256), Image.LANCZOS).save(static / "logo.png")
    big.resize((64, 64), Image.LANCZOS).save(static / "favicon.png")
    splash = HERE.parent / "desktop" / "splash"
    splash.mkdir(parents=True, exist_ok=True)
    big.resize((256, 256), Image.LANCZOS).save(splash / "logo.png")
    print("Logo written to", HERE, "and", static)
