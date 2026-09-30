# -*- coding: utf-8 -*-
"""对比：着装版（上一轮） vs 强保真版（以清晰特写作主参考，只改身体比例）"""
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = [
    ("站姿",
     "gen_q3/Q版立绘衣着站姿_约2_5头身可爱大头比例_同一位清秀年轻男_2026-09-27T09-13-40.png",
     "gen_q4/把第一张参考照片里的这位真人Q版化_身体改成约2_5头身的可_2026-09-27T09-15-04.png"),
    ("走路",
     "gen_q3/Q版立绘衣着走路_约2_5头身可爱大头比例_同一位清秀年轻男_2026-09-27T09-13-40.png",
     "gen_q4/把第一张参考照片里的这位真人Q版化_身体改成约2_5头身的可_2026-09-27T09-15-04.png"),
]
COLS = ["着装版（上一轮）", "强保真版（脸部优先参考特写）"]

CELL, PAD, TITLE = 380, 22, 34
W = PAD * 3 + TITLE + CELL * 2
H = PAD * 2 + TITLE + (CELL + PAD) * len(ROWS)
board = Image.new("RGB", (W, H), (247, 248, 252))
d = ImageDraw.Draw(board)
try:
    f_big = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 17)
    f_sm = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 14)
except Exception:
    f_big = f_sm = ImageFont.load_default()

for c, name in enumerate(COLS):
    d.text((PAD + TITLE + c * (CELL + PAD) + 6, PAD), name,
           fill=(70, 78, 96) if c == 0 else (47, 163, 107), font=f_big)


def paste_fit(im, x, y, w, h):
    im = im.copy()
    im.thumbnail((w, h), Image.LANCZOS)
    board.paste(im, (x + (w - im.width) // 2, y + (h - im.height) // 2),
                im if im.mode == "RGBA" else None)


# 参考照片（面部来源）贴右上角做参照
ref = Image.open(r"C:\Users\DY\.workbuddy\clipboard-images"
                 r"\clipboard-2026-09-27T09-09-43-067Z-b2bcb768.png")
ref.thumbnail((TITLE - 8, TITLE - 8), Image.LANCZOS)
board.paste(ref, (PAD + 2, PAD + 2))
d.text((PAD + TITLE + 2 * (CELL + PAD) + 6, PAD - 2), "参考照片 →", fill=(200, 130, 60), font=f_sm)

y = PAD + TITLE + 6
for label, old, new in ROWS:
    d.text((PAD, y + CELL // 2), label, fill=(120, 128, 145), font=f_sm)
    for c, rel in enumerate((old, new)):
        x = PAD + TITLE + c * (CELL + PAD)
        d.rectangle([x, y, x + CELL, y + CELL], fill=(255, 255, 255),
                    outline=(226, 229, 238) if c == 0 else (170, 215, 190))
        p = os.path.join(HERE, rel)
        if os.path.exists(p):
            paste_fit(Image.open(p), x, y, CELL, CELL)
    y += CELL + PAD

out = os.path.join(os.path.dirname(HERE), "Q版脸部保真对比.png")
board.save(out)
print("saved ->", out, board.size)
