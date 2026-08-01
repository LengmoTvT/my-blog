#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================
 冷漠博客 - 可视化管理后台
 功能: 文章CRUD、图片管理、富文本编辑、
       Mermaid流程图、本地预览、一键推送
 依赖: PyQt5, markdown
============================================
"""

import sys, os, re, shutil, subprocess, webbrowser, datetime
from pathlib import Path

from PyQt5.QtWidgets import (
    QAction, QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QTextEdit, QTextBrowser, QPushButton, QListWidget,
    QListWidgetItem, QSplitter, QDialog, QFormLayout, QDateTimeEdit,
    QFileDialog, QMessageBox, QToolBar, QStatusBar, QInputDialog,
    QMenu, QShortcut, QTabWidget
)
from PyQt5.QtCore import Qt, QTimer, QDateTime, QThread, pyqtSignal, QSize
from PyQt5.QtGui import (
    QFont, QIcon, QTextCursor, QKeySequence, QPixmap, QImage, QColor
)

try:
    import markdown as md
except ImportError:
    md = None

# ============ 路径 ============
BLOG_DIR = Path("D:/myblog").resolve()
POSTS_DIR = BLOG_DIR / "source" / "_posts"


# ============ 工具函数 ============
def parse_front_matter(text):
    if text.startswith('---'):
        parts = text[3:].split('---', 1)
        if len(parts) >= 2:
            fm_text, body = parts[0].strip(), parts[1].strip()
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
                    current_list = None
                    key, val = line.split(':', 1)
                    key, val = key.strip(), val.strip().strip('"').strip("'")
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
    try:
        text = Path(filepath).read_text(encoding='utf-8')
        fm, body = parse_front_matter(text)
        return fm.get('title', Path(filepath).stem)
    except Exception:
        return Path(filepath).stem


def get_article_date(filepath):
    try:
        text = Path(filepath).read_text(encoding='utf-8')
        fm, body = parse_front_matter(text)
        return fm.get('date', '')
    except Exception:
        return ''


def safe_filename(name):
    return re.sub(r'[<>:"/\\|?*]', '', name).strip()


# ============ Markdown编辑器(支持粘贴图片) ============
class MarkdownEditor(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.asset_folder = None
        self.setAcceptRichText(False)

    def set_asset_folder(self, folder):
        self.asset_folder = Path(folder) if folder else None

    def canInsertFromMimeData(self, source):
        return True if source.hasImage() else super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        if source.hasImage() and self.asset_folder:
            self.asset_folder.mkdir(parents=True, exist_ok=True)
            image = QImage(source.imageData())
            ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"img_{ts}.png"
            image.save(str(self.asset_folder / filename), 'PNG')
            self.insertPlainText(f"\n\n![{filename}]({filename})\n\n")
            return
        super().insertFromMimeData(source)


# ============ 新建文章对话框 ============
class NewPostDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新建文章")
        self.setMinimumWidth(480)
        self.cover_path = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QFormLayout(self)
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("输入文章标题...")
        layout.addRow("标题:", self.title_input)

        self.date_input = QDateTimeEdit(QDateTime.currentDateTime())
        self.date_input.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        layout.addRow("日期:", self.date_input)

        self.cats_input = QLineEdit()
        self.cats_input.setPlaceholderText("多个分类用逗号分隔")
        layout.addRow("分类:", self.cats_input)

        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("多个标签用逗号分隔")
        layout.addRow("标签:", self.tags_input)

        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("一句话描述 (可选)")
        layout.addRow("描述:", self.desc_input)

        cover_layout = QHBoxLayout()
        self.cover_label = QLabel("未选择")
        self.cover_label.setStyleSheet("color:#999;")
        cover_btn = QPushButton("选择封面图")
        cover_btn.clicked.connect(self.choose_cover)
        cover_layout.addWidget(self.cover_label)
        cover_layout.addWidget(cover_btn)
        layout.addRow("封面:", cover_layout)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("创建")
        ok_btn.setStyleSheet("background:#49B1F5;color:white;font-weight:bold;padding:8px 24px;")
        cancel_btn = QPushButton("取消")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

    def choose_cover(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择封面图", "", "图片 (*.png *.jpg *.jpeg *.webp *.gif)")
        if path:
            self.cover_path = path
            self.cover_label.setText(Path(path).name)
            self.cover_label.setStyleSheet("color:#333;")

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


# ============ 后台命令线程 ============
class CommandThread(QThread):
    finished_signal = pyqtSignal(str)
    def __init__(self, command, cwd=None):
        super().__init__()
        self.command = command
        self.cwd = cwd
    def run(self):
        try:
            result = subprocess.run(self.command, shell=True, cwd=self.cwd,
                                     capture_output=True, text=True, timeout=120)
            self.finished_signal.emit(result.stdout + result.stderr)
        except subprocess.TimeoutExpired:
            self.finished_signal.emit("超时(120秒)")
        except Exception as e:
            self.finished_signal.emit(f"出错: {e}")


# ============ 图片管理面板 ============
class ImagePanel(QWidget):
    """图片管理面板: 显示当前文章的图片，可插入/删除/设为封面"""
    insert_image = pyqtSignal(str)  # 信号: 插入图片到编辑器

    def __init__(self, parent=None):
        super().__init__(parent)
        self.asset_folder = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 标题 + 操作按钮
        top = QHBoxLayout()
        lbl = QLabel("图片管理")
        lbl.setStyleSheet("font-weight:bold;font-size:13px;")
        top.addWidget(lbl)
        top.addStretch()

        self.btn_add = QPushButton("添加图片")
        self.btn_add.setStyleSheet("background:#00c4b6;color:white;padding:4px 10px;")
        self.btn_add.clicked.connect(self.add_image)
        top.addWidget(self.btn_add)

        self.btn_del = QPushButton("删除选中")
        self.btn_del.setStyleSheet("background:#ff6b6b;color:white;padding:4px 10px;")
        self.btn_del.clicked.connect(self.del_image)
        top.addWidget(self.btn_del)

        self.btn_cover = QPushButton("设为封面")
        self.btn_cover.setStyleSheet("background:#6c5ce7;color:white;padding:4px 10px;")
        self.btn_cover.clicked.connect(self.set_cover)
        top.addWidget(self.btn_cover)

        layout.addLayout(top)

        # 图片列表
        self.img_list = QListWidget()
        self.img_list.setIconSize(QSize(80, 80))
        self.img_list.setSpacing(4)
        self.img_list.doubleClicked.connect(self.on_double_click)
        layout.addWidget(self.img_list)

        # 提示
        hint = QLabel("双击图片插入到编辑器\n右键更多操作")
        hint.setStyleSheet("color:#999;font-size:11px;")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

        self.img_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.img_list.customContextMenuRequested.connect(self.on_context_menu)

    def set_asset_folder(self, folder):
        self.asset_folder = Path(folder) if folder else None
        self.refresh()

    def refresh(self):
        self.img_list.clear()
        if not self.asset_folder or not self.asset_folder.exists():
            return
        for f in sorted(self.asset_folder.iterdir()):
            if f.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'):
                pixmap = QPixmap(str(f))
                if pixmap.isNull():
                    continue
                icon = QIcon(pixmap.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                item = QListWidgetItem(icon, f.name)
                item.setData(Qt.UserRole, str(f))
                self.img_list.addItem(item)

    def add_image(self):
        if not self.asset_folder:
            QMessageBox.warning(self, "提示", "请先新建或打开一篇文章")
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "选择图片", "", "图片 (*.png *.jpg *.jpeg *.webp *.gif *.bmp)")
        if not paths:
            return
        self.asset_folder.mkdir(parents=True, exist_ok=True)
        for path in paths:
            ext = Path(path).suffix
            ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"img_{ts}{ext}"
            shutil.copy2(path, self.asset_folder / filename)
        self.refresh()

    def del_image(self):
        item = self.img_list.currentItem()
        if not item:
            return
        path = item.data(Qt.UserRole)
        reply = QMessageBox.question(self, "确认", f"删除图片 {Path(path).name}？")
        if reply == QMessageBox.Yes:
            Path(path).unlink()
            self.refresh()

    def set_cover(self):
        item = self.img_list.currentItem()
        if not item:
            return
        path = item.data(Qt.UserRole)
        filename = Path(path).name
        # 发信号让主窗口更新 cover
        self.insert_image.emit(f"__COVER__:{filename}")

    def on_double_click(self, index):
        item = self.img_list.item(index.row())
        if item:
            filename = Path(item.data(Qt.UserRole)).name
            self.insert_image.emit(f"__INSERT__:{filename}")

    def on_context_menu(self, pos):
        item = self.img_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        act_insert = menu.addAction("插入到编辑器")
        menu.addSeparator()
        act_cover = menu.addAction("设为封面")
        menu.addSeparator()
        act_delete = menu.addAction("删除图片")
        action = menu.exec_(self.img_list.mapToGlobal(pos))
        if action == act_insert:
            filename = Path(item.data(Qt.UserRole)).name
            self.insert_image.emit(f"__INSERT__:{filename}")
        elif action == act_cover:
            filename = Path(item.data(Qt.UserRole)).name
            self.insert_image.emit(f"__COVER__:{filename}")
        elif action == act_delete:
            path = item.data(Qt.UserRole)
            reply = QMessageBox.question(self, "确认", f"删除图片 {Path(path).name}？")
            if reply == QMessageBox.Yes:
                Path(path).unlink()
                self.refresh()


# ============ 主窗口 ============
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("冷漠博客 - 管理后台")
        self.setMinimumSize(1300, 800)
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
            QToolBar { background: #fff; border: none; padding: 4px; spacing: 2px; }
            QToolBar QToolButton { padding: 6px 10px; border-radius: 4px; }
            QToolBar QToolButton:hover { background: #e8e8e8; }
            QListWidget { border: 1px solid #e0e0e0; border-radius: 6px; background: #fff; font-size: 13px; }
            QListWidget::item { padding: 8px 6px; border-bottom: 1px solid #f0f0f0; }
            QListWidget::item:selected { background: #e3f2fd; color: #1976d2; }
            QTextEdit, QTextBrowser { border: 1px solid #e0e0e0; border-radius: 6px; font-size: 14px; }
            QPushButton { padding: 6px 14px; border-radius: 4px; }
            QStatusBar { background: #fff; border-top: 1px solid #e0e0e0; }
            QLabel { font-size: 13px; }
            QTabWidget::pane { border: 1px solid #e0e0e0; border-radius: 6px; }
            QTabBar::tab { padding: 6px 16px; border-radius: 4px 4px 0 0; }
            QTabBar::tab:selected { background: #49B1F5; color: white; }
        """)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 4, 8, 8)
        main_layout.setSpacing(6)

        # === 顶部操作栏 ===
        top = QHBoxLayout()
        top.setSpacing(6)

        btn_new = QPushButton("＋ 新建文章")
        btn_new.setStyleSheet("background:#49B1F5;color:white;font-weight:bold;")
        btn_new.clicked.connect(self.new_post)
        top.addWidget(btn_new)

        btn_save = QPushButton("💾 保存")
        btn_save.setStyleSheet("background:#00c4b6;color:white;font-weight:bold;")
        btn_save.clicked.connect(self.save_post)
        top.addWidget(btn_save)

        btn_del = QPushButton("🗑 删除文章")
        btn_del.setStyleSheet("background:#ff6b6b;color:white;font-weight:bold;")
        btn_del.clicked.connect(self.delete_post)
        top.addWidget(btn_del)

        top.addStretch()

        btn_preview = QPushButton("🌐 本地预览")
        btn_preview.setStyleSheet("background:#6c5ce7;color:white;font-weight:bold;")
        btn_preview.clicked.connect(self.local_preview)
        top.addWidget(btn_preview)

        btn_push = QPushButton("🚀 一键推送")
        btn_push.setStyleSheet("background:#fd79a8;color:white;font-weight:bold;")
        btn_push.clicked.connect(self.push_github)
        top.addWidget(btn_push)

        main_layout.addLayout(top)

        # === 四栏布局: 文章列表 | 编辑器 | 预览 | 图片管理 ===
        splitter = QSplitter(Qt.Horizontal)

        # --- 左: 文章列表 ---
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(4)
        lbl = QLabel("📝 文章列表")
        lbl.setStyleSheet("font-weight:bold;font-size:14px;padding:4px;")
        left_lay.addWidget(lbl)
        self.post_list = QListWidget()
        self.post_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.post_list.customContextMenuRequested.connect(self.post_context_menu)
        self.post_list.currentItemChanged.connect(self.on_post_selected)
        left_lay.addWidget(self.post_list)
        # 统计
        self.count_label = QLabel("共 0 篇")
        self.count_label.setStyleSheet("color:#999;font-size:12px;padding:2px;")
        left_lay.addWidget(self.count_label)
        splitter.addWidget(left)

        # --- 中: 编辑器 + 工具栏 ---
        center = QWidget()
        center_lay = QVBoxLayout(center)
        center_lay.setContentsMargins(0, 0, 0, 0)
        center_lay.setSpacing(4)

        toolbar = QToolBar()
        toolbar.setIconSize(QSize(16, 16))
        self._add_tb(toolbar, "H1", self.md_h1, "一级标题")
        self._add_tb(toolbar, "H2", self.md_h2, "二级标题")
        self._add_tb(toolbar, "H3", self.md_h3, "三级标题")
        toolbar.addSeparator()
        self._add_tb(toolbar, "B", self.md_bold, "加粗")
        self._add_tb(toolbar, "I", self.md_italic, "斜体")
        self._add_tb(toolbar, "S", self.md_strike, "删除线")
        toolbar.addSeparator()
        self._add_tb(toolbar, "链接", self.md_link, "插入链接")
        self._add_tb(toolbar, "图片", self.md_image, "插入图片")
        self._add_tb(toolbar, "流程图", self.md_mermaid, "Mermaid")
        toolbar.addSeparator()
        self._add_tb(toolbar, "代码", self.md_code, "行内代码")
        self._add_tb(toolbar, "代码块", self.md_codeblock, "代码块")
        self._add_tb(toolbar, "引用", self.md_quote, "引用")
        self._add_tb(toolbar, "列表", self.md_list, "无序列表")
        self._add_tb(toolbar, "有序", self.md_olist, "有序列表")
        self._add_tb(toolbar, "表格", self.md_table, "表格")
        self._add_tb(toolbar, "分割线", self.md_hr, "分割线")
        center_lay.addWidget(toolbar)

        self.editor = MarkdownEditor()
        self.editor.textChanged.connect(self.on_text_changed)
        center_lay.addWidget(self.editor)
        splitter.addWidget(center)

        # --- 右: Tab (预览 + 图片管理) ---
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(4)
        tabs = QTabWidget()
        # 预览 Tab
        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(True)
        tabs.addTab(self.preview, "👁 实时预览")
        # 图片管理 Tab
        self.image_panel = ImagePanel()
        self.image_panel.insert_image.connect(self.on_image_action)
        tabs.addTab(self.image_panel, "🖼 图片管理")
        right_lay.addWidget(tabs)
        splitter.addWidget(right)

        splitter.setSizes([220, 430, 430])
        main_layout.addWidget(splitter)

        # === 状态栏 ===
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("就绪")

        # === 预览定时器 ===
        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.update_preview)
        self.preview_timer.setInterval(400)

        # === 快捷键 ===
        QShortcut(QKeySequence("Ctrl+S"), self, self.save_post)
        QShortcut(QKeySequence("Ctrl+B"), self, self.md_bold)
        QShortcut(QKeySequence("Ctrl+I"), self, self.md_italic)
        QShortcut(QKeySequence("Ctrl+N"), self, self.new_post)
        QShortcut(QKeySequence("Delete"), self, self.delete_post)

    def _add_tb(self, toolbar, text, callback, tooltip):
        act = QAction(text, self)
        act.setToolTip(tooltip)
        act.triggered.connect(callback)
        toolbar.addAction(act)

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
        self.count_label.setText(f"共 {len(posts)} 篇")
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
        self.image_panel.set_asset_folder(self.current_asset_folder)
        text = Path(filepath).read_text(encoding='utf-8')
        self.editor.setPlainText(text)
        self.is_modified = False
        self.status.showMessage(f"已打开: {Path(filepath).name}")
        self.update_preview()

    def post_context_menu(self, pos):
        item = self.post_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        act_open = menu.addAction("打开编辑")
        menu.addSeparator()
        act_del = menu.addAction("删除文章")
        action = menu.exec_(self.post_list.mapToGlobal(pos))
        if action == act_open:
            self.post_list.setCurrentItem(item)
        elif action == act_del:
            self.post_list.setCurrentItem(item)
            self.delete_post()

    # ===== 新建文章 =====
    def new_post(self):
        dialog = NewPostDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
        data = dialog.get_data()
        if not data['title']:
            QMessageBox.warning(self, "提示", "请输入标题")
            return
        safe_title = safe_filename(data['title'])
        md_path = POSTS_DIR / f"{safe_title}.md"
        if md_path.exists():
            QMessageBox.warning(self, "提示", f"已存在: {safe_title}")
            return
        asset_folder = POSTS_DIR / safe_title
        asset_folder.mkdir(parents=True, exist_ok=True)

        cover_line = ""
        if data['cover']:
            ext = Path(data['cover']).suffix
            shutil.copy2(data['cover'], asset_folder / f"cover{ext}")
            cover_line = f"cover: cover{ext}\n"

        tags_str = '\n'.join(f'  - {t}' for t in data['tags']) or '  - 未标记'
        cats_str = '\n'.join(f'  - {c}' for c in data['categories']) or '  - 未分类'

        content = f"""---
title: {data['title']}
date: {data['date']}
categories:
{cats_str}
tags:
{tags_str}
{cover_line}description: {data['description']}
---

## {data['title']}

在这里开始写作...
"""
        Path(md_path).write_text(content, encoding='utf-8')
        self.current_file = str(md_path)
        self.current_asset_folder = asset_folder
        self.editor.set_asset_folder(asset_folder)
        self.image_panel.set_asset_folder(asset_folder)
        self.editor.setPlainText(content)
        self._load_posts()
        for i in range(self.post_list.count()):
            if self.post_list.item(i).text() == data['title']:
                self.post_list.setCurrentRow(i)
                break
        self.status.showMessage(f"已创建: {safe_title}.md")

    # ===== 保存 =====
    def save_post(self):
        if not self.current_file:
            QMessageBox.information(self, "提示", "请先新建或打开文章")
            return
        text = self.editor.toPlainText()
        Path(self.current_file).write_text(text, encoding='utf-8')
        self.is_modified = False
        self.status.showMessage(f"已保存: {Path(self.current_file).name}")
        self._load_posts()

    # ===== 删除 =====
    def delete_post(self):
        if not self.current_file:
            return
        title = Path(self.current_file).stem
        reply = QMessageBox.question(self, "确认删除",
            f"删除文章 \"{title}\" 及其图片文件夹？\n此操作不可恢复！",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            Path(self.current_file).unlink()
            if self.current_asset_folder and self.current_asset_folder.exists():
                shutil.rmtree(self.current_asset_folder)
            self.current_file = None
            self.current_asset_folder = None
            self.editor.set_asset_folder(None)
            self.image_panel.set_asset_folder(None)
            self.editor.clear()
            self.preview.clear()
            self._load_posts()
            self.status.showMessage("已删除")

    # ===== 本地预览 =====
    def local_preview(self):
        self.save_post()
        if self.preview_process:
            try: self.preview_process.terminate()
            except: pass
        self.preview_process = subprocess.Popen(
            'npx hexo s -p 4000', cwd=str(BLOG_DIR), shell=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        QTimer.singleShot(3000, lambda: webbrowser.open("http://localhost:4000"))
        self.status.showMessage("本地服务器启动中... 3秒后打开浏览器")

    # ===== 一键推送 =====
    def push_github(self):
        self.save_post()
        reply = QMessageBox.question(self, "确认推送",
            "提交所有改动并推送到GitHub？\nVercel会自动构建。", QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        self.status.showMessage("正在提交并推送...")
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        cmd = f'cd /d "{BLOG_DIR}" && git add . && git commit -m "update: 文章更新 {ts}" && git push origin master'
        self.git_thread = CommandThread(cmd)
        self.git_thread.finished_signal.connect(self.on_push_done)
        self.git_thread.start()

    def on_push_done(self, output):
        if 'error' in output.lower() or 'fatal' in output.lower():
            QMessageBox.warning(self, "推送结果", f"可能失败:\n\n{output[-500:]}")
        else:
            QMessageBox.information(self, "推送成功", "已推送到GitHub!\nVercel将自动构建。")
        self.status.showMessage("推送完成")

    # ===== 图片操作回调 =====
    def on_image_action(self, action):
        if action.startswith("__INSERT__:"):
            filename = action.split("__INSERT__:")[1]
            self.editor.insertPlainText(f"\n\n![{filename}]({filename})\n\n")
        elif action.startswith("__COVER__:"):
            filename = action.split("__COVER__:")[1]
            # 更新 front matter 的 cover 字段
            text = self.editor.toPlainText()
            if re.search(r'^cover:', text, re.MULTILINE):
                text = re.sub(r'^cover:.*$', f'cover: {filename}', text, flags=re.MULTILINE)
            else:
                # 在 description 前插入
                text = re.sub(r'^(description:)', f'cover: {filename}\n$1', text, flags=re.MULTILINE)
            self.editor.setPlainText(text)
            self.status.showMessage(f"已设置封面: {filename}")

    # ===== 文本变化 =====
    def on_text_changed(self):
        self.is_modified = True
        self.preview_timer.start()

    def update_preview(self):
        text = self.editor.toPlainText()
        if md:
            html = md.markdown(text, extensions=['tables', 'fenced_code', 'nl2br'])
            html = re.sub(r'<pre><code class="language-mermaid">(.*?)</code></pre>',
                          r'<div class="mermaid">\1</div>', html, flags=re.DOTALL)
            css = '<style>body{font-family:sans-serif;line-height:1.8;padding:12px;}img{max-width:100%;border-radius:8px;display:block;margin:10px auto;}table{border-collapse:collapse;width:100%;}td,th{border:1px solid #ddd;padding:8px;}th{background:#f5f5f5;}code{background:#f0f0f0;padding:2px 6px;border-radius:3px;}pre{background:#272822;color:#f8f8f2;padding:12px;border-radius:6px;overflow-x:auto;}pre code{background:none;}.mermaid{background:#f9f9f9;padding:16px;border-radius:8px;text-align:center;}</style>'
            self.preview.setHtml(css + html)
        else:
            self.preview.setPlainText(text)

    # ===== Markdown 工具栏 =====
    def _wrap(self, before, after=""):
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            cursor.insertText(f"{before}{cursor.selectedText()}{after}")
        else:
            cursor.insertText(f"{before}{after}")
            cursor.movePosition(QTextCursor.Left, QTextCursor.MoveMode, len(after))
            self.editor.setTextCursor(cursor)

    def _line_start(self, prefix):
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        cursor.movePosition(QTextCursor.StartOfLine)
        cursor.insertText(prefix)
        cursor.endEditBlock()

    def md_h1(self): self._line_start("# ")
    def md_h2(self): self._line_start("## ")
    def md_h3(self): self._line_start("### ")
    def md_bold(self): self._wrap("**", "**")
    def md_italic(self): self._wrap("*", "*")
    def md_strike(self): self._wrap("~~", "~~")
    def md_code(self): self._wrap("`", "`")

    def md_link(self):
        cursor = self.editor.textCursor()
        text = cursor.selectedText() or "链接文字"
        cursor.insertText(f"[{text}](https://)")

    def md_image(self):
        if not self.current_asset_folder:
            QMessageBox.warning(self, "提示", "请先新建或打开文章")
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "选择图片", "", "图片 (*.png *.jpg *.jpeg *.webp *.gif *.bmp)")
        if not paths:
            return
        self.current_asset_folder.mkdir(parents=True, exist_ok=True)
        for path in paths:
            ext = Path(path).suffix
            ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"img_{ts}{ext}"
            shutil.copy2(path, self.current_asset_folder / filename)
            self.editor.insertPlainText(f"\n\n![{filename}]({filename})\n\n")
        self.image_panel.refresh()

    def md_mermaid(self):
        self.editor.insertPlainText('\n\n```mermaid\ngraph TD\n    A[开始] --> B[步骤1]\n    B --> C[步骤2]\n    C --> D{判断}\n    D -->|是| E[结束]\n    D -->|否| B\n```\n\n')

    def md_codeblock(self):
        cursor = self.editor.textCursor()
        text = cursor.selectedText() or "代码"
        cursor.insertText(f"\n```\n{text}\n```\n")

    def md_quote(self): self._line_start("> ")
    def md_list(self): self._line_start("- ")
    def md_olist(self): self._line_start("1. ")
    def md_hr(self): self.editor.insertPlainText("\n\n---\n\n")
    def md_table(self):
        self.editor.insertPlainText("\n\n| 列1 | 列2 | 列3 |\n|------|------|------|\n| 内容 | 内容 | 内容 |\n\n")

    def closeEvent(self, event):
        if self.is_modified:
            reply = QMessageBox.question(self, "未保存", "有未保存的更改，是否保存？",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if reply == QMessageBox.Yes: self.save_post()
            elif reply == QMessageBox.Cancel: event.ignore(); return
        if self.preview_process:
            try: self.preview_process.terminate()
            except: pass
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei UI", 10))
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
