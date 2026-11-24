from pathlib import Path
from urllib.request import urlopen
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1] / "app" / "src" / "main" / "res"
PHOTO_URL = "https://raw.githubusercontent.com/GOVIND-BOTS/-GOVIND-OFFICIAL-MP/main/IMG_20261103_064552_734.jpg"

with urlopen(PHOTO_URL, timeout=30) as response:
    photo = Image.open(response).convert("RGB")

# Keep a clean square crop for launcher icons.
icon = ImageOps.fit(photo, (512, 512), method=Image.Resampling.LANCZOS, centering=(0.5, 0.45))
for density, size in {"mdpi":48, "hdpi":72, "xhdpi":96, "xxhdpi":144, "xxxhdpi":192}.items():
    folder = ROOT / f"mipmap-{density}"
    folder.mkdir(parents=True, exist_ok=True)
    icon.resize((size, size), Image.Resampling.LANCZOS).save(folder / "ic_launcher.png", optimize=True)

splash = ROOT / "drawable-nodpi"
splash.mkdir(parents=True, exist_ok=True)
ImageOps.contain(photo, (1200, 1200), method=Image.Resampling.LANCZOS).save(splash / "welcome_photo.jpg", quality=92, optimize=True)
print("Launcher and welcome images generated.")
