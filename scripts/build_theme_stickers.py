from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "theme-stickers"


def canvas(width: int, height: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    return image, ImageDraw.Draw(image)


def save(image: Image.Image, name: str) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT / name, optimize=True)


def oriental_branch() -> None:
    image, draw = canvas(520, 190)
    points = [(18, 154), (82, 137), (139, 111), (208, 97), (275, 62), (348, 55), (420, 27), (500, 20)]
    draw.line(points, fill=(91, 74, 58, 210), width=7, joint="curve")
    rng = random.Random(17)
    for x, y in points[1:-1]:
        side = -1 if rng.random() > .48 else 1
        draw.line([(x, y), (x + 21, y + 33 * side)], fill=(91, 74, 58, 190), width=4)
        for offset in (0, 16):
            cx, cy = x + 18 + offset, y + (25 + offset // 2) * side
            color = (122, 46, 46, 185) if rng.random() > .45 else (181, 138, 74, 175)
            draw.ellipse((cx - 12, cy - 7, cx + 12, cy + 7), fill=color)
    save(image, "oriental-branch.png")


def oriental_seal() -> None:
    image, draw = canvas(110, 110)
    rng = random.Random(23)
    red = (151, 55, 48, 220)
    points = [(12 + rng.randint(-3, 3), 10), (98, 13), (95, 98), (10, 95)]
    draw.line(points + [points[0]], fill=red, width=6, joint="curve")
    draw.line([(31, 29), (78, 78)], fill=red, width=5)
    draw.line([(77, 28), (32, 78)], fill=red, width=5)
    draw.rectangle((39, 39, 69, 68), outline=red, width=4)
    save(image, "oriental-seal.png")


def press_tape() -> None:
    image, draw = canvas(350, 86)
    rng = random.Random(31)
    top = [(x, 13 + rng.randint(-6, 6)) for x in range(0, 351, 25)]
    bottom = [(x, 72 + rng.randint(-6, 6)) for x in reversed(range(0, 351, 25))]
    draw.polygon(top + bottom, fill=(222, 194, 135, 185))
    for x in range(-60, 410, 28):
        draw.line((x, 8, x + 72, 80), fill=(255, 249, 224, 55), width=5)
    save(image, "press-tape.png")


def press_burst() -> None:
    image, draw = canvas(150, 150)
    points = []
    for index in range(32):
        angle = index * math.pi / 16
        radius = 68 if index % 2 == 0 else 47
        points.append((75 + math.cos(angle) * radius, 75 + math.sin(angle) * radius))
    draw.polygon(points, fill=(182, 64, 50, 225))
    draw.ellipse((55, 55, 95, 95), fill=(251, 245, 232, 255))
    save(image, "press-burst.png")


def pop_star() -> None:
    image, draw = canvas(170, 170)
    points = []
    for index in range(18):
        angle = -math.pi / 2 + index * math.pi / 9
        radius = 78 if index % 2 == 0 else 35
        points.append((85 + math.cos(angle) * radius, 85 + math.sin(angle) * radius))
    draw.polygon(points, fill=(255, 183, 3, 245), outline=(20, 33, 61, 255))
    draw.line(points + [points[0]], fill=(20, 33, 61, 255), width=5, joint="curve")
    save(image, "pop-star.png")


def pop_arrow() -> None:
    image, draw = canvas(280, 130)
    points = [(18, 94), (46, 67), (84, 85), (118, 51), (158, 69), (204, 34)]
    draw.line(points, fill=(242, 56, 90, 245), width=14, joint="curve")
    draw.polygon([(199, 14), (264, 21), (226, 75)], fill=(242, 56, 90, 245))
    save(image, "pop-arrow.png")


def atlas_leaf() -> None:
    image, draw = canvas(260, 260)
    green = (63, 107, 87, 215)
    clay = (168, 103, 78, 180)
    draw.line((36, 230, 198, 42), fill=clay, width=7)
    for index in range(7):
        t = (index + 1) / 8
        x = 36 + (198 - 36) * t
        y = 230 + (42 - 230) * t
        for side in (-1, 1):
            dx, dy = 34 * side, -12 * side
            draw.line((x, y, x + dx, y + dy), fill=clay, width=4)
            draw.ellipse((x + dx - 25, y + dy - 12, x + dx + 25, y + dy + 12), fill=green)
    save(image, "atlas-leaf.png")


def atlas_flower() -> None:
    image, draw = canvas(180, 180)
    center = (90, 91)
    for index in range(8):
        angle = index * math.pi / 4
        cx = center[0] + math.cos(angle) * 43
        cy = center[1] + math.sin(angle) * 43
        draw.ellipse((cx - 25, cy - 12, cx + 25, cy + 12), fill=(199, 146, 79, 150))
    draw.ellipse((68, 69, 112, 113), fill=(168, 103, 78, 225))
    save(image, "atlas-flower.png")


def business_orbit() -> None:
    image, draw = canvas(300, 300)
    navy = (23, 50, 77, 225)
    lime = (194, 226, 91, 235)
    coral = (237, 106, 90, 220)
    for box, start, end, color, width in [((24, 24, 276, 276), 205, 510, navy, 12), ((56, 56, 244, 244), 185, 430, lime, 18), ((89, 89, 211, 211), 240, 540, coral, 10)]:
        draw.arc(box, start=start, end=end, fill=color, width=width)
    draw.ellipse((133, 133, 167, 167), fill=navy)
    save(image, "business-orbit.png")


def business_signal() -> None:
    image, draw = canvas(340, 125)
    colors = [(23, 50, 77, 230), (194, 226, 91, 240), (237, 106, 90, 225)]
    for index, color in enumerate(colors):
        x = 15 + index * 83
        draw.polygon([(x, 96), (x + 36, 19), (x + 77, 19), (x + 41, 96)], fill=color)
    draw.line((16, 110, 325, 110), fill=(23, 50, 77, 140), width=3)
    save(image, "business-signal.png")


def cinema_ticket() -> None:
    image, draw = canvas(360, 170)
    cream = (250, 247, 239, 250)
    coral = (211, 90, 84, 235)
    plum = (85, 59, 93, 235)
    polygon = [(10, 22), (350, 22), (350, 61), (334, 72), (350, 83), (350, 148), (10, 148), (10, 83), (26, 72), (10, 61)]
    draw.polygon(polygon, fill=cream, outline=plum)
    draw.line((102, 24, 102, 146), fill=coral, width=5)
    draw.line((121, 56, 318, 56), fill=plum, width=6)
    draw.line((121, 87, 279, 87), fill=coral, width=5)
    draw.line((121, 115, 308, 115), fill=plum, width=3)
    for y in range(39, 139, 20):
        draw.ellipse((46, y, 56, y + 10), fill=plum)
    save(image, "cinema-ticket.png")


def cinema_spotlight() -> None:
    image, draw = canvas(360, 260)
    plum = (85, 59, 93, 195)
    gold = (242, 166, 90, 165)
    coral = (211, 90, 84, 180)
    draw.polygon([(22, 18), (109, 18), (237, 241), (94, 241)], fill=gold)
    draw.polygon([(251, 15), (334, 15), (270, 241), (146, 241)], fill=(98, 150, 157, 120))
    draw.ellipse((68, 188, 291, 248), fill=(255, 250, 237, 220), outline=coral, width=5)
    draw.arc((93, 177, 271, 251), 190, 352, fill=plum, width=7)
    save(image, "cinema-spotlight.png")


def cinema_clapper() -> None:
    image, draw = canvas(360, 225)
    cream = (250, 247, 239, 245)
    plum = (85, 59, 93, 240)
    gold = (242, 166, 90, 235)
    coral = (211, 90, 84, 230)
    # A compact, text-free clapperboard: recognisable as cinema without adding
    # another dark rectangle to the article flow.
    draw.rounded_rectangle((55, 87, 318, 201), radius=16, fill=cream, outline=plum, width=5)
    draw.line((74, 124, 298, 124), fill=coral, width=5)
    draw.line((89, 154, 185, 154), fill=plum, width=4)
    draw.line((203, 154, 278, 154), fill=gold, width=4)
    board = [(36, 73), (306, 28), (321, 75), (50, 118)]
    draw.polygon(board, fill=plum)
    for index in range(6):
        x = 53 + index * 46
        draw.polygon([(x, 69), (x + 26, 65), (x + 47, 34), (x + 21, 38)], fill=gold if index % 2 == 0 else cream)
    draw.ellipse((19, 63, 61, 105), fill=coral, outline=cream, width=4)
    save(image, "cinema-clapper.png")


def cinema_reel() -> None:
    image, draw = canvas(270, 245)
    cream = (250, 247, 239, 245)
    plum = (85, 59, 93, 235)
    coral = (211, 90, 84, 225)
    gold = (242, 166, 90, 220)
    draw.ellipse((22, 18, 202, 198), fill=cream, outline=plum, width=8)
    for angle in (-math.pi / 2, 0, math.pi / 2, math.pi):
        cx = 112 + math.cos(angle) * 50
        cy = 108 + math.sin(angle) * 50
        draw.ellipse((cx - 24, cy - 24, cx + 24, cy + 24), fill=gold)
    draw.ellipse((91, 87, 133, 129), fill=coral)
    draw.arc((43, 39, 181, 177), start=35, end=315, fill=plum, width=4)
    draw.line((181, 166, 250, 221), fill=plum, width=8)
    draw.line((180, 177, 243, 226), fill=coral, width=3)
    save(image, "cinema-reel.png")


def main() -> None:
    for builder in (
        oriental_branch,
        oriental_seal,
        press_tape,
        press_burst,
        pop_star,
        pop_arrow,
        atlas_leaf,
        atlas_flower,
        business_orbit,
        business_signal,
        cinema_ticket,
        cinema_spotlight,
        cinema_clapper,
        cinema_reel,
    ):
        builder()


if __name__ == "__main__":
    main()
