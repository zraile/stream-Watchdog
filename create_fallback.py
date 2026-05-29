"""
Pillow ile 1920x1080 fallback.jpg oluşturur.
"YAYIN KESİNTİSİ - Kamera yeniden bağlanıyor..." yazan koyu mavi arka planlı görsel.
"""

from PIL import Image, ImageDraw, ImageFont


def create_fallback(path: str = "fallback.jpg", width: int = 1920, height: int = 1080):
    img = Image.new("RGB", (width, height), color=(10, 15, 40))
    draw = ImageDraw.Draw(img)

    lines = [
        ("YAYIN KESİNTİSİ", 80),
        ("Kamera yeniden bağlanıyor...", 40),
    ]

    font_paths = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]

    y_offset = height // 2 - 80

    for text, size in lines:
        font = None
        for fp in font_paths:
            try:
                font = ImageFont.truetype(fp, size)
                break
            except OSError:
                continue
        if font is None:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        draw.text((x, y_offset), text, fill=(180, 200, 255), font=font)
        y_offset += size + 20

    img.save(path, quality=95)
    print(f"✅ Fallback görseli oluşturuldu: {path}")


if __name__ == "__main__":
    create_fallback()
