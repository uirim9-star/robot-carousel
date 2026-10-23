"""카드 JPEG를 한 장으로 이어 붙인 미리보기(sheet.jpg)를 만든다 — 사람이 7장을 한 번에 보게.

python sheet.py slides/2026-10-23
"""
import os, re, sys
from PIL import Image

day = sys.argv[1]
files = sorted(f for f in os.listdir(day) if re.match(r"card_\d+\.jpg$", f))
w, h, cols = 360, 450, 4
sheet = Image.new("RGB", (cols * w + (cols + 1) * 10, ((len(files) + cols - 1) // cols) * (h + 10) + 10), "#e8e8ed")
for i, f in enumerate(files):
    sheet.paste(Image.open(os.path.join(day, f)).resize((w, h)), (10 + (i % cols) * (w + 10), 10 + (i // cols) * (h + 10)))
sheet.save(os.path.join(day, "sheet.jpg"), quality=88)
print(os.path.join(day, "sheet.jpg"))
