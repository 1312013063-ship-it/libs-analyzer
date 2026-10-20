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
AI 分析图谱对话框（Z-902 深色风格）

展示一次 LIBS 测试的智能分析：
  - 左：元素-材料关系图谱 + 置信度条形（networkx + matplotlib）
  - 右：材料推断卡片、元素明细表、AI 解读文本
  - 支持导出图谱 PNG
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox,
    QHeaderView, QAbstractItemView, QScrollArea, QWidget,
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from .ai_insight import analyze_insight, build_insight_figure, _LEVEL_COLORS
from .z902_style import BRAND, BG_PANEL, TEXT, TEXT_DIM, TEXT_FAINT

_ELEM_HEADERS = ["元素", "中文", "谱线数", "偏差(nm)", "置信度", "等级", "浓度(wt%)"]


class AIGraphDialog(QDialog):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        self.insight = None
        self._fig = None
        self.setWindowTitle("AI 分析图谱 · LIBS 智能解读")
        self.resize(1280, 760)
        self._build_ui()
        self._run()

    # ------------------------------------------------------------- UI
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # 标题条
        head = QHBoxLayout()
        lbl_title = QLabel("AI 分析图谱")
        lbl_title.setStyleSheet(
            f"color:{BRAND}; font-size:20px; font-weight:bold;")
        self.lbl_sub = QLabel("")
        self.lbl_sub.setStyleSheet(f"color:{TEXT_DIM};")
        head.addWidget(lbl_title)
        head.addWidget(self.lbl_sub)
        head.addStretch(1)
        root.addLayout(head)

        split = QSplitter(Qt.Horizontal)

        # ---- 左：图谱
        self.split = split
        self.lbl_fig = QLabel("正在分析…")
        self.lbl_fig.setAlignment(Qt.AlignCenter)
        self.lbl_fig.setStyleSheet(
            f"background:#0C1015; color:{TEXT_DIM}; border-radius:8px;")
        split.addWidget(self.lbl_fig)

        # ---- 右：解读面板（滚动）
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(8, 0, 0, 0)

        # 材料推断卡片
        self.lbl_mat = QLabel("")
        self.lbl_mat.setWordWrap(True)
        self.lbl_mat.setStyleSheet(
            f"background:{BG_PANEL}; color:{TEXT}; border-radius:8px;"
            "padding:10px; font-size:14px; font-weight:bold;"
            f"border:1px solid {BRAND};")
        rv.addWidget(self.lbl_mat)

        self.table = QTableWidget(0, len(_ELEM_HEADERS))
        self.table.setHorizontalHeaderLabels(_ELEM_HEADERS)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        rv.addWidget(self.table, 3)

        scr = QScrollArea()
        scr.setWidgetResizable(True)
        scr.setFrameShape(QScrollArea.NoFrame)
        self.lbl_summary = QLabel("")
        self.lbl_summary.setWordWrap(True)
        self.lbl_summary.setTextInteractionFlags(
            Qt.TextSelectableByMouse)
        self.lbl_summary.setStyleSheet(
            f"background:{BG_PANEL}; color:{TEXT}; border-radius:8px;"
            "padding:10px; font-size:13px;")
        scr.setWidget(self.lbl_summary)
        rv.addWidget(scr, 2)

        split.addWidget(right)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        root.addWidget(split, 1)

        # 底部
        bar = QHBoxLayout()
        self.btn_reanalyze = QPushButton("用当前光谱重新分析")
        self.btn_reanalyze.setObjectName("primary")
        self.btn_reanalyze.clicked.connect(self._run)
        self.btn_png = QPushButton("导出图谱 PNG…")
        self.btn_png.clicked.connect(self.export_png)
        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(self.accept)
        bar.addWidget(self.btn_reanalyze)
        bar.addWidget(self.btn_png)
        bar.addStretch(1)
        bar.addWidget(self.btn_close)
        root.addLayout(bar)

    # ------------------------------------------------------------- 分析
    def _run(self):
        m = self.main
        if m.spectrum is None:
            QMessageBox.information(self, "提示", "请先生成演示光谱或打开光谱文件。")
            self.lbl_mat.setText("无数据")
            return
        self.insight = analyze_insight(
            m.matches, m.spectrum,
            calibrations=m.calibrations, base=m.base_metal)
        self.lbl_sub.setText(
            f"光谱：{self.insight.spectrum_name}"
            f"{' ｜ 基体：' + m.base_metal if m.base_metal else ''}"
            f" ｜ 元素 {len(self.insight.elements)} 个 / "
            f"匹配峰 {len(m.matches)} 个")
        self._show()

    def _show(self):
        ins = self.insight

        # 材料卡片
        if ins.materials:
            top = ins.materials[0]
            txt = f"◆ 材料推断：{top.name_cn}（{top.name}） 置信度 {top.confidence * 100:.0f}%"
            if len(ins.materials) > 1:
                other = " ｜ ".join(
                    f"{mm.name_cn} {mm.confidence * 100:.0f}%"
                    for mm in ins.materials[1:])
                txt += f"\n其他候选：{other}"
            txt += f"\n依据组合：{top.elements[0]} + " + " + ".join(top.elements[1:]) \
                   if len(top.elements) > 1 else ""
        else:
            txt = "◆ 材料推断：未找到常见材料组合（可能为非常规合金或混合样品）"
        self.lbl_mat.setText(txt)

        # 元素表
        self.table.setRowCount(len(ins.elements))
        for i, e in enumerate(ins.elements):
            vals = [e.element, e.name, str(e.n_lines),
                    f"{e.best_delta:.3f}",
                    f"{e.confidence * 100:.0f}%",
                    e.level,
                    (f"{e.conc:.4g} ± {e.se:.4g}" if e.conc is not None else "")]
            for j, v in enumerate(vals):
                item = QTableWidgetItem(v)
                if j == 5:
                    item.setForeground(_qcolor(_LEVEL_COLORS.get(e.level, "#93A1B0")))
                self.table.setItem(i, j, item)

        # 解读
        self.lbl_summary.setText(ins.summary)

        # 图谱
        self._fig = build_insight_figure(ins)
        self._replace_figure()

    def _replace_figure(self):
        if self._fig is None:
            return
        canvas = FigureCanvas(self._fig)
        canvas.setStyleSheet("background:#101418; border-radius:8px;")
        self.split.replaceWidget(0, canvas)
        self.lbl_fig.deleteLater()
        # 强制分配左右比例，避免替换后左图区塌缩为 0 宽
        self.split.setSizes([700, 540])
        self.split.setStretchFactor(0, 3)
        self.split.setStretchFactor(1, 2)
        self._fig.canvas.draw()
        self._canvas = canvas

    # ------------------------------------------------------------- 导出
    def export_png(self):
        if self._fig is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 AI 分析图谱", "ai_insight.png", "PNG 图片 (*.png)")
        if not path:
            return
        self._fig.savefig(path, dpi=200, bbox_inches="tight")
        QMessageBox.information(self, "已导出", f"图谱已保存：\n{path}")


def _qcolor(hex_str):
    from PyQt5.QtGui import QColor
    h = hex_str.lstrip("#")
    return QColor(*(int(h[i:i + 2], 16) for i in (0, 2, 4)))
