# -*- coding: utf-8 -*-
"""对比：上一版Q版（裤子缺失） vs 新版（完整着装）"""
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = [
    ("站姿",
     "gen_q2/Q版保真立绘站姿_身体比例Q版化_约2_5头身_四肢短圆可爱_2026-09-27T09-11-41.png",
     "gen_q3/Q版立绘衣着站姿_约2_5头身可爱大头比例_同一位清秀年轻男_2026-09-27T09-13-40.png"),
    ("走路",
     "gen_q2/Q版保真立绘走路迈步_身体比例Q版化_约2_5头身_四肢短圆_2026-09-27T09-12-36.png",
     "gen_q3/Q版立绘衣着走路_约2_5头身可爱大头比例_同一位清秀年轻男_2026-09-27T09-13-40.png"),
    ("西装",
     "gen_q2/Q版保真立绘西装微笑_身体比例Q版化_约2_5头身_四肢短圆_2026-09-27T09-12-37.png",
     "gen_q3/Q版立绘衣着西装_约2_5头身可爱大头比例_同一位清秀年轻男_2026-09-27T09-13-40.png"),
]
COLS = ["上一版（缺裤子）", "新版（完整着装：上衣+长裤+鞋）"]

CELL, PAD, TITLE = 360, 22, 34
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
           fill=(236, 95, 142) if c == 0 else (47, 163, 107), font=f_big)


def paste_fit(im, x, y, w, h):
    im = im.copy()
    im.thumbnail((w, h), Image.LANCZOS)
    board.paste(im, (x + (w - im.width) // 2, y + (h - im.height) // 2),
                im if im.mode == "RGBA" else None)


y = PAD + TITLE + 6
for label, old, new in ROWS:
    d.text((PAD, y + CELL // 2), label, fill=(120, 128, 145), font=f_sm)
    for c, rel in enumerate((old, new)):
        x = PAD + TITLE + c * (CELL + PAD)
        d.rectangle([x, y, x + CELL, y + CELL], fill=(255, 255, 255),
                    outline=(238, 200, 214) if c == 0 else (170, 215, 190))
        p = os.path.join(HERE, rel)
        if os.path.exists(p):
            paste_fit(Image.open(p), x, y, CELL, CELL)
    y += CELL + PAD

out = os.path.join(os.path.dirname(HERE), "Q版着装对比.png")
board.save(out)
print("saved ->", out, board.size)
