# -*- coding: utf-8 -*-
"""
郭文韬桌宠 · PySide6 桌面宠物
- 透明、无边框、置顶窗口；左键拖动（带跑动姿势），滚轮缩放
- 单击轮流触发：跳跃 / 压扁回弹 / 左右抖动
- 互动随机显示简短中文气泡（不遮挡角色）
- 右键菜单：陪我聊聊天 / 摸摸头 / 喂吃的 / 让他走路 / 让他睡觉 / 跟随鼠标
             / 调整大小 / 置顶开关 / 退出程序
- 位置与大小记忆（保存在 %APPDATA%/WenTaoPet/config.json）
"""
import json
import math
import os
import random
import sys
import tempfile
import traceback

try:
    import winreg
except ImportError:
    winreg = None

from PySide6.QtCore import Qt, QTimer, QPoint, QPointF, QRect, QRectF, QVariantAnimation, QLockFile
from PySide6.QtGui import (QPixmap, QPainter, QTransform, QColor, QFont, QCursor,
                           QAction, QActionGroup, QIcon, QFontMetrics, QPainterPath,
                           QPolygonF, QPen)
from PySide6.QtWidgets import QApplication, QWidget, QMenu, QLabel, QSystemTrayIcon

APP_NAME = "WenTaoPet"
# 素材高 1200px：0.163 ≈ 默认显示高约 196px（缩放按素材像素计）
DEFAULT_SCALE = 0.163
MIN_SCALE, MAX_SCALE = 0.082, 0.875
NORM_H = 1200.0          # 素材归一化高度（帧动画按此标度折算显示大小）

MARGIN_X = 26        # 窗口左右留白（容纳抖动/压扁形变）
MARGIN_TOP = 30      # 顶部留白（容纳旋转 + Zzz）
MARGIN_BOTTOM = 6

FOODS = ["🍗", "🍜", "🍚", "🍰", "🧋", "🍎", "🍫", "🥟"]

LINES = {
    "jump":   ["哇——起飞！", "看我的弹跳力！", "一跃而上～", "这高度还行吧？"],
    "squash": ["哎哟，压扁了", "变·成·饼", "噗——弹回来啦", "别压啦别压啦"],
    "shake":  ["摇一摇，提神醒脑", "晃得我头晕…", "跟着节奏摇～", "左右左右！"],
    "pat":    ["好舒服呀，再摸摸", "头发要乱啦～", "乖巧.jpg", "嗯嗯，最喜欢这个了"],
    "feed":   ["谢谢投喂，真香！", "减脂期…算了，开吃！", "好吃到转圈圈～", "还想再来一份"],
    "walk_start": ["散步去咯～", "目标：屏幕另一头！", "走走走，活动筋骨"],
    "walk_end":   ["到站！今天两万步", "呼，有点累啦", "这条路我可熟了"],
    "sleep":  ["我先睡会儿…晚安", "别吵，充电中…", "梦里什么都有"],
    "wake":   ["谁！谁叫我！", "再睡五分钟……好吧起了", "哈欠——醒啦"],
    "chat":   ["来啦来啦，聊点什么？", "我是文韬，请多指教", "今天也要加油鸭！",
               "我发现一个真相——想听吗？", "逻辑链闭环了！", "要不要一起推理一下？",
               "忙归忙，记得喝水哦", "最近有点想喝奶茶", "有我在，别怕"],
    "follow_on":  ["跟紧你啦，走哪我跟哪～", "小尾巴上线！"],
    "follow_off": ["好吧，我自己待会儿"],
    "idle":   ["（发呆中）", "无聊，戳戳我嘛", "我在看着你哦", "今天也要元气满满！",
               "要不要一起推理？"],
}


def pick_line(key):
    return random.choice(LINES[key])


def base_dir():
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


ASSETS = os.path.join(base_dir(), "assets")


def config_dir():
    if "--selftest" in sys.argv:
        # 自测时隔离配置，避免污染真实用户配置
        d = os.path.join(tempfile.gettempdir(), APP_NAME + "_selftest")
    else:
        d = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


CONFIG_FILE = os.path.join(config_dir(), "config.json")
LOG_FILE = os.path.join(config_dir(), "error.log")

SPRITES = {
    "idle":  "idle.png",
    "happy": "happy.png",
    "shy":   "shy.png",
    "walk":  "walk.png",
    "sleep": "sleep.png",
    "chat":  "chat.png",
    "wave":  "wave.png",
    "eat":   "eat.png",
    "think": "think.png",
    "surprise": "surprise.png",
}

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "WenTaoPet"

MENU_QSS = """
QMenu{background:rgba(250,250,252,248);border:1px solid rgba(0,0,0,40);border-radius:10px;
padding:6px;font-family:'Microsoft YaHei UI';font-size:13px;color:#222;}
QMenu::item{padding:6px 24px 6px 14px;border-radius:6px;background:transparent;}
QMenu::item:selected{background:#4f8cff;color:white;}
QMenu::separator{height:1px;background:rgba(0,0,0,28);margin:4px 10px;}
QMenu::item:disabled{color:#aaa;}
"""


class Bubble(QWidget):
    """角色对话气泡：圆角矩形 + 指向角色的小尾巴。
    白底深字 + 描边 + 轻微投影，保证深色桌面上也看得清。"""

    PAD_X, PAD_Y = 14, 9
    TAIL = 9
    MAX_TEXT_W = 230
    RADIUS = 12

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._text = ""
        self._side = "top"      # top: 气泡在角色上方、尾巴朝下（另有 right / left）
        self._tail_pos = 0      # 尾巴尖端位置（窗口坐标）
        self._font = QFont("Microsoft YaHei UI", 10)
        self._font.setBold(True)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.fade_out)
        self._anim = None

    def _text_size(self):
        fm = QFontMetrics(self._font)
        rect = fm.boundingRect(QRect(0, 0, self.MAX_TEXT_W, 10000),
                               Qt.TextWordWrap | Qt.AlignLeft, self._text)
        return max(rect.width(), 24), max(rect.height(), fm.height())

    def popup(self, text, pet_rect, screen):
        self._text = text
        tw, th = self._text_size()
        w = tw + self.PAD_X * 2
        h = th + self.PAD_Y * 2 + self.TAIL
        cx = pet_rect.center().x()
        # 默认：气泡放在角色上方，尾巴朝下对准角色
        self._side = "top"
        x = cx - w // 2
        y = pet_rect.top() - h + 2
        if y < screen.top() + 4:                       # 上方放不下 → 右侧，尾巴朝左
            self._side = "right"
            x = pet_rect.right() - 4
            y = pet_rect.top() + 6
            if x + w > screen.right() - 4:             # 右侧放不下 → 左侧，尾巴朝右
                self._side = "left"
                x = pet_rect.left() - w + 4
                if x < screen.left() + 4:              # 都放不下 → 强行放上方
                    self._side = "top"
                    x = cx - w // 2
                    y = screen.top() + 4
        x = max(screen.left() + 4, min(x, screen.right() - w - 4))
        y = max(screen.top() + 4, min(y, screen.bottom() - h - 4))
        self.resize(w, h)
        self.move(x, y)
        if self._side == "top":
            self._tail_pos = max(self.RADIUS + 6, min(cx - x, w - self.RADIUS - 6))
        else:
            self._tail_pos = max(self.RADIUS + 6,
                                 min(pet_rect.center().y() - y, h - self.RADIUS - 6))
        self.setWindowOpacity(1.0)
        self.show()
        self.raise_()
        self._hide_timer.start(2800)

    def _shape_path(self):
        w, h, t = self.width(), self.height(), self.TAIL
        path = QPainterPath()
        if self._side == "top":
            path.addRoundedRect(QRectF(0.75, 0.75, w - 1.5, h - t - 0.75),
                                self.RADIUS, self.RADIUS)
            tx = self._tail_pos
            path.addPolygon(QPolygonF([QPointF(tx - 8, h - t - 1.0),
                                       QPointF(tx, h - 0.8),
                                       QPointF(tx + 8, h - t - 1.0)]))
        elif self._side == "right":
            path.addRoundedRect(QRectF(t + 0.75, 0.75, w - t - 1.5, h - 1.5),
                                self.RADIUS, self.RADIUS)
            ty = self._tail_pos
            path.addPolygon(QPolygonF([QPointF(t + 1.0, ty - 8),
                                       QPointF(0.8, ty),
                                       QPointF(t + 1.0, ty + 8)]))
        else:
            path.addRoundedRect(QRectF(0.75, 0.75, w - t - 1.5, h - 1.5),
                                self.RADIUS, self.RADIUS)
            ty = self._tail_pos
            path.addPolygon(QPolygonF([QPointF(w - t - 1.0, ty - 8),
                                       QPointF(w - 0.8, ty),
                                       QPointF(w - t - 1.0, ty + 8)]))
        return path

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        path = self._shape_path()
        # 投影：深色桌面上把气泡"托"起来
        p.save()
        p.translate(0, 1.8)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 80))
        p.drawPath(path)
        p.restore()
        # 底面 + 描边
        p.setPen(QPen(QColor(56, 62, 78, 200), 1.6))
        p.setBrush(QColor(255, 255, 255, 252))
        p.drawPath(path)
        # 文字
        w, h, t = self.width(), self.height(), self.TAIL
        left = self.PAD_X + (t if self._side != "top" else 0)
        right_pad = self.PAD_X + (t if self._side == "left" else 0)
        body_h = h - (t if self._side == "top" else 0)
        tr = QRectF(left, self.PAD_Y, w - left - right_pad, body_h - self.PAD_Y * 2)
        p.setPen(QColor(18, 20, 26))
        p.setFont(self._font)
        p.drawText(tr, Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignVCenter, self._text)

    def fade_out(self):
        if not self.isVisible():
            return
        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setDuration(220)
        self._anim.valueChanged.connect(lambda v: self.setWindowOpacity(float(v)))
        self._anim.finished.connect(self.hide)
        self._anim.start()


class Particle(QWidget):
    """粒子装饰：会旋转、上飘、淡出的小贴图（星星/爱心/音符…）。"""

    def __init__(self, pixmap):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._pm = pixmap
        self.resize(pixmap.size())
        self._rot = 0.0

    def set_rot(self, deg):
        self._rot = deg
        self.update()

    def paintEvent(self, event):
        if self._pm.isNull():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.translate(self.width() / 2.0, self.height() / 2.0)
        p.rotate(self._rot)
        p.drawPixmap(QPointF(-self._pm.width() / 2.0, -self._pm.height() / 2.0), self._pm)


class FoodWidget(QLabel):
    """被投喂的食物，飞向角色。"""

    def __init__(self, emoji):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setText(emoji)
        self.setStyleSheet("font-size:36px;")
        self.adjustSize()
        self._anim = None

    def fly(self, start, target, on_done):
        self.move(start)
        self.show()
        self.raise_()
        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(650)

        def step(t):
            t = float(t)
            x = start.x() + (target.x() - start.x()) * t
            y = start.y() + (target.y() - start.y()) * t - int(70 * math.sin(math.pi * t))
            self.move(QPoint(round(x), round(y)))

        def done():
            self.hide()
            self.deleteLater()
            on_done()

        self._anim.valueChanged.connect(step)
        self._anim.finished.connect(done)
        self._anim.start()


class Pet(QWidget):
    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.stay_top = True
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        # ---- 素材 ----
        self.pixmaps = {}
        for k, f in SPRITES.items():
            pm = QPixmap(os.path.join(ASSETS, f))
            if pm.isNull():
                pm = QPixmap(200, 260)
                pm.fill(QColor(180, 190, 210, 220))
            self.pixmaps[k] = pm

        # ---- 粒子装饰贴图（AI 生成）----
        self.particle_src = {}
        pdir = os.path.join(ASSETS, "particles")
        for k in ("star", "heart", "note", "sparkle", "confetti"):
            pp = QPixmap(os.path.join(pdir, k + ".png"))
            if not pp.isNull():
                self.particle_src[k] = pp
        self._particles = []

        # ---- 帧动画（图生视频抽帧，assets/anims/<name>/）----
        self.anims = {}
        anim_root = os.path.join(ASSETS, "anims")
        if os.path.isdir(anim_root):
            for name in sorted(os.listdir(anim_root)):
                mpath = os.path.join(anim_root, name, "meta.json")
                if not os.path.isfile(mpath):
                    continue
                try:
                    with open(mpath, "r", encoding="utf-8") as fp:
                        meta = json.load(fp)
                    adir = os.path.join(anim_root, name)
                    files = sorted(f for f in os.listdir(adir) if f.endswith(".png"))
                    frames = [QPixmap(os.path.join(adir, f)) for f in files]
                    frames = [f for f in frames if not f.isNull()]
                    if frames:
                        self.anims[name] = {
                            "frames": frames,
                            "fps": int(meta.get("fps", 12)),
                            "w": int(meta.get("w", frames[0].width())),
                            "h": int(meta.get("h", frames[0].height())),
                        }
                except Exception:
                    pass
        self.anim_name = None       # 当前帧动画名（None = 单图模式）
        self.anim_frame_idx = 0.0
        self._anim_scaled = {}      # (name, k, dpr) -> 缩放后的帧列表

        # ---- 状态 ----
        self.scale_f = DEFAULT_SCALE
        self.sprite_key = "idle"
        self.mode = "idle"            # idle / walk / follow / sleep
        self.busy = False             # 一次性动画播放中
        self.flip = False             # 水平镜像（朝向）
        self.bobbing = False          # 跑动上下摆动
        self.bob_phase = 0.0
        self.dim = 0.0                # 睡觉变暗程度
        self.idle_anim = "breathe"    # 待机动画：breathe / float / sway
        self.click_step = 0           # 点击轮换：跳跃→压扁→抖动
        self.rot = 0.0
        self.dx = 0.0
        self.dy = 0.0
        self.sx = 1.0
        self.sy = 1.0
        self._anims = []
        self._press_global = None
        self._press_pos = None
        self._moved = False
        self._last_flip_x = 0
        self._walk_dir = 1
        self._walk_left = 0
        self._rendered = None
        self._ox = 0.0
        self._oy = 0.0
        self._lw = 0.0
        self._lh = 0.0
        self._mask_key = None
        self._spm_key = None
        self._spm = None

        self.bubble = Bubble()
        self.food = None

        # ---- 定时器 ----
        self.tick = QTimer(self)
        self.tick.setInterval(33)
        self.tick.timeout.connect(self.on_tick)
        self.tick.start()

        self.idle_timer = QTimer(self)
        self.idle_timer.setInterval(30000)
        self.idle_timer.timeout.connect(self.on_idle_timer)
        self.idle_timer.start()

        self._revert_timer = QTimer(self)
        self._revert_timer.setSingleShot(True)
        self._revert_timer.timeout.connect(self.revert_sprite)

        self.load_config()
        self.apply_geometry()

        scr = self.screen_avail()
        self.move(scr.right() - self.width() - 60, scr.bottom() - self.height() - 60)
        pos = self._saved_pos
        if pos is not None:
            self.move(pos)
        self.clamp_into_screen()
        app_icon = os.path.join(ASSETS, "pet.ico")
        if os.path.exists(app_icon):
            QApplication.instance().setWindowIcon(QIcon(app_icon))

        # ---- 托盘图标（防丢失 + 快捷退出）----
        try:
            self.tray = QSystemTrayIcon(QIcon(app_icon) if os.path.exists(app_icon)
                                        else QIcon(self.pixmaps["idle"]), self)
            tmenu = QMenu()
            tmenu.setStyleSheet(MENU_QSS)
            tmenu.addAction("显示桌宠", self.show_from_tray)
            ta = QAction("窗口置顶", tmenu, checkable=True)
            ta.setChecked(self.stay_top)
            ta.toggled.connect(self.toggle_top)
            tmenu.addAction(ta)
            tmenu.addSeparator()
            tmenu.addAction("退出程序", self.quit_app)
            self.tray.setContextMenu(tmenu)
            self.tray.setToolTip("郭文韬桌宠")
            self.tray.show()
        except Exception:
            self.tray = None

    def show_from_tray(self):
        self.show()
        self.raise_()
        self.clamp_into_screen()

    # ------------------------------------------------ 基础几何
    def screen_avail(self):
        scr = self.screen() or QApplication.primaryScreen()
        return scr.availableGeometry()

    def base_size(self):
        a = self.anims.get(self.anim_name) if self.anim_name else None
        if a is not None:
            k = NORM_H / max(1, a["h"]) * self.scale_f
            return round(a["w"] * k), round(a["h"] * k)
        pm = self.pixmaps[self.sprite_key]
        return round(pm.width() * self.scale_f), round(pm.height() * self.scale_f)

    def apply_geometry(self):
        bw, bh = self.base_size()
        self.resize(bw + MARGIN_X * 2, bh + MARGIN_TOP + MARGIN_BOTTOM)

    def anchor_move(self, cx, bottom):
        """以底部中心为锚点移动窗口。"""
        self.move(round(cx - self.width() / 2), round(bottom - self.height() + 1))

    def clamp_into_screen(self):
        av = self.screen_avail()
        g = self.geometry()
        nx = min(max(g.x(), av.left() + 2), max(av.left() + 2, av.right() - g.width() - 1))
        ny = min(max(g.y(), av.top() + 2), max(av.top() + 2, av.bottom() - g.height() - 1))
        if nx != g.x() or ny != g.y():
            self.move(nx, ny)

    # ------------------------------------------------ 配置
    def load_config(self):
        self._saved_pos = None
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as fp:
                cfg = json.load(fp)
            if "scale" in cfg:
                raw_scale = float(cfg["scale"])
                # 旧配置未记录素材高度时按 640 处理（历史版本素材高度）
                cfg_asset_h = float(cfg.get("asset_h", 640) or 640)
                cur_h = float(self.pixmaps["idle"].height() or 1)
                # 素材分辨率变化时折算，保持桌宠视觉大小不变
                raw_scale = raw_scale * cfg_asset_h / cur_h
            else:
                raw_scale = DEFAULT_SCALE
            self.scale_f = max(MIN_SCALE, min(MAX_SCALE, raw_scale))
            self.idle_anim = cfg.get("idle_anim", "breathe")
            if self.idle_anim not in ("breathe", "float", "sway"):
                self.idle_anim = "breathe"
            if "x" in cfg and "y" in cfg:
                self._saved_pos = QPoint(int(cfg["x"]), int(cfg["y"]))
            self.stay_top = bool(cfg.get("stay_top", True))
            self.setWindowFlag(Qt.WindowStaysOnTopHint, self.stay_top)
        except Exception:
            pass

    def save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as fp:
                json.dump({"x": self.x(), "y": self.y(), "scale": self.scale_f,
                           "stay_top": self.stay_top, "idle_anim": self.idle_anim,
                           "asset_h": self.pixmaps["idle"].height()}, fp)
        except Exception:
            pass

    # ------------------------------------------------ 绘制
    def _dpr(self):
        try:
            return float(self.devicePixelRatioF() or 1.0)
        except Exception:
            return 1.0

    def _get_spm(self):
        bw, bh = self.base_size()
        dpr = self._dpr()
        key = (self.sprite_key, bw, bh, dpr)
        if self._spm_key != key or self._spm is None:
            pm = self.pixmaps[self.sprite_key]
            # 按物理像素缩放：高 DPI 屏（125%/150%）下也保持清晰
            spm = pm.scaled(round(bw * dpr), round(bh * dpr),
                            Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            spm.setDevicePixelRatio(dpr)
            self._spm = spm
            self._spm_key = key
        return self._spm

    def _get_anim_spm(self):
        """当前帧动画的缩放帧（带 dpr 与缓存）。"""
        a = self.anims[self.anim_name]
        k = NORM_H / max(1, a["h"]) * self.scale_f
        dpr = self._dpr()
        key = (self.anim_name, round(k, 4), dpr)
        cached = self._anim_scaled.get(key)
        if cached is None:
            cached = []
            for f in a["frames"]:
                spm = f.scaled(round(a["w"] * k * dpr), round(a["h"] * k * dpr),
                               Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                spm.setDevicePixelRatio(dpr)
                cached.append(spm)
            self._anim_scaled[key] = cached
        i = int(self.anim_frame_idx) % len(cached)
        return cached[i]

    def _render(self):
        if self.anim_name and self.anims.get(self.anim_name):
            spm = self._get_anim_spm()
        else:
            spm = self._get_spm()
        bw, bh = self.base_size()
        t = QTransform()
        t.translate(MARGIN_X + bw / 2.0, MARGIN_TOP + bh)
        t.rotate(self.rot)
        t.scale((-1 if self.flip else 1) * self.sx, self.sy)
        t.translate(-bw / 2.0, -bh)
        dpr = self._dpr()
        rendered = spm.transformed(t, Qt.SmoothTransformation)
        rendered.setDevicePixelRatio(dpr)
        self._rendered = rendered
        lw = rendered.width() / dpr          # 逻辑宽高
        lh = rendered.height() / dpr
        self._lw, self._lh = lw, lh
        self._ox = (self.width() - lw) / 2.0
        self._oy = self.height() - MARGIN_BOTTOM - lh
        # 蒙版：让透明区域不拦截鼠标（对齐到逻辑坐标）
        key = (self.sprite_key, bw, bh, round(self.rot), round(self.sx, 2),
               round(self.sy, 2), self.flip, dpr)
        if key != self._mask_key:
            self._mask_key = key
            small = rendered.scaled(max(1, round(lw)), max(1, round(lh)),
                                    Qt.IgnoreAspectRatio, Qt.FastTransformation)
            mask = small.mask()
            if not mask.isNull():
                self.setMask(QRegion_from_bitmap(mask).translated(round(self._ox),
                                                                  round(self._oy)))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        if self._rendered is not None:
            p.drawPixmap(QPointF(self._ox, self._oy), self._rendered)
            if self.dim > 0.01:
                p.fillRect(QRectF(self._ox, self._oy, self._lw, self._lh),
                           QColor(6, 10, 28, int(150 * self.dim)))
        if self.mode == "sleep":
            self._draw_zzz(p)

    def _draw_zzz(self, p):
        self.bob_phase_z = getattr(self, "bob_phase_z", 0.0)
        base_x = round(self._ox + self._lw - 6)
        base_y = int(max(14, self._oy + 6))
        for i in range(3):
            a = int(120 + 100 * math.sin(self.bob_phase_z * 2 + i))
            a = max(40, min(230, a))
            size = 11 + i * 3
            rise = (math.sin(self.bob_phase_z + i * 0.9) + 1) * 5
            p.setPen(QColor(110, 150, 255, a))
            p.setFont(QFont("Segoe UI", size, QFont.Bold))
            p.drawText(QPoint(base_x - i * 16, base_y - i * 8 - rise), "Z")

    # ------------------------------------------------ 主循环
    def on_tick(self):
        # 帧动画推进（tick 30fps → 按 anim fps 换算步进）
        if self.anim_name and self.anims.get(self.anim_name):
            a = self.anims[self.anim_name]
            self.anim_frame_idx = (self.anim_frame_idx + a["fps"] / 30.0) % len(a["frames"])

        if self.mode == "walk":
            self.bobbing = True
            step = max(1, round(3 * self.scale_f / DEFAULT_SCALE))
            self.move(self.x() + self._walk_dir * step, self.y())
            av = self.screen_avail()
            if self._walk_dir > 0 and self.x() + self.width() >= av.right() - 2:
                self._walk_dir = -1
            elif self._walk_dir < 0 and self.x() <= av.left() + 2:
                self._walk_dir = 1
            self.flip = self._walk_dir < 0
            self._walk_left -= 1
            if self._walk_left <= 0:
                self.end_walk()
        elif self.mode == "follow":
            self._follow_step()
        elif self.mode == "sleep":
            self.dim = min(1.0, self.dim + 0.05)
            self.bobbing = False
        else:  # idle
            self.dim = max(0.0, self.dim - 0.06)

        if self.mode == "sleep":
            self.bob_phase_z = getattr(self, "bob_phase_z", 0.0) + 0.08

        anim_on = bool(self.anim_name and self.anims.get(self.anim_name))
        if self.bobbing and not self.busy:
            if anim_on:
                # 帧动画自带动作，不再叠加摆动
                self.rot = 0.0
                self.dy = 0.0
                self.sx = 1.0
                self.sy = 1.0
            else:
                self.bob_phase += 0.26
                self.rot = math.sin(self.bob_phase) * 7
                self.dy = -abs(math.sin(self.bob_phase)) * 4
                self.sx = 1.0
                self.sy = 1.0
        elif not self.busy:
            self.rot *= 0.6
            self.dy *= 0.6
            if abs(self.rot) < 0.2:
                self.rot = 0.0
            if abs(self.dy) < 0.2:
                self.dy = 0.0
            if anim_on:
                # 帧动画自带动作（呼吸/摇摆等已录进帧里）
                self.sx = 1.0
                self.sy = 1.0
            else:
                # 待机动画（缓慢周期）
                self.bob_phase += 0.03
                b = math.sin(self.bob_phase)
                if self.idle_anim == "float":
                    self.sx = self.sy = 1.0
                    self.dy = -14 * b                      # 上下漂浮（幅度已明显）
                    self.rot = 3 * math.sin(self.bob_phase * 0.7)
                elif self.idle_anim == "sway":
                    self.sx = self.sy = 1.0
                    self.rot = 11 * b                      # 左右摇摆
                else:  # breathe
                    self.sy = 1.0 + 0.032 * b              # 呼吸起伏
                    self.sx = 1.0 - 0.018 * b

        self._render()

    def _follow_step(self):
        target = QCursor.pos()
        c = self.geometry().center()
        dxv = target.x() - c.x()
        dyv = target.y() - (c.y() + self.height() // 5)
        dist = math.hypot(dxv, dyv)
        if dist < max(18.0, self.width() * 0.18):
            self.bobbing = False
            return
        self.bobbing = True
        sp = max(2.2, dist * 0.055)
        nx = self.x() + dxv / dist * sp
        ny = self.y() + dyv / dist * sp
        self.move(round(nx), round(ny))
        self.clamp_into_screen()
        if abs(dxv) > 4:
            self.flip = dxv < 0

    def on_idle_timer(self):
        if self.mode == "idle" and not self.busy and not self.bubble.isVisible():
            if random.random() < 0.30:
                self.show_line("idle")
            if random.random() < 0.30:
                self.flash_sprite("think", 2400)   # 偶尔托腮发会儿呆

    # ------------------------------------------------ 气泡 / 精灵切换
    def show_line(self, key):
        self.bubble.popup(pick_line(key), self.frameGeometry(), self.screen_avail())

    # ------------------------------------------------ 粒子装饰
    def spawn_particles(self, keys=None, count=5):
        """在角色身上撒一把粒子（星星/爱心/音符…），上飘、旋转、淡出。"""
        if not self.particle_src:
            return
        keys = keys or ["sparkle", "star"]
        g = self.geometry()
        base = max(0.55, min(1.9, self.scale_f / DEFAULT_SCALE))
        cx = g.center().x()
        cy = g.top() + int(g.height() * 0.34)
        spread = g.width() * 0.45
        rise = max(80.0, g.height() * 0.85)
        for _ in range(count):
            src = self.particle_src[random.choice(keys)]
            size = int(random.uniform(20, 34) * base)
            pm = src.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pw = Particle(pm)
            sx = cx + random.uniform(-spread, spread)
            sy = cy + random.uniform(-6, 14)
            drift = random.uniform(-28, 28)
            r0 = random.uniform(-25, 25)
            rd = random.uniform(-170, 170)
            pw.move(round(sx), round(sy))
            pw.setWindowOpacity(0.0)
            pw.show()
            pw.raise_()
            self._particles.append(pw)

            anim = QVariantAnimation(self)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setDuration(random.randint(900, 1500))

            def step(t, pw=pw, sx=sx, sy=sy, drift=drift, rise=rise, r0=r0, rd=rd):
                t = float(t)
                ease = 1 - (1 - t) * (1 - t)          # 先快后慢
                pw.move(round(sx + drift * t), round(sy - rise * ease))
                pw.setWindowOpacity(min(1.0, t * 5) * (1.0 - t * t))
                pw.set_rot(r0 + rd * t)

            def done(pw=pw, anim=anim):
                pw.hide()
                pw.deleteLater()
                if pw in self._particles:
                    self._particles.remove(pw)
                if anim in self._anims:
                    self._anims.remove(anim)

            anim.valueChanged.connect(step)
            anim.finished.connect(done)
            self._anims.append(anim)
            anim.start()

    def set_sprite(self, key):
        if key in self.anims:
            self.anim_name = key           # 有帧动画 → 播放帧序列
        else:
            self.anim_name = None          # 无帧动画 → 单图模式
        self.sprite_key = key
        g = self.geometry()
        self.apply_geometry()
        self.anchor_move(g.center().x(), g.bottom())
        self.clamp_into_screen()
        self._render()

    def context_sprite(self):
        return {"walk": "walk", "sleep": "sleep"}.get(self.mode, "idle")

    def revert_sprite(self):
        self.set_sprite(self.context_sprite())

    def flash_sprite(self, key, ms=1500):
        self.set_sprite(key)
        self._revert_timer.start(ms)

    # ------------------------------------------------ 一次性动画
    def one_shot(self, dur, fn, on_end=None):
        a = QVariantAnimation(self)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setDuration(dur)
        a.valueChanged.connect(lambda v: fn(float(v)))

        def fin():
            if a in self._anims:
                self._anims.remove(a)
            if on_end:
                on_end()

        a.finished.connect(fin)
        self._anims.append(a)
        a.start()

    def trigger_interaction(self):
        acts = [("jump", self.do_jump), ("squash", self.do_squash), ("shake", self.do_shake)]
        name, fn = acts[self.click_step % len(acts)]
        self.click_step += 1
        if name == "shake":
            # 抖动会让角色"惊讶"（该档不移动窗口，切图安全）
            self.flash_sprite("surprise", 1000)
        fn()
        self.spawn_particles(["sparkle"], 4)
        self.show_line(name)

    def do_jump(self):
        if self.busy:
            return
        self.busy = True
        h = self.pixmaps[self.sprite_key].height() * self.scale_f * 0.85
        x0, y0 = self.x(), self.y()

        def fn(t):
            self.move(x0, round(y0 - h * 4 * t * (1 - t)))

        def end():
            self.move(x0, y0)
            self.busy = False
            self.do_squash(quick=True)   # 落地小回弹

        self.one_shot(520, fn, end)

    def do_squash(self, quick=False):
        if self.busy and not quick:
            return
        self.busy = True
        dur = 170 if quick else 480
        amp = 0.16 if quick else 0.30

        def fn(t):
            s = math.sin(math.pi * t)
            self.sx = 1 + amp * s
            self.sy = 1 - amp * 1.05 * s

        def end():
            self.sx = self.sy = 1.0
            self.busy = False

        self.one_shot(dur, fn, end)

    def do_shake(self):
        if self.busy:
            return
        self.busy = True

        def fn(t):
            self.dx = 10 * math.sin(6 * math.pi * t)
            self.rot = 4 * math.sin(6 * math.pi * t)

        def end():
            self.dx = 0.0
            self.rot = 0.0
            self.busy = False

        self.one_shot(620, fn, end)

    # ------------------------------------------------ 模式
    def start_walk(self):
        self.wake(silent=True)
        self.mode = "walk"
        self.set_sprite("walk")
        self._walk_dir = random.choice((-1, 1))
        self.flip = self._walk_dir < 0
        self._walk_left = random.randint(250, 420)
        self.show_line("walk_start")

    def end_walk(self):
        self.mode = "idle"
        self.set_sprite("idle")
        self.show_line("walk_end")

    def start_sleep(self):
        self.mode = "sleep"
        self.set_sprite("sleep")
        self.show_line("sleep")

    def wake(self, silent=False):
        was_sleeping = self.mode == "sleep"
        if was_sleeping and not silent:
            self.show_line("wake")
        self.mode = "idle"
        self.dim = 0.0
        if self.sprite_key == "sleep":
            self.set_sprite("idle")
        if was_sleeping and not silent:
            self.flash_sprite("wave", 1400)   # 醒来挥手

    def toggle_follow(self, on):
        if on:
            self.wake(silent=True)
            self.mode = "follow"
            self.flash_sprite("wave", 1400)   # 挥手说"跟紧你啦"
            self.show_line("follow_on")
        elif self.mode == "follow":
            self.mode = "idle"
            self.set_sprite("idle")
            self.show_line("follow_off")

    def stop_auto_modes(self):
        if self.mode in ("walk", "follow"):
            self.mode = "idle"
            self.set_sprite("idle")

    # ------------------------------------------------ 互动
    def pat(self):
        self.wake(silent=True)
        self.flash_sprite("shy", 1600)
        self.do_squash(quick=True)
        self.spawn_particles(["heart", "star"], 5)
        self.show_line("pat")

    def feed(self):
        self.wake(silent=True)
        g = self.geometry()
        target = QPoint(g.center().x() - 12, g.top() + int(self.height() * 0.42))
        start = QPoint(g.center().x() + 150, g.top() - 70)
        self.food = FoodWidget(random.choice(FOODS))

        def on_fed():
            self.flash_sprite("eat", 1800)    # 换成吃饭姿势
            self.do_squash(quick=True)
            self.spawn_particles(["heart", "confetti"], 6)
            self.show_line("feed")

        self.food.fly(start, target, on_fed)

    def chat(self):
        self.wake(silent=True)
        self.flash_sprite("chat", 6000)
        self.spawn_particles(["note", "star"], 4)
        self.show_line("chat")

    # ------------------------------------------------ 缩放
    def set_scale(self, s):
        g = self.geometry()
        self.scale_f = max(MIN_SCALE, min(MAX_SCALE, s))
        self.apply_geometry()
        self.anchor_move(g.center().x(), g.bottom())
        self.clamp_into_screen()
        self._render()
        self.save_config()

    def wheelEvent(self, e):
        d = e.angleDelta().y()
        if d == 0:
            return
        self.set_scale(self.scale_f * (1.12 if d > 0 else 1 / 1.12))

    # ------------------------------------------------ 菜单
    def show_menu(self, gpos):
        m = QMenu(self)
        m.setStyleSheet(MENU_QSS)
        m.addAction("陪我聊聊天", self.chat)
        m.addAction("摸摸头", self.pat)
        m.addAction("喂吃的", self.feed)
        m.addAction("让他走路", self.start_walk)
        m.addAction("让他睡觉", self.start_sleep)
        m.addSeparator()
        af = QAction("跟随鼠标", m, checkable=True)
        af.setChecked(self.mode == "follow")
        af.toggled.connect(self.toggle_follow)
        m.addAction(af)
        sm = m.addMenu("调整大小")
        sm.addAction("放大一点", lambda: self.set_scale(self.scale_f * 1.15))
        sm.addAction("缩小一点", lambda: self.set_scale(self.scale_f / 1.15))
        sm.addAction("恢复默认", lambda: self.set_scale(DEFAULT_SCALE))
        am = m.addMenu("待机动画")
        ag = QActionGroup(am)
        ag.setExclusive(True)
        for key, label in (("breathe", "呼吸"), ("float", "漂浮"), ("sway", "摇摆")):
            a = QAction(label, am, checkable=True)
            a.setChecked(self.idle_anim == key)
            a.triggered.connect(lambda checked=False, k=key: self.set_idle_anim(k))
            ag.addAction(a)
            am.addAction(a)
        at = QAction("窗口置顶", m, checkable=True)
        at.setChecked(self.stay_top)
        at.toggled.connect(self.toggle_top)
        m.addAction(at)
        au = QAction("开机自启", m, checkable=True)
        au.setChecked(self.is_autostart())
        au.toggled.connect(self.toggle_autostart)
        m.addAction(au)
        m.addSeparator()
        m.addAction("退出程序", self.quit_app)
        m.exec(gpos)

    # ------------------------------------------------ 待机动画 / 开机自启
    def set_idle_anim(self, key):
        if key in ("breathe", "float", "sway"):
            self.idle_anim = key
            self.save_config()

    @staticmethod
    def _exe_path():
        if getattr(sys, "frozen", False):
            return sys.executable
        return os.path.abspath(sys.argv[0])

    def is_autostart(self):
        if winreg is None:
            return False
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
                val, _ = winreg.QueryValueEx(key, RUN_VALUE)
                return os.path.normcase(str(val).strip('"')) == os.path.normcase(self._exe_path())
        except OSError:
            return False

    def toggle_autostart(self, on):
        if winreg is None or not getattr(sys, "frozen", False):
            return   # 仅打包后的 exe 支持开机自启
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                if on:
                    winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, f'"{self._exe_path()}"')
                else:
                    try:
                        winreg.DeleteValue(key, RUN_VALUE)
                    except FileNotFoundError:
                        pass
        except OSError:
            pass

    def toggle_top(self, on):
        self.stay_top = bool(on)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.stay_top)
        self.show()
        self.save_config()

    def quit_app(self):
        self.save_config()
        self.bubble.close()
        if self.tray is not None:
            self.tray.hide()
        QApplication.instance().quit()

    # ------------------------------------------------ 鼠标
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            if self.mode == "sleep":
                self.wake()
                return
            if self.busy:
                return
            self._press_global = e.globalPosition().toPoint()
            self._press_pos = self.pos()
            self._moved = False
        elif e.button() == Qt.RightButton:
            if self.mode == "sleep":
                self.wake(silent=True)
            self.show_menu(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        if self._press_global is None:
            return
        gp = e.globalPosition().toPoint()
        if not self._moved and (gp - self._press_global).manhattanLength() > 8:
            self._moved = True
            self.stop_auto_modes()
        if self._moved:
            self.bobbing = True
            dx = gp.x() - self._press_global.x()
            if abs(dx - self._last_flip_x) > 10:
                self.flip = dx < 0
                self._last_flip_x = dx
            self.move(self._press_pos + (gp - self._press_global))
            self.clamp_into_screen()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self._press_global is not None:
            was_moved = self._moved
            self._press_global = None
            self._moved = False
            self.bobbing = False
            if not was_moved:
                self.trigger_interaction()
            else:
                self.save_config()


def QRegion_from_bitmap(bitmap):
    from PySide6.QtGui import QRegion
    return QRegion(bitmap)


def excepthook(tp, val, tb):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fp:
            fp.write("".join(traceback.format_exception(tp, val, tb)) + "\n")
    except Exception:
        pass
    sys.__excepthook__(tp, val, tb)


def run_selftest(app, pet):
    print("[selftest] start, anims loaded:", sorted(pet.anims.keys()))
    steps = [
        (200, lambda: pet.show()),
        (300, lambda: pet.show_line("idle")),
        (500, pet.do_jump),
        (1300, pet.do_squash),
        (1700, pet.do_shake),
        (2100, pet.feed),
        (2600, pet.pat),
        (2900, pet.start_walk),
        (3200, pet.end_walk),
        (3400, pet.start_sleep),
        (3800, pet.wake),
        (4000, lambda: pet.toggle_follow(True)),
        (4300, lambda: pet.toggle_follow(False)),
        (4500, lambda: pet.set_scale(0.5)),
        (4700, lambda: pet.set_scale(DEFAULT_SCALE)),
        (4800, lambda: pet.flash_sprite("wave", 400)),
        (4900, lambda: pet.flash_sprite("eat", 400)),
        (5000, lambda: pet.flash_sprite("think", 400)),
        (5100, lambda: pet.flash_sprite("surprise", 400)),
        (5200, lambda: pet.set_idle_anim("float")),
        (5350, lambda: pet.set_idle_anim("sway")),
        (5500, lambda: pet.set_idle_anim("breathe")),
        (5650, pet.save_config),
    ]

    def finish():
        print("SELFTEST OK")
        app.quit()

    for ms, fn in steps:
        QTimer.singleShot(ms, fn)
    QTimer.singleShot(6000, finish)


def main():
    selftest = "--selftest" in sys.argv
    sys.excepthook = excepthook

    lock = QLockFile(os.path.join(tempfile.gettempdir(), APP_NAME + ".lock"))
    lock.setStaleLockTime(0)
    if not selftest and not lock.tryLock(100):
        print("WenTaoPet is already running.")
        return

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(APP_NAME)

    if getattr(sys, "frozen", False):
        try:
            import faulthandler
            faulthandler.enable(open(LOG_FILE, "a", encoding="utf-8"))
        except Exception:
            pass

    pet = Pet()
    pet.show()

    if selftest:
        run_selftest(app, pet)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
