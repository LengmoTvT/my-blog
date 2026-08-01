#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================
 冷漠博客 - 图片切换工具
 用法: python switch_image.py
 交互式选择要替换的图片类型，输入图片路径，
 自动复制图片到 source/img/ 并更新主题配置。
============================================
"""

import os
import re
import glob
import shutil
import sys

# 路径
BLOG_DIR = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(BLOG_DIR, "_config.butterfly.yml")
IMG_DIR = os.path.join(BLOG_DIR, "source", "img")

# 可替换的图片项
# (序号, 显示名称, 配置类型, 标准文件名前缀)
# 配置类型: top = 顶级字段, avatar = avatar.img, cover = cover.default_cover 列表
OPTIONS = {
    "1": ("头像 (avatar)          - 侧边栏作者头像", "avatar", "avatar"),
    "2": ("网站图标 (favicon)      - 浏览器标签页图标", "top", "favicon"),
    "3": ("首页横幅 (index_img)    - 首页顶部大图", "top", "index"),
    "4": ("归档页横幅 (archive_img)", "top", "archive"),
    "5": ("网站背景 (background)   - 全站背景图", "top", "background"),
    "6": ("页脚背景 (footer_img)   - 页脚背景图", "top", "footer"),
    "7": ("文章默认封面 (default_cover)", "cover", "cover"),
}


def read_cfg():
    with open(CFG_PATH, "r", encoding="utf-8") as f:
        return f.read()


def write_cfg(content):
    with open(CFG_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def copy_image(src_path, std_name):
    """把图片复制到 source/img/ 下，返回 /img/xxx.ext 路径"""
    if not os.path.isfile(src_path):
        print("错误: 找不到文件 " + src_path)
        return None
    ext = os.path.splitext(src_path)[1].lower()  # .png .jpg ...
    if ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".bmp"):
        print("错误: 不支持的图片格式 " + ext + "，支持 png/jpg/jpeg/webp/gif/ico/bmp")
        return None
    os.makedirs(IMG_DIR, exist_ok=True)
    # 删除旧的同名前缀图片
    for old in glob.glob(os.path.join(IMG_DIR, std_name + ".*")):
        os.remove(old)
    dst = os.path.join(IMG_DIR, std_name + ext)
    shutil.copy2(src_path, dst)
    web_path = "/img/" + std_name + ext
    print("已复制: " + src_path + " -> " + dst)
    return web_path


def update_top_field(content, field, value):
    """更新顶级字段 如 favicon: /img/xxx.png"""
    # 匹配 字段名: 任意值 (行首开头)
    pattern = re.compile(r"^(" + re.escape(field) + r"):\s*.*$", re.MULTILINE)
    if pattern.search(content):
        content = pattern.sub(r"\1: " + value, content)
    else:
        print("警告: 在配置中未找到字段 " + field)
    return content


def update_avatar(content, value):
    """更新 avatar.img 字段"""
    pattern = re.compile(r"^(avatar:\s*\n\s+img:\s*).*$", re.MULTILINE)
    if pattern.search(content):
        content = pattern.sub(r"\1" + value, content)
    else:
        print("警告: 在配置中未找到 avatar.img 字段")
    return content


def update_cover(content, value):
    """更新 default_cover 列表，替换或新增第一项"""
    # 匹配 default_cover: 下的第一个 # - xxx 注释行 或 - xxx 实行
    pattern = re.compile(
        r"(default_cover:\s*\n)(\s*#?\s*-\s*.*\n)?", re.MULTILINE
    )
    if pattern.search(content):
        content = pattern.sub(
            r"\1    - " + value + "\n", content
        )
    else:
        print("警告: 在配置中未找到 default_cover 字段")
    return content


def clear_field(content, field):
    """清空某顶级字段"""
    return update_top_field(content, field, "")


def main():
    print("=" * 50)
    print("  冷漠博客 - 图片切换工具")
    print("=" * 50)
    print("当前可替换的图片项:")
    for k in sorted(OPTIONS.keys()):
        print("  [" + k + "] " + OPTIONS[k][0])
    print("  [0] 退出")
    print()

    choice = input("请选择 (0-7): ").strip()
    if choice == "0" or choice == "":
        print("已退出。")
        return
    if choice not in OPTIONS:
        print("无效选择。")
        return

    display, cfg_type, std_name = OPTIONS[choice]
    print()
    print("已选择: " + display)
    print("请输入图片文件的完整路径")
    print("(例如: C:\\Users\\Administrator\\Pictures\\avatar.png)")
    print("(输入 c 清除该项的图片，恢复默认)")
    src = input("路径: ").strip().strip('"').strip("'")

    if src.lower() == "c":
        content = read_cfg()
        if cfg_type == "avatar":
            content = update_avatar(content, "/img/butterfly-icon.png")
        elif cfg_type == "cover":
            content = update_cover(content, "")
        elif cfg_type == "top":
            field_map = {
                "favicon": "favicon",
                "index": "index_img",
                "archive": "archive_img",
                "background": "background",
                "footer": "footer_img",
            }
            field = field_map.get(std_name, std_name)
            content = update_top_field(content, field, "")
        write_cfg(content)
        print("已清除 " + display + " 的图片设置。")
        return

    web_path = copy_image(src, std_name)
    if not web_path:
        return

    content = read_cfg()
    if cfg_type == "avatar":
        content = update_avatar(content, web_path)
    elif cfg_type == "cover":
        content = update_cover(content, web_path)
    elif cfg_type == "top":
        field_map = {
            "favicon": "favicon",
            "index": "index_img",
            "archive": "archive_img",
            "background": "background",
            "footer": "footer_img",
        }
        field = field_map.get(std_name, std_name)
        content = update_top_field(content, field, web_path)
    write_cfg(content)

    print()
    print("完成! 图片已更新: " + web_path)
    print("配置文件已修改: _config.butterfly.yml")
    print()
    print("下一步: 运行 hexo clean && hexo g && hexo s 预览效果")


if __name__ == "__main__":
    main()
