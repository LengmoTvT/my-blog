# -*- coding: utf-8 -*-
"""
冷漠博客 - 一键换横幅
双击运行 -> 选本地图片 -> 自动裁剪+替换 banner.jpg
原图自动备份到 source/img/banner_backup_时间戳.jpg
"""
import os
import sys
import shutil
import datetime
import tkinter as tk
from tkinter import filedialog, messagebox

BLOG_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(BLOG_DIR, "source", "img")
TARGET = os.path.join(IMG_DIR, "banner.jpg")
SUPPORTED = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")

# 目标横幅尺寸：宽 2560，高 900（16:5.6 不会太长，不用划半天）
TARGET_W = 2560
TARGET_H = 900


def resize_image(src, dst):
    """按目标尺寸中心裁剪缩放，使用 Pillow；没装就直接复制"""
    try:
        from PIL import Image
    except ImportError:
        shutil.copy2(src, dst)
        return False, "未安装 Pillow，已直接复制（未裁剪）"

    img = Image.open(src)
    # 转 RGB（兼容 png/webp 透明通道）
    if img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, (0, 0, 0))
        if img.mode == "P":
            img = img.convert("RGBA")
        bg.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    src_w, src_h = img.size
    # 目标比例
    ratio = TARGET_W / TARGET_H
    src_ratio = src_w / src_h

    # 先按比例裁剪再缩放
    if abs(src_ratio - ratio) < 0.01:
        cropped = img
    elif src_ratio > ratio:
        # 原图更宽 -> 左右裁
        new_w = int(src_h * ratio)
        left = (src_w - new_w) // 2
        cropped = img.crop((left, 0, left + new_w, src_h))
    else:
        # 原图更高 -> 上下裁
        new_h = int(src_w / ratio)
        top = (src_h - new_h) // 3  # 偏上，保留人物头部
        cropped = img.crop((0, top, src_w, top + new_h))

    resized = cropped.resize((TARGET_W, TARGET_H), Image.LANCZOS)
    resized.save(dst, "JPEG", quality=92, optimize=True)
    return True, f"已裁剪缩放为 {TARGET_W}x{TARGET_H}（不会太长）"


def main():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    path = filedialog.askopenfilename(
        title="选择要作为首页横幅的图片",
        filetypes=[("图片文件", " *.png *.jpg *.jpeg *.webp *.bmp *.gif"), ("所有文件", "*.*")],
    )
    if not path:
        return

    ext = os.path.splitext(path)[1].lower()
    if ext not in SUPPORTED:
        messagebox.showerror("错误", f"不支持的格式: {ext}\n支持: png/jpg/jpeg/webp/bmp/gif")
        return

    os.makedirs(IMG_DIR, exist_ok=True)

    # 备份原图（如果存在）
    if os.path.isfile(TARGET):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = os.path.join(IMG_DIR, f"banner_backup_{ts}.jpg")
        try:
            shutil.copy2(TARGET, backup)
            backup_msg = f"\n旧横幅已备份: banner_backup_{ts}.jpg"
        except Exception as e:
            backup_msg = f"\n（备份失败: {e}）"
    else:
        backup_msg = ""

    try:
        ok, info = resize_image(path, TARGET)
    except Exception as e:
        messagebox.showerror("错误", f"处理失败: {e}")
        return

    messagebox.showinfo(
        "完成 ✅",
        f"横幅已替换！\n"
        f"来源: {os.path.basename(path)}\n"
        f"结果: {info}{backup_msg}\n\n"
        f"接下来刷新 http://localhost:4000/ 就能看到\n"
        f"（推送到线上用编辑器的一键推送或 git 提交）",
    )


if __name__ == "__main__":
    main()
