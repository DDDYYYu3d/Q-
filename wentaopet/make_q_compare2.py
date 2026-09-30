# -*- coding: utf-8 -*-
"""三列对比：写实原版 / Q版第一轮 / Q版保真加强版（重点看脸部相似度）"""
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = [
    ("待机", "idle",
     "Q版可爱写实立绘站姿_约2_5头身的大头小身比例_同一位清秀_2026-09-27T09-10-18.png",
     "Q版保真立绘站姿_身体比例Q版化_约2_5头身_四肢短圆可爱_2026-09-27T09-11-41.png"),
    ("开心", "happy",
     "Q版可爱写实立绘大笑欢呼_约2_5头身的可爱大头比例_同一位_2026-09-27T09-10-17.png",
     "Q版保真立绘大笑欢呼_身体比例Q版化_约2_5头身_四肢短圆_2026-09-27T09-11-39.png"),
]
COLS = ["写实原版（现在用的）", "Q版 第一轮", "Q版 保真加强版"]

CELL, PAD, TITLE = 320, 20, 32
W = PAD * 4 + TITLE + CELL * 3
H = PAD * 3 + 30 + CELL * 2 + TITLE
board = Image.new("RGB", (W, H), (247, 248, 252))
d = ImageDraw.Draw(board)
try:
    f_big = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)
    f_sm = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 14)
except Exception:
    f_big = f_sm = ImageFont.load_default()

# 列标题（竖排在左侧）
for c, name in enumerate(COLS):
    d.text((PAD + TITLE + c * (CELL + PAD) + 6, PAD), name,
           fill=(63, 124, 240) if c == 2 else (70, 78, 96), font=f_big)


def paste_fit(im, x, y, w, h):
    im = im.copy()
    im.thumbnail((w, h), Image.LANCZOS)
    board.paste(im, (x + (w - im.width) // 2, y + (h - im.height) // 2),
                im if im.mode == "RGBA" else None)


y = PAD + 34
for label, asset_name, q1, q2 in ROWS:
    paths = [os.path.join(HERE, "assets", asset_name + ".png"),
             os.path.join(HERE, "gen_q", q1),
             os.path.join(HERE, "gen_q2", q2)]
    d.text((PAD, y + CELL // 2), label, fill=(120, 128, 145), font=f_sm)
    for c, p in enumerate(paths):
        x = PAD + TITLE + c * (CELL + PAD)
        d.rectangle([x, y, x + CELL, y + CELL], fill=(255, 255, 255),
                    outline=(226, 229, 238) if c < 2 else (140, 175, 250))
        if os.path.exists(p):
            paste_fit(Image.open(p), x, y, CELL, CELL)
    y += CELL + PAD

out = os.path.join(os.path.dirname(HERE), "Q版脸型对比.png")
board.save(out)
print("saved ->", out, board.size)
