from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT_DIR = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT_DIR / "packaging" / "assets"


def create_base_icon(size: int = 1024) -> Image.Image:
    image = Image.new("RGBA", (size, size), "#131921")
    draw = ImageDraw.Draw(image)
    margin = int(size * 0.14)
    radius = int(size * 0.09)
    draw.rounded_rectangle(
        (margin, margin, size - margin, size - margin),
        radius=radius,
        fill="#FFFFFF",
    )

    fold = int(size * 0.22)
    draw.polygon(
        [
            (size - margin - fold, margin),
            (size - margin, margin + fold),
            (size - margin - fold, margin + fold),
        ],
        fill="#EAeded",
    )

    line_left = int(size * 0.30)
    line_right = int(size * 0.70)
    line_width = int(size * 0.045)
    for y in (0.38, 0.52):
        y_pos = int(size * y)
        draw.line(
            (line_left, y_pos, line_right, y_pos),
            fill="#232F3E",
            width=line_width,
        )

    check_width = int(size * 0.06)
    draw.line(
        (
            int(size * 0.31),
            int(size * 0.68),
            int(size * 0.43),
            int(size * 0.79),
            int(size * 0.70),
            int(size * 0.60),
        ),
        fill="#FF9900",
        width=check_width,
        joint="curve",
    )
    return image


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    base = create_base_icon()
    base.save(ASSET_DIR / "app-icon.png", optimize=True)
    base.save(
        ASSET_DIR / "app-icon.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    base.save(ASSET_DIR / "app-icon.icns", format="ICNS")


if __name__ == "__main__":
    main()
