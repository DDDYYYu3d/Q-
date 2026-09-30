# -*- coding: utf-8 -*-
"""生成「当前写实版 vs 新版Q版」对比图，便于确认风格与面部相似度。"""
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
GENQ = os.path.join(HERE, "gen_q")

PAIRS = [
    ("idle", "Q版可爱写实立绘站姿_约2_5头身的大头小身比例_同一位清秀_2026-09-27T09-10-18.png"),
    ("happy", "Q版可爱写实立绘大笑欢呼_约2_5头身的可爱大头比例_同一位_2026-09-27T09-10-17.png"),
    ("shy", "Q版可爱写实立绘害羞抱头_约2_5头身可爱大头比例_同一位清_2026-09-27T09-10-17.png"),
    ("walk", "Q版可爱写实立绘走路姿态_约2_5头身可爱大头比例_同一位清_2026-09-27T09-10-18.png"),
]
LABELS = ["待机", "开心", "害羞", "走路"]

CELL, PAD, TITLE = 330, 22, 30
W = PAD + (CELL + PAD) * len(PAIRS)
H = PAD + TITLE + CELL + PAD + TITLE + CELL + PAD
board = Image.new("RGB", (W, H), (247, 248, 252))
d = ImageDraw.Draw(board)
try:
    f_big = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 19)
    f_sm = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 14)
except Exception:
    f_big = f_sm = ImageFont.load_default()


def paste_fit(src, x, y, w, h):
    src = src.copy()
    src.thumbnail((w, h), Image.LANCZOS)
    board.paste(src, (x + (w - src.width) // 2, y + (h - src.height) // 2), src if src.mode == "RGBA" else None)


def draw_cell(x, y):
    d.rectangle([x, y, x + CELL, y + CELL], fill=(255, 255, 255), outline=(226, 229, 238))


# 第一行：当前写实版
d.text((PAD, PAD), "当前：写实版（已装在这版桌宠里）", fill=(70, 78, 96), font=f_big)
y1 = PAD + TITLE
for i, (name, _) in enumerate(PAIRS):
    x = PAD + i * (CELL + PAD)
    draw_cell(x, y1)
    im = Image.open(os.path.join(HERE, "assets", name + ".png"))
    paste_fit(im, x, y1, CELL, CELL)
    d.text((x + 6, y1 + CELL - 22), LABELS[i], fill=(120, 128, 145), font=f_sm)

# 第二行：新版 Q 版
y2 = y1 + CELL + PAD + TITLE
d.text((PAD, y2 - TITLE), "新版：Q版可爱写实风（AI 重绘，面部特征保留）", fill=(63, 124, 240), font=f_big)
for i, (name, qfn) in enumerate(PAIRS):
    x = PAD + i * (CELL + PAD)
    draw_cell(x, y2)
    im = Image.open(os.path.join(GENQ, qfn))
    paste_fit(im, x, y2, CELL, CELL)
    d.text((x + 6, y2 + CELL - 22), LABELS[i], fill=(63, 124, 240), font=f_sm)

out = os.path.join(os.path.dirname(HERE), "Q版对比预览.png")
board.save(out)
print("saved ->", out, board.size)
