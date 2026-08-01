#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================
 冷漠博客 - 可视化编辑器
 功能: 富文本编辑、图片粘贴、Mermaid流程图、
       文章管理、本地预览、一键推送GitHub
 依赖: PyQt5, markdown
============================================
"""

import sys
import os
import re
import shutil
import subprocess
import webbrowser
import datetime
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QTextEdit, QTextBrowser, QPushButton, QListWidget,
    QListWidgetItem, QSplitter, QDialog, QFormLayout, QDateTimeEdit,
    QFileDialog, QMessageBox, QToolBar, QAction, QStatusBar, QInputDialog,
    QMenu, QFrame, QScrollArea, QShortcut
)
from PyQt5.QtCore import Qt, QTimer, QDateTime, QThread, pyqtSignal, QSize
from PyQt5.QtGui import (
    QFont, QIcon, QTextCursor, QKeySequence, QPixmap, QImage,
    QTextDocument, QTextCharFormat, QColor
)

try:
    import markdown as md
except ImportError:
    md = None

# ============ 路径常量 ============
BLOG_DIR = Path(__file__).parent if hasattr(Path(__file__), 'parent') else Path(os.getcwd())
try:
    BLOG_DIR = Path("D:/myblog").resolve()
except Exception:
    pass
POSTS_DIR = BLOG_DIR / "source" / "_posts"


# ============ 工具函数 ============
def parse_front_matter(text):
    """解析文章的 front matter 和正文"""
    if text.startswith('---'):
        parts = text[3:].split('---', 1)
        if len(parts) >= 2:
            fm_text = parts[0].strip()
            body = parts[1].strip()
            fm = {}
            current_key = None
            current_list = None
            for line in fm_text.split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if line.startswith('- ') and current_key:
                    val = line[2:].strip().strip('"').strip("'")
                    if current_list is None:
                        current_list = []
                    current_list.append(val)
                    fm[current_key] = current_list
                elif ':' in line:
                    if current_list is not None:
                        current_list = None
                    key, val = line.split(':', 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if val:
                        fm[key] = val
                    else:
                        current_key = key
                        current_list = []
                        fm[key] = []
                else:
                    current_list = None
            return fm, body
    return {}, text


def build_front_matter(fm):
    """从字典构建 front matter 字符串"""
    lines = ['---']
    for key in ['title', 'date', 'categories', 'tags', 'cover', 'description']:
        if key not in fm:
            continue
        val = fm[key]
        if isinstance(val, list):
            lines.append(f'{key}:')
            for item in val:
                lines.append(f'  - {item}')
        elif val:
            lines.append(f'{key}: {val}')
    lines.append('---')
    return '\n'.join(lines)


def get_article_title(filepath):
    """从 md 文件读取标题"""
    try:
        text = Path(filepath).read_text(encoding='utf-8')
        fm, body = parse_front_matter(text)
        return fm.get('title', Path(filepath).stem)
    except Exception:
        return Path(filepath).stem


def get_article_date(filepath):
    """从 md 文件读取日期"""
    try:
        text = Path(filepath).read_text(encoding='utf-8')
        fm, body = parse_front_matter(text)
        return fm.get('date', '')
    except Exception:
        return ''


# ============ Markdown 编辑器 (支持图片粘贴) ============
class MarkdownEditor(QTextEdit):
    """自定义 QTextEdit，支持粘贴图片自动保存"""

    image_pasted = pyqtSignal(str)  # 信号: 图片已保存，参数为文件名

    def __init__(self, parent=None):
        super().__init__(parent)
        self.asset_folder = None  # 当前文章的资源文件夹

    def set_asset_folder(self, folder):
        self.asset_folder = Path(folder) if folder else None

    def canInsertFromMimeData(self, source):
        if source.hasImage():
            return True
        return super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        if source.hasImage() and self.asset_folder:
            self.asset_folder.mkdir(parents=True, exist_ok=True)
            image = QImage(source.imageData())
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"img_{timestamp}.png"
            filepath = self.asset_folder / filename
            image.save(str(filepath), 'PNG')
            markdown_img = f"\n\n![{filename}]({filename})\n\n"
            self.insertPlainText(markdown_img)
            self.image_pasted.emit(filename)
            return
        super().insertFromMimeData(source)


# ============ 新建文章对话框 ============
class NewPostDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新建文章")
        self.setMinimumWidth(450)
        self.setStyleSheet("""
            QDialog { background: #f5f5f5; }
            QLabel { font-size: 13px; }
            QLineEdit, QDateTimeEdit { padding: 6px; border: 1px solid #ccc; border-radius: 4px; }
            QPushButton { padding: 8px 20px; border-radius: 4px; }
        """)

        layout = QFormLayout(self)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("输入文章标题...")
        layout.addRow("标题:", self.title_input)

        self.date_input = QDateTimeEdit(QDateTime.currentDateTime())
        self.date_input.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        layout.addRow("日期:", self.date_input)

        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("多个标签用逗号分隔，如: CTF, 逆向, 笔记")
        layout.addRow("标签:", self.tags_input)

        self.cats_input = QLineEdit()
        self.cats_input.setPlaceholderText("多个分类用逗号分隔，如: 学习笔记, 折腾记录")
        layout.addRow("分类:", self.cats_input)

        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("一句话描述文章内容 (可选)")
        layout.addRow("描述:", self.desc_input)

        self.cover_path = ""
        cover_layout = QHBoxLayout()
        self.cover_label = QLabel("未选择封面图")
        self.cover_label.setStyleSheet("color: #999; font-size: 12px;")
        cover_btn = QPushButton("选择封面图")
        cover_btn.clicked.connect(self.choose_cover)
        cover_layout.addWidget(self.cover_label)
        cover_layout.addWidget(cover_btn)
        layout.addRow("封面:", cover_layout)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("创建")
        ok_btn.setStyleSheet("background: #49B1F5; color: white; font-weight: bold;")
        cancel_btn = QPushButton("取消")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

    def choose_cover(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择封面图", "", "图片文件 (*.png *.jpg *.jpeg *.webp *.gif)"
        )
        if path:
            self.cover_path = path
            self.cover_label.setText(Path(path).name)
            self.cover_label.setStyleSheet("color: #333; font-size: 12px;")

    def get_data(self):
        dt = self.date_input.dateTime().toPyDateTime()
        return {
            'title': self.title_input.text().strip(),
            'date': dt.strftime("%Y-%m-%d %H:%M:%S"),
            'tags': [t.strip() for t in self.tags_input.text().split(',') if t.strip()],
            'categories': [c.strip() for c in self.cats_input.text().split(',') if c.strip()],
            'cover': self.cover_path,
            'description': self.desc_input.text().strip(),
        }


# ============ 后台命令执行线程 ============
class CommandThread(QThread):
    """后台执行命令，避免阻塞UI"""
    finished_signal = pyqtSignal(str)

    def __init__(self, command, cwd=None):
        super().__init__()
        self.command = command
        self.cwd = cwd

    def run(self):
        try:
            result = subprocess.run(
                self.command, shell=True, cwd=self.cwd,
                capture_output=True, text=True, timeout=120
            )
            output = result.stdout + result.stderr
            self.finished_signal.emit(output)
        except subprocess.TimeoutExpired:
            self.finished_signal.emit("命令执行超时 (120秒)")
        except Exception as e:
            self.finished_signal.emit(f"执行出错: {e}")


# ============ 主窗口 ============
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("冷漠博客 - 可视化编辑器")
        self.setMinimumSize(1200, 750)
        self.current_file = None
        self.current_asset_folder = None
        self.preview_process = None
        self.git_thread = None
        self.is_modified = False

        self._setup_ui()
        self._load_posts()
        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet("""
            QMainWindow { background: #f0f2f5; }
            QToolBar { background: #ffffff; border: none; padding: 4px; spacing: 2px; }
            QToolBar QToolButton { padding: 6px 10px; border-radius: 4px; }
            QToolBar QToolButton:hover { background: #e8e8e8; }
            QListWidget { border: 1px solid #e0e0e0; border-radius: 6px; background: #fff; font-size: 13px; }
            QListWidget::item { padding: 8px 6px; border-bottom: 1px solid #f0f0f0; }
            QListWidget::item:selected { background: #e3f2fd; color: #1976d2; }
            QTextEdit, QTextBrowser { border: 1px solid #e0e0e0; border-radius: 6px; font-size: 14px; }
            QPushButton { padding: 6px 16px; border-radius: 4px; }
            QStatusBar { background: #fff; border-top: 1px solid #e0e0e0; }
            QLabel { font-size: 13px; }
        """)

    def _setup_ui(self):
        # === 中央 widget ===
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 4, 8, 8)
        main_layout.setSpacing(6)

        # === 顶部按钮栏 ===
        top_bar = QHBoxLayout()
        top_bar.setSpacing(6)

        btn_new = QPushButton("新建文章")
        btn_new.setStyleSheet("background: #49B1F5; color: white; font-weight: bold;")
        btn_new.clicked.connect(self.new_post)
        top_bar.addWidget(btn_new)

        btn_save = QPushButton("保存")
        btn_save.setStyleSheet("background: #00c4b6; color: white; font-weight: bold;")
        btn_save.clicked.connect(self.save_post)
        top_bar.addWidget(btn_save)

        btn_del = QPushButton("删除")
        btn_del.setStyleSheet("background: #ff6b6b; color: white;")
        btn_del.clicked.connect(self.delete_post)
        top_bar.addWidget(btn_del)

        top_bar.addStretch()

        btn_preview = QPushButton("本地预览")
        btn_preview.setStyleSheet("background: #6c5ce7; color: white; font-weight: bold;")
        btn_preview.clicked.connect(self.local_preview)
        top_bar.addWidget(btn_preview)

        btn_push = QPushButton("一键推送")
        btn_push.setStyleSheet("background: #fd79a8; color: white; font-weight: bold;")
        btn_push.clicked.connect(self.push_github)
        top_bar.addWidget(btn_push)

        main_layout.addLayout(top_bar)

        # === 三栏布局 ===
        splitter = QSplitter(Qt.Horizontal)

        # 左栏: 文章列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        left_label = QLabel("文章列表")
        left_label.setStyleSheet("font-weight: bold; font-size: 14px; padding: 4px;")
        left_layout.addWidget(left_label)
        self.post_list = QListWidget()
        self.post_list.currentItemChanged.connect(self.on_post_selected)
        left_layout.addWidget(self.post_list)
        splitter.addWidget(left_widget)

        # 中栏: 编辑器 + 工具栏
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(4)

        # Markdown 工具栏
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(16, 16))
        self._add_toolbar_action(toolbar, "H1", self.md_h1, "一级标题")
        self._add_toolbar_action(toolbar, "H2", self.md_h2, "二级标题")
        self._add_toolbar_action(toolbar, "H3", self.md_h3, "三级标题")
        toolbar.addSeparator()
        self._add_toolbar_action(toolbar, "B", self.md_bold, "加粗 (Ctrl+B)")
        self._add_toolbar_action(toolbar, "I", self.md_italic, "斜体 (Ctrl+I)")
        self._add_toolbar_action(toolbar, "S", self.md_strikethrough, "删除线")
        toolbar.addSeparator()
        self._add_toolbar_action(toolbar, "链接", self.md_link, "插入链接")
        self._add_toolbar_action(toolbar, "图片", self.md_image, "插入图片")
        self._add_toolbar_action(toolbar, "流程图", self.md_mermaid, "插入Mermaid流程图")
        toolbar.addSeparator()
        self._add_toolbar_action(toolbar, "代码", self.md_code, "行内代码")
        self._add_toolbar_action(toolbar, "代码块", self.md_codeblock, "代码块")
        self._add_toolbar_action(toolbar, "引用", self.md_quote, "引用")
        self._add_toolbar_action(toolbar, "列表", self.md_list, "无序列表")
        self._add_toolbar_action(toolbar, "有序", self.md_olist, "有序列表")
        self._add_toolbar_action(toolbar, "表格", self.md_table, "插入表格")
        self._add_toolbar_action(toolbar, "分割线", self.md_hr, "分割线")
        center_layout.addWidget(toolbar)

        self.editor = MarkdownEditor()
        self.editor.textChanged.connect(self.on_text_changed)
        center_layout.addWidget(self.editor)
        splitter.addWidget(center_widget)

        # 右栏: 预览
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)
        preview_label = QLabel("实时预览")
        preview_label.setStyleSheet("font-weight: bold; font-size: 14px; padding: 4px;")
        right_layout.addWidget(preview_label)
        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(True)
        right_layout.addWidget(self.preview)
        splitter.addWidget(right_widget)

        # 比例: 文章列表 1 : 编辑器 2 : 预览 2
        splitter.setSizes([200, 450, 450])
        main_layout.addWidget(splitter)

        # === 状态栏 ===
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("就绪 - 选择或新建文章开始写作")

        # === 预览定时器 (防抖) ===
        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.update_preview)
        self.preview_timer.setInterval(400)

        # === 快捷键 ===
        QShortcut(QKeySequence("Ctrl+S"), self, self.save_post)
        QShortcut(QKeySequence("Ctrl+B"), self, self.md_bold)
        QShortcut(QKeySequence("Ctrl+I"), self, self.md_italic)

    def _add_toolbar_action(self, toolbar, text, callback, tooltip):
        action = QAction(text, self)
        action.setToolTip(tooltip)
        action.triggered.connect(callback)
        toolbar.addAction(action)

    # ===== 文章列表 =====
    def _load_posts(self):
        self.post_list.clear()
        if not POSTS_DIR.exists():
            return
        posts = sorted(POSTS_DIR.glob("*.md"), key=lambda f: get_article_date(f), reverse=True)
        for p in posts:
            title = get_article_title(p)
            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, str(p))
            self.post_list.addItem(item)
        self.status.showMessage(f"已加载 {len(posts)} 篇文章")

    def on_post_selected(self, current, previous):
        if not current:
            return
        filepath = current.data(Qt.UserRole)
        if not filepath or not Path(filepath).exists():
            return
        self.current_file = filepath
        self.current_asset_folder = POSTS_DIR / Path(filepath).stem
        self.editor.set_asset_folder(self.current_asset_folder)
        text = Path(filepath).read_text(encoding='utf-8')
        self.editor.setPlainText(text)
        self.is_modified = False
        self.status.showMessage(f"已打开: {Path(filepath).name}")

    # ===== 新建文章 =====
    def new_post(self):
        dialog = NewPostDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
        data = dialog.get_data()
        if not data['title']:
            QMessageBox.warning(self, "提示", "请输入文章标题")
            return

        safe_title = re.sub(r'[<>:"/\\|?*]', '', data['title']).strip()
        md_path = POSTS_DIR / f"{safe_title}.md"
        if md_path.exists():
            QMessageBox.warning(self, "提示", f"文章已存在: {safe_title}")
            return

        asset_folder = POSTS_DIR / safe_title
        asset_folder.mkdir(parents=True, exist_ok=True)

        cover_line = ""
        if data['cover']:
            ext = Path(data['cover']).suffix
            cover_dst = asset_folder / f"cover{ext}"
            shutil.copy2(data['cover'], cover_dst)
            cover_line = f"cover: cover{ext}\n"

        tags_str = '\n'.join(f'  - {t}' for t in data['tags'])
        cats_str = '\n'.join(f'  - {c}' for c in data['categories'])

        content = f"""---
title: {data['title']}
date: {data['date']}
categories:
{cats_str if cats_str else '  - 未分类'}
tags:
{tags_str if tags_str else '  - 未标记'}
{cover_line}description: {data['description']}
---

## {data['title']}

在这里开始写作...
"""

        Path(md_path).write_text(content, encoding='utf-8')
        self.current_file = str(md_path)
        self.current_asset_folder = asset_folder
        self.editor.set_asset_folder(asset_folder)
        self.editor.setPlainText(content)
        self._load_posts()
        # 选中新文章
        for i in range(self.post_list.count()):
            if self.post_list.item(i).text() == data['title']:
                self.post_list.setCurrentRow(i)
                break
        self.status.showMessage(f"已创建: {safe_title}.md")

    # ===== 保存文章 =====
    def save_post(self):
        if not self.current_file:
            QMessageBox.information(self, "提示", "请先新建或打开一篇文章")
            return
        text = self.editor.toPlainText()
        Path(self.current_file).write_text(text, encoding='utf-8')
        self.is_modified = False
        self.status.showMessage(f"已保存: {Path(self.current_file).name}")
        self._load_posts()

    # ===== 删除文章 =====
    def delete_post(self):
        if not self.current_file:
            return
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定删除文章 \"{Path(self.current_file).stem}\" 及其图片文件夹吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            Path(self.current_file).unlink()
            if self.current_asset_folder and self.current_asset_folder.exists():
                shutil.rmtree(self.current_asset_folder)
            self.current_file = None
            self.current_asset_folder = None
            self.editor.set_asset_folder(None)
            self.editor.clear()
            self.preview.clear()
            self._load_posts()
            self.status.showMessage("文章已删除")

    # ===== 本地预览 =====
    def local_preview(self):
        self.save_post()
        if self.preview_process:
            try:
                self.preview_process.terminate()
            except Exception:
                pass
        self.preview_process = subprocess.Popen(
            f'npx hexo s -p 4000',
            cwd=str(BLOG_DIR),
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        QTimer.singleShot(3000, lambda: webbrowser.open("http://localhost:4000"))
        self.status.showMessage("本地服务器启动中... 3秒后打开浏览器")

    # ===== 一键推送 GitHub =====
    def push_github(self):
        self.save_post()
        reply = QMessageBox.question(
            self, "确认推送",
            "将提交所有改动并推送到GitHub远程仓库？\nVercel会自动重新构建网站。",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        self.status.showMessage("正在提交并推送...")
        cmd = f'cd /d "{BLOG_DIR}" && git add . && git commit -m "update: 文章更新 {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}" && git push origin master'
        self.git_thread = CommandThread(cmd)
        self.git_thread.finished_signal.connect(self.on_push_done)
        self.git_thread.start()

    def on_push_done(self, output):
        if 'error' in output.lower() or 'fatal' in output.lower():
            QMessageBox.warning(self, "推送结果", f"推送可能失败:\n\n{output[-500:]}")
        else:
            QMessageBox.information(self, "推送成功", f"已推送到GitHub!\nVercel将自动构建部署。\n\n{output[-300:]}")
        self.status.showMessage("推送完成")

    # ===== 编辑器文本变化 =====
    def on_text_changed(self):
        self.is_modified = True
        self.preview_timer.start()

    def update_preview(self):
        text = self.editor.toPlainText()
        if md:
            extensions = ['tables', 'fenced_code', 'nl2br']
            html = md.markdown(text, extensions=extensions)
            # 为 mermaid 代码块添加渲染标记
            html = re.sub(
                r'<pre><code class="language-mermaid">(.*?)</code></pre>',
                r'<div class="mermaid">\1</div>',
                html, flags=re.DOTALL
            )
            css = '<style>body{font-family:sans-serif;line-height:1.8;padding:12px;}img{max-width:100%;border-radius:8px;display:block;margin:10px auto;}table{border-collapse:collapse;width:100%;}td,th{border:1px solid #ddd;padding:8px;}th{background:#f5f5f5;}code{background:#f0f0f0;padding:2px 6px;border-radius:3px;}pre{background:#272822;color:#f8f8f2;padding:12px;border-radius:6px;overflow-x:auto;}pre code{background:none;}.mermaid{background:#f9f9f9;padding:16px;border-radius:8px;text-align:center;}</style>'
            self.preview.setHtml(css + html)
        else:
            self.preview.setPlainText(text)

    # ===== Markdown 工具栏方法 =====
    def _wrap_selection(self, before, after=""):
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText()
            cursor.insertText(f"{before}{text}{after}")
        else:
            cursor.insertText(f"{before}{after}")
            cursor.movePosition(QTextCursor.Left, QTextCursor.MoveMode, len(after))
            self.editor.setTextCursor(cursor)

    def _insert_at_line_start(self, prefix):
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        cursor.movePosition(QTextCursor.StartOfLine)
        cursor.insertText(prefix)
        cursor.endEditBlock()

    def md_h1(self):
        self._insert_at_line_start("# ")
    def md_h2(self):
        self._insert_at_line_start("## ")
    def md_h3(self):
        self._insert_at_line_start("### ")
    def md_bold(self):
        self._wrap_selection("**", "**")
    def md_italic(self):
        self._wrap_selection("*", "*")
    def md_strikethrough(self):
        self._wrap_selection("~~", "~~")
    def md_code(self):
        self._wrap_selection("`", "`")

    def md_link(self):
        cursor = self.editor.textCursor()
        text = cursor.selectedText() or "链接文字"
        cursor.insertText(f"[{text}](https://)")

    def md_image(self):
        if not self.current_asset_folder:
            QMessageBox.warning(self, "提示", "请先新建或打开一篇文章")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "", "图片文件 (*.png *.jpg *.jpeg *.webp *.gif *.bmp)"
        )
        if path:
            self.current_asset_folder.mkdir(parents=True, exist_ok=True)
            ext = Path(path).suffix
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"img_{timestamp}{ext}"
            dst = self.current_asset_folder / filename
            shutil.copy2(path, dst)
            self.editor.insertPlainText(f"\n\n![{filename}]({filename})\n\n")

    def md_mermaid(self):
        template = "\n\n```mermaid\ngraph TD\n    A[开始] --> B[步骤1]\n    B --> C[步骤2]\n    C --> D{判断}\n    D -->|是| E[结束]\n    D -->|否| B\n```\n\n"
        self.editor.insertPlainText(template)

    def md_codeblock(self):
        cursor = self.editor.textCursor()
        text = cursor.selectedText() or "代码"
        cursor.insertText(f"\n```\n{text}\n```\n")

    def md_quote(self):
        self._insert_at_line_start("> ")
    def md_list(self):
        self._insert_at_line_start("- ")
    def md_olist(self):
        self._insert_at_line_start("1. ")
    def md_hr(self):
        self.editor.insertPlainText("\n\n---\n\n")

    def md_table(self):
        table = "\n\n| 列1 | 列2 | 列3 |\n|------|------|------|\n| 内容 | 内容 | 内容 |\n| 内容 | 内容 | 内容 |\n\n"
        self.editor.insertPlainText(table)

    def closeEvent(self, event):
        if self.is_modified:
            reply = QMessageBox.question(
                self, "未保存",
                "有未保存的更改，是否保存？",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply == QMessageBox.Yes:
                self.save_post()
            elif reply == QMessageBox.Cancel:
                event.ignore()
                return
        if self.preview_process:
            try:
                self.preview_process.terminate()
            except Exception:
                pass
        event.accept()


# ============ 程序入口 ============
def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei UI", 10))
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
