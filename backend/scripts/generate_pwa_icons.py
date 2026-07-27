import os
from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
IMAGE_DIR = STATIC_DIR / "images"
PWA_DIR = IMAGE_DIR / "pwa"

PWA_DIR.mkdir(parents=True, exist_ok=True)

logo_path = IMAGE_DIR / "logo.png"
if not logo_path.exists():
    raise FileNotFoundError(f"Logo not found at {logo_path}")

logo = Image.open(logo_path).convert("RGBA")

# Generate standard icons
logo.resize((192, 192), Image.Resampling.LANCZOS).save(PWA_DIR / "icon-192.png")
logo.resize((512, 512), Image.Resampling.LANCZOS).save(PWA_DIR / "icon-512.png")
logo.resize((180, 180), Image.Resampling.LANCZOS).save(PWA_DIR / "apple-touch-icon.png")

# Generate maskable icons with background padding
def create_maskable_icon(size):
    bg_color = (13, 31, 22, 255) # #0d1f16
    img = Image.new("RGBA", (size, size), bg_color)
    target_size = int(size * 0.8) # 80% safe zone
    resized_logo = logo.resize((target_size, target_size), Image.Resampling.LANCZOS)
    offset = (size - target_size) // 2
    img.paste(resized_logo, (offset, offset), resized_logo)
    return img

create_maskable_icon(192).save(PWA_DIR / "icon-maskable-192.png")
create_maskable_icon(512).save(PWA_DIR / "icon-maskable-512.png")

print(f"PWA icons successfully generated in {PWA_DIR}")
