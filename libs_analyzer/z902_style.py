# -*- coding: utf-8 -*-

# Copyright (C) 2026 Libs通用测试软件 作者
# SPDX-License-Identifier: GPL-3.0-or-later
#
# 本软件是自由软件：你可以依据 GNU 通用公共许可证（GPL v3 或更新版本）
# 的条款再分发和/或修改它。详见项目根目录 LICENSE 文件。
#
# 本软件按“现状”分发，不附带任何明示或默示担保；
# 详情请参阅 GNU GPL v3：<https://www.gnu.org/licenses/>。

"""
SciAps Z-902 深色工业主题（Profile Builder 风格）

全局 QSS 与配色常量：
  - 深色工业底（近黑/深灰） + 品牌蓝高亮（SciAps 蓝 #00A9E0）
  - 卡片化面板、圆角扁平按钮、深色表格
  - 供 run_app() 全局 setStyleSheet 使用，所有窗口/对话框自动继承
"""
from PyQt5.QtGui import QColor

# ---------------------------------------------------------------- 品牌色
BRAND = "#00A9E0"          # SciAps 品牌蓝（主高亮）
BRAND_DARK = "#0087B3"     # 深蓝（hover/按下）
BRAND_GLOW = "#2FC2F0"     # 亮蓝（激活/强调文字）
ACCENT = "#7DD3FC"         # 辅助浅蓝（选中文字）
OK = "#3FB950"             # 绿色（通过/确认/高置信）
WARN = "#D29922"           # 琥珀（注意/中置信）
DANGER = "#F85149"         # 红（低置信/异常）

BG = "#101418"             # 窗口背景
BG_PANEL = "#161B21"       # 面板/分组框
BG_CARD = "#1D242C"        # 卡片/输入框
BG_HOVER = "#232C36"       # hover
BG_SELECT = "#28333F"      # 选中
BORDER = "#2C3844"         # 边框
TEXT = "#E8EEF5"           # 主文字
TEXT_DIM = "#93A1B0"       # 次文字
TEXT_FAINT = "#5C6B7A"     # 弱文字
PLOT_BG = "#0C1015"        # 光谱图画布
PLOT_GRID = "#232C36"      # 网格

DARK_TEXT = "#0B1015"      # 品牌按钮上的深色文字


def qcolor(hex_str):
    """hex 字符串 -> QColor（供图内配色使用）。"""
    h = hex_str.lstrip("#")
    return QColor(*(int(h[i:i + 2], 16) for i in (0, 2, 4)))


# ---------------------------------------------------------------- 全局 QSS
Z902_QSS = f"""
* {{
    font-family: "Microsoft YaHei", "Segoe UI", "PingFang SC";
    font-size: 13px;
    color: {TEXT};
}}
QMainWindow, QDialog {{ background: {BG}; }}
QWidget {{ background: transparent; }}

/* ---------- 顶栏 / 标签页 ---------- */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    top: -1px;
    background: {BG};
}}
QTabBar::tab {{
    background: {BG_PANEL};
    color: {TEXT_DIM};
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 9px 22px;
    margin-right: 2px;
    font-size: 14px;
    font-weight: bold;
}}
QTabBar::tab:hover {{ background: {BG_HOVER}; color: {TEXT}; }}
QTabBar::tab:selected {{
    background: {BRAND_DARK};
    color: white;
    border-color: {BRAND};
}}

/* ---------- 分组框（卡片化） ---------- */
QGroupBox {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 12px;
    padding: 10px 8px 8px 8px;
    font-weight: bold;
    color: {TEXT};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: {BRAND_GLOW};
    background: {BG_PANEL};
    border-radius: 4px;
}}

/* ---------- 按钮 ---------- */
QPushButton {{
    background: {BG_CARD};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 14px;
    min-height: 22px;
}}
QPushButton:hover {{ background: {BG_HOVER}; border-color: {BRAND_DARK}; }}
QPushButton:pressed {{ background: {BRAND_DARK}; }}
QPushButton:disabled {{ color: {TEXT_FAINT}; background: {BG_PANEL}; }}

QPushButton#primary {{
    background: {BRAND};
    color: {DARK_TEXT};
    border: none;
    font-weight: bold;
}}
QPushButton#primary:hover {{ background: {BRAND_GLOW}; }}
QPushButton#primary:pressed {{ background: {BRAND_DARK}; }}

QPushButton#danger {{
    background: {BG_CARD};
    color: {DANGER};
    border: 1px solid {DANGER};
}}
QPushButton#danger:hover {{ background: {BG_HOVER}; }}

/* ---------- 输入控件 ---------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px 8px;
    selection-background-color: {BRAND_DARK};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QComboBox:focus, QDateEdit:focus {{
    border-color: {BRAND};
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid {TEXT_DIM};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    selection-background-color: {BRAND_DARK};
}}
QDateEdit::drop-down {{ border: none; width: 22px; }}

/* ---------- 复选框 ---------- */
QCheckBox {{ spacing: 6px; }}
QCheckBox::indicator {{
    width: 15px; height: 15px;
    border: 1px solid {BORDER};
    border-radius: 4px;
    background: {BG_CARD};
}}
QCheckBox::indicator:hover {{ border-color: {BRAND}; }}
QCheckBox::indicator:checked {{
    background: {BRAND};
    border-color: {BRAND};
    image: none;
}}

/* ---------- 表格 ---------- */
QTableWidget, QTableView {{
    background: {BG_PANEL};
    alternate-background-color: {BG_CARD};
    gridline-color: {BORDER};
    border: 1px solid {BORDER};
    border-radius: 6px;
    selection-background-color: {BG_SELECT};
    selection-color: {TEXT};
}}
QHeaderView::section {{
    background: {BG_CARD};
    color: {BRAND_GLOW};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 6px 8px;
    font-weight: bold;
}}
QTableCornerButton::section {{ background: {BG_CARD}; border: none; }}

/* ---------- 滚动条 ---------- */
QScrollBar:vertical {{
    background: {BG_PANEL}; width: 10px; margin: 0;
    border-radius: 5px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER}; border-radius: 5px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {BRAND_DARK}; }}
QScrollBar:horizontal {{ background: {BG_PANEL}; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{
    background: {BORDER}; border-radius: 5px; min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{ background: {BRAND_DARK}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}

/* ---------- 菜单 / 状态栏 / 工具提示 ---------- */
QMenuBar {{ background: {BG_PANEL}; border-bottom: 1px solid {BORDER}; }}
QMenuBar::item {{ padding: 6px 12px; border-radius: 4px; }}
QMenuBar::item:selected {{ background: {BRAND_DARK}; color: white; }}
QMenu {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 6px; }}
QMenu::item {{ padding: 6px 26px; border-radius: 4px; }}
QMenu::item:selected {{ background: {BRAND_DARK}; color: white; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 8px; }}

QStatusBar {{ background: {BG_PANEL}; color: {TEXT_DIM};
             border-top: 1px solid {BORDER}; }}
QStatusBar::item {{ border: none; }}

QToolTip {{
    background: {BG_CARD};
    color: {TEXT};
    border: 1px solid {BRAND};
    border-radius: 4px;
    padding: 4px 8px;
}}

/* ---------- 分裂器手柄 ---------- */
QSplitter::handle {{ background: {BORDER}; }}
QSplitter::handle:horizontal {{ width: 2px; }}
QSplitter::handle:vertical {{ height: 2px; }}

QLabel {{ background: transparent; }}
"""
