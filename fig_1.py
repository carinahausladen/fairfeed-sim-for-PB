"""
fig_1.py — render the paper's Figure 1, the onboarding figure (fig_1.png).

This is the paper's Figure 1 (internal panels A/B/C) — a static HTML/CSS design
mockup, not a simulation result. We render data/onboarding/
figure_onboarding_v2.html with headless Chrome and autocrop the white border
with Pillow, the same pipeline that produced the figure in the paper.

    python3 fig_1.py

Needs Google Chrome (or Chromium) and Pillow. If Chrome is not found the script
prints the path it looked for so you can pass --chrome=/path/to/chrome.
"""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HTML = HERE / "data" / "onboarding" / "figure_onboarding_v2.html"
RAW = HERE / "output" / "_onboarding_raw.png"
OUT = HERE / "output" / "fig_1.png"
PAPER_PNG = HERE.parent / "acm" / "fig_onboarding.png"   # the submission's copy; skipped if absent

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome", "chromium", "chromium-browser",
]


def find_chrome():
    for c in CHROME_CANDIDATES:
        if Path(c).exists():
            return c
    from shutil import which
    for c in CHROME_CANDIDATES:
        if which(c):
            return which(c)
    return None


def main():
    chrome = find_chrome()
    if not chrome:
        print("Google Chrome / Chromium not found. Looked in:")
        for c in CHROME_CANDIDATES:
            print("  ", c)
        print("Pass --chrome=/path/to/chrome, or open the HTML and screenshot it manually:")
        print("  ", HTML)
        sys.exit(1)

    OUT.parent.mkdir(exist_ok=True)
    # high device-scale render so the 241pt-wide figure is crisp at print size
    subprocess.run([
        chrome, "--headless", "--disable-gpu", "--hide-scrollbars",
        "--force-device-scale-factor=5", "--window-size=900,1400",
        f"--screenshot={RAW}", HTML.as_uri(),
    ], check=True, capture_output=True)
    print(f"rendered raw screenshot -> {RAW}")

    try:
        from PIL import Image, ImageChops
    except ImportError:
        print("Pillow not installed; leaving the un-cropped screenshot at", RAW)
        print("  (pip install pillow, then re-run to autocrop the white border)")
        return

    im = Image.open(RAW).convert("RGB")
    bg = Image.new("RGB", im.size, (255, 255, 255))
    bbox = ImageChops.difference(im, bg).getbbox()
    if bbox:
        pad = 6
        bbox = (max(0, bbox[0] - pad), max(0, bbox[1] - pad),
                min(im.width, bbox[2] + pad), min(im.height, bbox[3] + pad))
        im = im.crop(bbox)
    im.save(OUT)
    RAW.unlink(missing_ok=True)
    print(f"wrote {OUT}  ({im.width}x{im.height})")
    if PAPER_PNG.parent.is_dir():
        shutil.copyfile(OUT, PAPER_PNG)
        print(f"wrote {PAPER_PNG}  (paper's Figure 1)")
    else:
        print(f"skipped {PAPER_PNG} (no paper folder — standalone package)")


if __name__ == "__main__":
    # allow --chrome=/path override
    for a in sys.argv[1:]:
        if a.startswith("--chrome="):
            CHROME_CANDIDATES.insert(0, a.split("=", 1)[1])
    main()
