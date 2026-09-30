# -*- coding: utf-8 -*-
"""效果预览图：在深色桌面背景上合成 桌宠 + 对话气泡 + 粒子装饰，用于确认可读性。"""
import os
import sys

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QImage, QLinearGradient, QPainter, QPixmap,
                           QRadialGradient)
from PySide6.QtWidgets import QApplication

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import main as M  # noqa: E402

W, H = 1040, 660


def main():
    app = QApplication(sys.argv)
    canvas = QImage(W, H, QImage.Format_ARGB32_Premultiplied)
    p = QPainter(canvas)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)

    # 深色壁纸（模拟用户桌面）
    g = QLinearGradient(0, 0, 0, H)
    g.setColorAt(0.0, QColor(16, 18, 26))
    g.setColorAt(1.0, QColor(34, 38, 52))
    p.fillRect(QRect(0, 0, W, H), g)
    halo = QRadialGradient(QPointF(360, 420), 320)
    halo.setColorAt(0.0, QColor(90, 120, 200, 45))
    halo.setColorAt(1.0, QColor(90, 120, 200, 0))
    p.fillRect(QRect(0, 0, W, H), halo)

    title = QFont("Microsoft YaHei UI", 11)
    title.setBold(True)
    p.setFont(title)
    p.setPen(QColor(180, 190, 210))
    p.drawText(QRectF(36, 26, 600, 30), Qt.AlignLeft | Qt.AlignVCenter,
               "深色桌面效果预览：对话气泡 + 粒子装饰")

    # 桌宠本体
    pet = QPixmap(os.path.join(M.ASSETS, "idle.png")).scaledToHeight(330, Qt.SmoothTransformation)
    px, py = 300, H - 60 - pet.height()
    p.drawPixmap(px, py, pet)

    # 气泡（复用程序里的真实绘制逻辑）
    pet_rect = QRect(px, py, pet.width(), pet.height())
    b = M.Bubble()
    b.popup("我是文韬，请多指教～", pet_rect, QRect(0, 0, W, H))
    p.drawPixmap(b.x(), b.y(), b.grab())

    # 粒子装饰（各类型展示一下）
    for key, x, y, s in (("sparkle", 396, 150, 40), ("star", 300, 205, 52),
                         ("heart", 430, 240, 46), ("note", 470, 320, 40),
                         ("confetti", 250, 150, 62), ("sparkle", 262, 320, 30)):
        pm = QPixmap(os.path.join(M.ASSETS, "particles", key + ".png"))
        if pm.isNull():
            continue
        pm = pm.scaledToHeight(s, Qt.SmoothTransformation)
        p.drawPixmap(x, y, pm)
        p.setFont(QFont("Microsoft YaHei UI", 8))
        p.setPen(QColor(150, 160, 180))
        p.drawText(x, y + pm.height() + 14, key)

    p.end()
    out = os.path.join(os.path.dirname(HERE), "效果预览.png")
    canvas.save(out)
    print("saved ->", out)


if __name__ == "__main__":
    main()
