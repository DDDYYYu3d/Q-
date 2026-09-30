# -*- coding: utf-8 -*-
"""
郭文韬桌宠 - 素材处理：照片抠图（去背景）+ 裁剪缩放 + 图标 + 预览图
用法:
  python process_images.py            # 使用 rembg(u2net) 抠图
  python process_images.py --fallback # 无模型时用均匀背景色键抠图(仅适合纯色背景照片)
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter, ImageDraw, ImageFont
from scipy import ndimage

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gen_q5")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# (输出名, 源文件, 目标高度px, 用途说明)
# 源为 AI 生成图：真实照片 -> Q版可爱写实（脸部严格照搬真人五官），白底立绘
JOBS = [
    ("idle",  "站姿Q版化真人_把第一张参考照片中的这位真人做Q版化__脸部_2026-09-27T09-17-09.png", 1200),  # 站姿 奶白毛衣
    ("walk",  "走路Q版化真人_把第一张参考照片中的这位真人做Q版化__脸部_2026-09-27T09-17-10.png", 1200),  # 蓝运动服 走路
    ("happy", "大笑Q版化真人_把第一张参考照片中的这位真人做Q版化__脸部_2026-09-27T09-17-12.png", 1200),  # 大笑欢呼
    ("shy",   "害羞Q版化真人_把第一张参考照片中的这位真人做Q版化__脸部_2026-09-27T09-17-10.png", 1200),  # 害羞挠头
    ("sleep", "打盹Q版化真人_把第一张参考照片中的这位真人做Q版化__脸部_2026-09-27T09-17-08.png", 1200),  # 抱枕打盹
    ("chat",  "西装Q版化真人_把第一张参考照片中的这位真人做Q版化__脸部_2026-09-27T09-17-36.png", 1200),  # 黑西装
    ("wave",  "挥手Q版化真人_把第一张参考照片中的这位真人做Q版化__脸部_2026-09-27T09-17-36.png", 1200),  # 挥手打招呼
    ("eat",   "吃面Q版化真人_把第一张参考照片中的这位真人做Q版化__脸部_2026-09-27T09-17-36.png", 1200),  # 端碗吃面
    ("think", "思考Q版化真人_把第一张参考照片中的这位真人做Q版化__脸部_2026-09-27T09-17-36.png", 1200),  # 托腮思考
    ("surprise", "惊讶Q版化真人_把第一张参考照片中的这位真人做Q版化__脸部_2026-09-27T09-17-36.png", 1200),  # 惊讶
]

_session = None


def rembg_cut(im):
    global _session
    from rembg import remove, new_session
    if _session is None:
        _session = new_session("u2net")
    return remove(im, session=_session)


def fallback_key(im):
    """均匀背景色键抠图（保底方案）：从边缘泛洪，把与边框中值色相近的连通区域判为背景。"""
    a = np.asarray(im.convert("RGB")).astype(np.int16)
    border = np.concatenate([a[0, :], a[-1, :], a[:, 0], a[:, -1]])
    med = np.median(border, axis=0)
    dist = np.sqrt(((a - med) ** 2).sum(-1))
    bg = dist < 30
    lab, n = ndimage.label(bg)
    if n:
        border_labels = set(lab[0, :]) | set(lab[-1, :]) | set(lab[:, 0]) | set(lab[:, -1])
        mask = np.zeros_like(bg)
        for l in border_labels:
            if l:
                mask |= (lab == l)
        alpha = np.where(mask, 0, 255).astype(np.uint8)
    else:
        alpha = np.full(a.shape[:2], 255, np.uint8)
    out = im.convert("RGBA")
    am = Image.fromarray(alpha).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.5))
    out.putalpha(am)
    return out


def largest_component(rgba):
    """只保留最大的前景连通域——顺带去掉角标水印等漂浮物。"""
    arr = np.asarray(rgba).copy()
    a = arr[:, :, 3]
    m = a > 8
    if not m.any():
        return rgba
    lab, n = ndimage.label(m)
    if n <= 1:
        return rgba
    sizes = ndimage.sum(m, lab, range(1, n + 1))
    keep = 1 + int(np.argmax(sizes))
    arr[:, :, 3][lab != keep] = 0
    return Image.fromarray(arr)


def clean_edges(rgba):
    """边缘收缩1px+轻微羽化，去除白边。"""
    a = rgba.getchannel("A").filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.0))
    out = rgba.copy()
    out.putalpha(a)
    return out


def crop_resize(rgba, target_h):
    bbox = rgba.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if bbox:
        rgba = rgba.crop(bbox)
    w, h = rgba.size
    nw = max(1, round(w * target_h / h))
    return rgba.resize((nw, target_h), Image.LANCZOS)


def make_icon():
    im = Image.open(os.path.join(OUT, "idle.png"))
    s = int(max(im.size) * 1.12)
    canvas = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    canvas.paste(im, ((s - im.width) // 2, s - im.height - (s - im.height) // 2))
    canvas.save(os.path.join(OUT, "pet.ico"),
                sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])


def make_preview():
    names = [j[0] for j in JOBS]
    imgs = [Image.open(os.path.join(OUT, n + ".png")) for n in names]
    cell = 300
    pad = 24
    W = pad + (cell + pad) * len(imgs)
    H = cell + pad * 2 + 34
    board = Image.new("RGB", (W, H), (245, 246, 250))
    d = ImageDraw.Draw(board)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 16)
    except Exception:
        font = ImageFont.load_default()
    for i, (n, im) in enumerate(zip(names, imgs)):
        x = pad + i * (cell + pad)
        # 棋盘格背景表示透明
        for yy in range(0, cell, 20):
            for xx in range(0, cell, 20):
                c = (255, 255, 255) if (xx // 20 + yy // 20) % 2 == 0 else (232, 234, 240)
                d.rectangle([x + xx, pad + yy, x + xx + 20 - 1, pad + yy + 20 - 1], fill=c)
        r = min(cell / im.width, cell / im.height)
        im2 = im.resize((int(im.width * r), int(im.height * r)), Image.LANCZOS)
        board.paste(im2, (x + (cell - im2.width) // 2, pad + (cell - im2.height) // 2), im2)
        d.text((x + cell // 2, pad + cell + 8), n, fill=(60, 60, 70), font=font, anchor="ma")
    out = os.path.join(os.path.dirname(OUT), "素材预览.png")
    board.save(out)
    print("preview ->", out)


def main():
    os.makedirs(OUT, exist_ok=True)
    use_rembg = "--fallback" not in sys.argv
    for name, fn, th in JOBS:
        p = os.path.join(SRC, fn)
        if not os.path.exists(p):
            print(f"[SKIP] {name}: 源文件不存在 {p}")
            continue
        im = Image.open(p).convert("RGB")
        print(f"[{name}] source={im.size} mode={'rembg' if use_rembg else 'fallback'}")
        try:
            rgba = rembg_cut(im) if use_rembg else fallback_key(im)
        except Exception as ex:
            print(f"[{name}] rembg 失败({ex})，改用色键保底")
            rgba = fallback_key(im)
        rgba = largest_component(rgba)
        rgba = clean_edges(rgba)
        rgba = crop_resize(rgba, th)
        out = os.path.join(OUT, name + ".png")
        rgba.save(out)
        cov = (np.asarray(rgba)[:, :, 3] > 8).mean()
        print(f"  -> {os.path.basename(out)} size={rgba.size} alpha_cov={cov:.1%}")
    make_icon()
    make_preview()
    print("DONE")


if __name__ == "__main__":
    main()
