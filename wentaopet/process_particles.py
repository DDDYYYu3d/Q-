# -*- coding: utf-8 -*-
"""粒子装饰贴图处理：确保透明通道 → 去杂点 → 裁剪 → 缩放到统一尺寸"""
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "gen_particles")
OUT = os.path.join(HERE, "assets", "particles")

JOBS = [
    ("star", "星光粒子贴图_五角星造型_半透明发光暖黄白色_柔和光晕_单个_2026-09-27T08-16-05.png", 256, True, False),
    ("heart", "爱心粒子贴图_粉红色立体爱心_柔和渐变光泽_圆润可爱_单个居_2026-09-27T08-16-00.png", 256, True, False),
    ("note", "音符粒子贴图_浅蓝色八分音符_圆润可爱卡通感_单个居中_纯透_2026-09-27T08-16-02.png", 256, True, False),
    # 主体本身接近白色，白底泛洪会误吞主体 → 改用分割模型
    ("sparkle", "闪光粒子贴图_四角星芒闪烁高光_白色带淡金边_单个居中_纯透_2026-09-27T08-16-04.png", 256, True, True),
    ("confetti", "彩带粒子贴图_一小簇彩色纸屑彩带_红黄蓝粉配色_庆祝氛围_纯_2026-09-27T08-15-59.png", 320, False, True),
]

_session = None


def has_alpha(im):
    if im.mode != "RGBA":
        return False
    a = np.asarray(im)[:, :, 3]
    return bool(a.min() < 250 and (a < 128).mean() > 0.02)


def rembg_cut(im):
    global _session
    from rembg import remove, new_session
    if _session is None:
        _session = new_session("u2net")
    return remove(im.convert("RGB"), session=_session)


def filter_components(rgba, keep_single):
    """keep_single=True 只留最大连通域；否则按面积阈值去掉碎点。"""
    arr = np.asarray(rgba).copy()
    m = arr[:, :, 3] > 16
    lab, n = ndimage.label(m)
    if n <= 1:
        return rgba
    sizes = ndimage.sum(m, lab, range(1, n + 1))
    if keep_single:
        keep = {1 + int(np.argmax(sizes))}
    else:
        thr = max(1.0, float(sizes.max()) * 0.05)
        keep = {i + 1 for i, s in enumerate(sizes) if s >= thr}
    arr[:, :, 3][~np.isin(lab, list(keep))] = 0
    return Image.fromarray(arr)


def white_bg_key(im, tol=14):
    """纯白底泛洪抠图：只把「与图像边界连通的白色区域」判为背景，图形内部的白色保留。
    对这类发光小图标比通用抠图模型更可靠（不会切断星芒尖角）。"""
    from PIL import ImageFilter
    a = np.asarray(im.convert("RGB")).astype(np.int32)
    dist = np.sqrt(((a - 255) ** 2).sum(-1))
    bg = dist < tol
    lab, n = ndimage.label(bg)
    if n == 0:
        out = im.convert("RGBA")
        out.putalpha(Image.new("L", im.size, 255))
        return out
    border_labels = set(lab[0, :]) | set(lab[-1, :]) | set(lab[:, 0]) | set(lab[:, -1])
    border_labels.discard(0)
    mask = np.isin(lab, list(border_labels)) if border_labels else np.zeros_like(bg)
    alpha = np.where(mask, 0, 255).astype(np.uint8)
    out = im.convert("RGBA")
    am = Image.fromarray(alpha).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    out.putalpha(am)
    return out


def is_white_bg(im, tol=14):
    a = np.asarray(im.convert("RGB")).astype(np.int32)
    corners = np.concatenate([a[:12, :12].reshape(-1, 3), a[:12, -12:].reshape(-1, 3),
                              a[-12:, :12].reshape(-1, 3), a[-12:, -12:].reshape(-1, 3)])
    med = np.median(corners, axis=0)
    return float(np.sqrt(((med - 255) ** 2).sum())) < tol


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn, size, single, force_rembg in JOBS:
        p = os.path.join(SRC, fn)
        if not os.path.exists(p):
            print(f"[SKIP] {name}: {p}")
            continue
        im = Image.open(p)
        if force_rembg:
            rgba = rembg_cut(im)
            src = "rembg"
        elif has_alpha(im):
            rgba = im.convert("RGBA")
            src = "alpha"
        elif is_white_bg(im):
            rgba = white_bg_key(im)
            src = "whitekey"
        else:
            rgba = rembg_cut(im)
            src = "rembg"
        rgba = filter_components(rgba, single)
        bbox = rgba.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
        if bbox:
            rgba = rgba.crop(bbox)
        scale = size / max(rgba.size)
        rgba = rgba.resize((max(1, round(rgba.width * scale)),
                            max(1, round(rgba.height * scale))), Image.LANCZOS)
        out = os.path.join(OUT, name + ".png")
        rgba.save(out)
        cov = (np.asarray(rgba)[:, :, 3] > 8).mean()
        print(f"[{name}] via={src} -> {rgba.size} cov={cov:.1%}")
    print("DONE")


if __name__ == "__main__":
    main()
