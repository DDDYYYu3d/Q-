# 郭文韬桌宠（WenTaoPet）

> 一只从真人照片"长"出来的 Windows 桌面宠物：AI 生成 Q 版可爱写实立绘，透明贴纸式桌宠，带帧动画、对话气泡与粒子装饰。单文件 EXE，免安装，双击即用。


---

## 一、简介

**WenTaoPet** 是一个完全离线运行的个人桌宠项目。它以用户提供的真人照片为唯一形象来源，通过「AI 图生图 →  抠图 → 桌宠程序 → 单文件打包」的流水线制作而成：

- **形象**：Q 版可爱写实风格（约 2.5 头身），生成时以最清晰的正脸特写作面部锚点，逐项锁定五官特征，保证"脸还是本人"；
- **动画**：待机呼吸、走路、打盹三个核心动作由「图生视频 → 抽帧 → 逐帧抠图 → 脚底对齐」做成 **61 帧循环动画**，其余互动使用程序变换 + 粒子特效；
- **技术**：Python 3.13 + PySide6（Qt 6），PyInstaller 打包为单文件 EXE，内嵌全部运行库与素材，**目标电脑无需安装 Python**。

## 二、功能一览

| 类别 | 功能 |
| --- | --- |
| 基础 | 透明 · 无边框 · 置顶窗口；左键拖动（跑动姿势、自动转向）；滚轮缩放（约 98~1050px 高） |
| 互动 | 单击轮流触发：跳跃 / 压扁回弹 / 左右抖动（配惊讶表情与闪光粒子） |
| 菜单 | 陪我聊聊天 · 摸摸头 · 喂吃的 · 让他走路 · 让他睡觉 · 跟随鼠标 · 调整大小 · 待机动画（呼吸/漂浮/摇摆） · 窗口置顶 · 开机自启 · 退出 |
| 动画 | 帧动画：待机呼吸循环（61F）· 走路循环（61F）· 打盹循环（61F）；互动程序动画；粒子装饰（星星/爱心/音符/闪光/彩带） |
| 气泡 | 独立气泡窗口：指向角色的小尾巴、白底深字描边投影（深色桌面清晰可读） |
| 系统 | 托盘图标（显示/置顶/退出）· 单实例保护 · 位置大小与设置记忆（`%APPDATA%\WenTaoPet`）· 崩溃日志（`error.log`） |

## 三、运行要求

- 64 位 **Windows 10 / 11**（Python 3.13 不支持 Win7/8 与 32 位系统）
- 无需安装 Python、无需联网
- 首次启动延迟 1~3 秒（单文件自解压），属正常现象
- 杀毒软件若误报，添加信任即可

成品：`文韬桌宠.exe`（约 81 MB）。普通使用只需要这一个文件，详细操作见 `../使用说明.html` 或 `../使用说明.txt`。

## 四、目录结构

```
wentaopet/
├─ main.py                  # 桌宠主程序（Qt 窗口/动画/交互/托盘/菜单）
├─ process_images.py        # 素材流水线：AI 立绘 → rembg 抠图 → 裁剪缩放 → 图标/预览图
├─ process_particles.py     # 粒子贴图处理（白底泛洪/分割模型混合策略）
├─ process_video_frames.py  # 视频 → 抽帧 → 逐帧抠图 → 脚底对齐 → 帧序列
├─ preview_render.py        # 深色桌面效果预览图渲染
├─ make_q_compare*.py       # 各轮风格对比图脚本
├─ assets/
│  ├─ idle/happy/shy/...    # 10 张姿态立绘（透明 PNG，1200px 高）
│  ├─ anims/{idle,walk,sleep}/  # 帧动画（各 61 帧 + meta.json）
│  ├─ particles/            # 粒子贴图（5 种）
│  └─ pet.ico               # 程序图标
├─ gen/ gen_q*/             # AI 生成的各轮原图（写实版/Q版各轮）
├─ videos/                  # 图生视频原始 MP4
├─ assets_realistic_backup/ # 写实版素材备份（可随时切回）
└─ dist/WenTaoPet.exe       # 打包产物
```

## 五、从源码构建

```bash
# 1. 环境（Python 3.13）
python -m venv venv && venv\Scripts\python -m pip install ^
  -i https://mirrors.aliyun.com/pypi/simple/ ^
  PySide6-Essentials pyinstaller pillow numpy scipy rembg onnxruntime opencv-python-headless

# 2. 抠图素材（需 AI 生成原图放在 gen_q5/，u2net 模型放 %USERPROFILE%\.u2net\）
python process_images.py
python process_particles.py
python process_video_frames.py videos\<走路视频>.mp4 walk   # 其余动画同理

# 3. 打包单文件 EXE
python -m PyInstaller --noconfirm --onefile --windowed --name WenTaoPet ^
  --icon assets/pet.ico --add-data "assets;assets" main.py
```

> 注：抠图模型 u2net.onnx 国内可从 hf-mirror.com 镜像仓库下载，放入 `C:\Users\<用户>\.u2net\`。

## 六、技术要点

- **形象保真**：图生图采用「双参考锚点」——第一输入位为最清晰正脸特写，提示词逐项锁定五官（脸型/双眼皮眼型/眉形/鼻梁/唇形/下颌线/肤色肤质）并声明"严禁美化、严禁卡通化脸部"；身体仅做 Q 版比例化（约 2.5 头身）。
- **帧动画管线**：VideoGen 图生视频（白底立绘作首帧 → 形象一致）→ OpenCV 按 12fps 抽帧 → rembg 逐帧抠图 → 按每帧"脚底中心"统一对齐（消除播放抖动）→ 61 帧透明序列。
- **渲染**：所有贴图按 `devicePixelRatio` 生成物理像素图（高 DPI 屏不发虚）；窗口 mask 逐帧跟随精灵轮廓（透明区域不拦截鼠标）；帧动画播放时自动停用程序变换，避免双重动作叠加。
- **抠图策略**：人像走 rembg/u2net；纯白底图形走"边界泛洪"色键抠图（保留主体内部白色、不切尖角）；白色主体则仍走分割模型。

## 七、版本历史

| 版本 | 内容 |
| --- | --- |
| v1.0 | 写实版素材（AI 图生图 + rembg）+ 基础交互 + 单文件打包 |
| v1.1 | 素材高清化（1400px）+ 高 DPI 物理像素渲染 + 设置迁移 |
| v1.2 | 气泡重做（指向尾巴/深色桌面高对比）+ 粒子装饰 + 待机动画三选 + 开机自启 + 托盘 |
| v2.0 | 全素材重绘为 Q 版可爱写实（面部强保真）+ 完整着装 |
| v2.1 | 帧动画：图生视频抽帧接入待机/走路/睡觉三个循环动作 |

## 八、声明

本项目为个人爱好作品，仅限个人桌面使用，请勿商用或二次传播立绘素材。

## 📥 下载

前往 [Releases](https://github.com/DDDYYYu3d/Q-/releases) 页面，下载最新版 `WenTaoPet.zip`。
解压后，双击 `文韬桌宠.exe` 即可运行。

> 
> ⚠️ 提示：Windows Defender 可能会误报，这是 PyInstaller 打包程序常见现象，源码开源可自查。

---

*构建于 2026-09 · Python 3.13 · PySide6 6.11 · PyInstaller 6.22*
