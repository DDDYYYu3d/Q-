# -*- coding: utf-8 -*-
"""视频 -> 透明帧序列：
1. cv2 读视频，按目标 fps 抽帧
2. 逐帧 rembg 抠图（最大连通域去杂物）
3. 记录每帧"脚底中心"位置，统一画布对齐（消除播放抖动）
4. 输出 assets/anims/<name>/f000.png... + meta.json
"""
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))

_session = None


def rembg_cut(im):
    global _session
    from rembg import remove, new_session
    if _session is None:
        _session = new_session("u2net")
    return remove(im, session=_session)


def largest_component(rgba):
    arr = np.asarray(rgba).copy()
    m = arr[:, :, 3] > 8
    if not m.any():
        return rgba
    lab, n = ndimage.label(m)
    if n <= 1:
        return rgba
    sizes = ndimage.sum(m, lab, range(1, n + 1))
    keep = 1 + int(np.argmax(sizes))
    arr[:, :, 3][lab != keep] = 0
    return Image.fromarray(arr)


def main(video_path, out_name, target_fps=12, out_h=560):
    out_dir = os.path.join(HERE, "assets", "anims", out_name)
    os.makedirs(out_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    vw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    vh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"video: {vw}x{vh} @{fps:.1f}fps, {total} frames, {total / max(fps, 1):.1f}s")

    step = max(1, round(fps / target_fps))
    idx = saved = 0
    frames = []  # (PIL RGBA, foot_cx, foot_y)

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            rgba = rembg_cut(pil)
            rgba = largest_component(rgba)
            al = np.asarray(rgba)[:, :, 3]
            ys, xs = np.where(al > 8)
            if len(xs) < 50:
                idx += 1
                continue
            x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
            foot_cx = (x0 + x1) / 2.0
            foot_y = float(y1)
            crop = rgba.crop((x0, y0, x1 + 1, y1 + 1))
            # 统一高度
            scale = out_h / max(1, crop.height)
            nw = max(1, round(crop.width * scale))
            crop = crop.resize((nw, out_h), Image.LANCZOS)
            frames.append((crop, foot_cx - x0, out_h - 1))
            saved += 1
            if saved % 10 == 0:
                print(f"  {saved} frames...")
        idx += 1
    cap.release()

    if not frames:
        print("[FAIL] no frames extracted")
        sys.exit(1)

    # 统一画布对齐：所有帧脚底中心放在同一锚点
    max_w = max(f.width for f, _, _ in frames)
    ax = min(max(fc for _, fc, _ in frames), max_w - 4)   # 锚点 x
    ay = out_h - 1                                        # 锚点 y（底边）
    cw = max(max(f.width for f, _, _ in frames), ax) + 8
    ch = out_h + 8

    for i, (f, fc, fy) in enumerate(frames):
        canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        canvas.paste(f, (round(ax - fc), round(ay - fy)), f)
        canvas.save(os.path.join(out_dir, f"f{i:03d}.png"))

    meta = {"fps": target_fps, "count": len(frames), "w": cw, "h": ch,
            "anchor": [round(ax), round(ay)], "loop": True}
    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as fp:
        json.dump(meta, fp)
    print(f"DONE: {len(frames)} frames -> {out_dir}  canvas={cw}x{ch}")


if __name__ == "__main__":
    video = sys.argv[1] if len(sys.argv) > 1 else None
    name = sys.argv[2] if len(sys.argv) > 2 else "walk"
    if not video or not os.path.exists(video):
        print("usage: process_video_frames.py <video.mp4> <name>")
        sys.exit(1)
    main(video, name)
