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
AI 脉冲质量甄别对话框（Z-902 深色风格）

核心流程（对应"数据脉冲如实保留 + AI 自动识别无效 + 提示改进方向 + 用户可查看/标记"）：
  1. 全部原始脉冲谱图在列表中逐一展示（如实保留，不删除）
  2. AI 自动评估每个脉冲：健康度 0-100 + 判定（有效/疑似/无效）+ 原因 + 改进方向
  3. 点击脉冲行查看该脉冲原始谱图（与参考中位谱对比）
  4. 用户可对任意脉冲手动标记"无效/有效"（覆盖/修正 AI 判定）
  5. 「重算平均谱」排除无效脉冲后生成平均谱，供后续定性/定量分析
"""
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox,
    QHeaderView, QAbstractItemView, QScrollArea, QWidget,
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt

from .pulse_quality import analyze_pulses, average_valid_pulses, pulse_summary
from .data_io import save_pulses_csv
from .z902_style import (BRAND, BG_PANEL, BG_CARD, PLOT_BG, PLOT_GRID,
                         TEXT, TEXT_DIM, TEXT_FAINT, OK, WARN, DANGER)

_HEADERS = ["脉冲", "健康度", "AI 判定", "原因 / 改进方向", "用户标记"]
_LEVEL_COLOR = {"有效": OK, "疑似": WARN, "无效": DANGER}


class PulseQualityDialog(QDialog):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        self.pulse_data = main.pulse_data
        self.verdicts = analyze_pulses(self.pulse_data)
        self._fig = None
        self._ax = None
        self._canvas = None
        self._current = 0
        self.setWindowTitle("AI 脉冲质量甄别 · 原始谱图保留")
        self.resize(1320, 780)
        self._build_ui()
        self._refresh_table()
        self._show_pulse(0)
        self._update_summary()

    # ------------------------------------------------------------- UI
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        head = QHBoxLayout()
        title = QLabel("AI 脉冲质量甄别")
        title.setStyleSheet(
            f"color:{BRAND}; font-size:19px; font-weight:bold;")
        self.lbl_sub = QLabel("")
        self.lbl_sub.setStyleSheet(f"color:{TEXT_DIM};")
        head.addWidget(title)
        head.addWidget(self.lbl_sub)
        head.addStretch(1)
        self.lbl_keep = QLabel("✔ 全部原始谱图已保留")
        self.lbl_keep.setStyleSheet(
            f"color:{OK}; font-weight:bold; background:transparent;")
        head.addWidget(self.lbl_keep)
        root.addLayout(head)

        split = QSplitter(Qt.Horizontal)
        self.split = split

        # ---- 左：脉冲列表
        self.table = QTableWidget(0, len(_HEADERS))
        self.table.setHorizontalHeaderLabels(_HEADERS)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_select)
        split.addWidget(self.table)

        # ---- 右：谱图 + AI 结论
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(8, 0, 0, 0)

        self.fig = plt.Figure(figsize=(7.4, 4.6), dpi=100)
        self.fig.patch.set_facecolor(BG_PANEL)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor(PLOT_BG)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setStyleSheet(f"background:{BG_PANEL};")
        rv.addWidget(self.canvas, 3)

        # AI 结论面板
        self.lbl_ai = QLabel("")
        self.lbl_ai.setWordWrap(True)
        self.lbl_ai.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_ai.setStyleSheet(
            f"background:{BG_CARD}; color:{TEXT}; border-radius:8px;"
            "padding:10px; font-size:13px;")
        rv.addWidget(self.lbl_ai, 2)

        split.addWidget(right)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 3)
        root.addWidget(split, 1)

        # ---- 底部操作
        bar = QHBoxLayout()
        self.btn_mark_invalid = QPushButton("标记选中为无效")
        self.btn_mark_invalid.setObjectName("danger")
        self.btn_mark_invalid.clicked.connect(
            lambda: self._mark("invalid"))
        self.btn_mark_valid = QPushButton("标记选中为有效")
        self.btn_mark_valid.setObjectName("primary")
        self.btn_mark_valid.clicked.connect(
            lambda: self._mark("valid"))
        self.btn_clear_mark = QPushButton("清除用户标记")
        self.btn_clear_mark.clicked.connect(
            lambda: self._mark(None))
        self.btn_export = QPushButton("导出全部脉冲 CSV…")
        self.btn_export.clicked.connect(self.export_csv)
        bar.addWidget(self.btn_mark_invalid)
        bar.addWidget(self.btn_mark_valid)
        bar.addWidget(self.btn_clear_mark)
        bar.addWidget(self.btn_export)
        bar.addStretch(1)
        self.btn_avg = QPushButton("重算平均谱（排除无效）")
        self.btn_avg.setObjectName("primary")
        self.btn_avg.clicked.connect(self.reaverage)
        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(self.accept)
        bar.addWidget(self.btn_avg)
        bar.addWidget(self.btn_close)
        root.addLayout(bar)

    # ------------------------------------------------------------- 数据
    def _refresh_table(self):
        pd = self.pulse_data
        self.table.setRowCount(pd.n_pulses)
        for i, v in enumerate(self.verdicts):
            self.table.setItem(i, 0, QTableWidgetItem(v.name))
            it = QTableWidgetItem(f"{v.score:.0f}")
            it.setForeground(_qcolor(_LEVEL_COLOR[v.level]))
            self.table.setItem(i, 1, it)
            self.table.setItem(i, 2, QTableWidgetItem(v.level))
            reason = v.issues[0][0] if v.issues else "—"
            self.table.setItem(i, 3, QTableWidgetItem(reason))
            mark = {None: "", "invalid": "用户·无效",
                    "valid": "用户·有效"}[v.user_mark]
            self.table.setItem(i, 4, QTableWidgetItem(mark))
        self.table.selectRow(min(self._current, pd.n_pulses - 1))

    def _on_select(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        self._current = rows[0].row()
        self._show_pulse(self._current)

    def _show_pulse(self, i):
        v = self.verdicts[i]
        y = self.pulse_data.intensities[i]
        ref = np_median(self.pulse_data)
        color = _LEVEL_COLOR[v.level]
        ax = self.ax
        ax.clear()
        ax.plot(self.pulse_data.wl, y, lw=0.9, color=color,
                label=f"{v.name}（{v.level}，{v.score:.0f} 分）")
        ax.plot(self.pulse_data.wl, ref, lw=0.7, color=BRAND,
                ls="--", alpha=0.7, label="参考中位谱")
        ax.set_facecolor(PLOT_BG)
        ax.set_xlabel("波长 (nm)", color=TEXT_DIM)
        ax.set_ylabel("强度 (a.u.)", color=TEXT_DIM)
        ax.set_title(f"{v.name} 原始谱图（如实保留）",
                     color=TEXT, fontsize=12, fontweight="bold")
        ax.grid(True, alpha=0.35, lw=0.5, color=PLOT_GRID)
        ax.tick_params(colors=TEXT_DIM, labelsize=9)
        for s in ax.spines.values():
            s.set_color(PLOT_GRID)
        ax.legend(fontsize=9, facecolor=BG_CARD,
                  edgecolor=PLOT_GRID, labelcolor=TEXT)
        self.fig.tight_layout()
        self.canvas.draw_idle()

        # AI 结论
        lines = [f"◆ {v.name}：健康度 {v.score:.0f}/100 · "
                 f"AI 判定「{v.level}」"
                 + ("（用户已标记，以用户为准）"
                    if v.user_mark else "")]
        if v.issues:
            for j, (reason, advice) in enumerate(v.issues, 1):
                lines.append(f"{j}. {reason}")
                lines.append(f"   改进方向：{advice}")
        else:
            lines.append("该脉冲质量良好，无异常。")
        self.lbl_ai.setText("\n".join(lines))

    def _update_summary(self):
        pd = self.pulse_data
        n_valid = sum(1 for v in self.verdicts if v.effective_valid)
        n_ai_invalid = sum(1 for v in self.verdicts
                           if v.level == "无效")
        n_user = sum(1 for v in self.verdicts if v.user_mark)
        self.lbl_sub.setText(
            f"光谱：{getattr(self.main.spectrum, 'name', '—')} ｜ "
            f"共 {pd.n_pulses} 个脉冲（原始全部保留）｜ "
            f"AI 判定无效 {n_ai_invalid} 个｜ 重算将使用 {n_valid} 个有效"
            + (f"｜ 用户标记 {n_user} 个" if n_user else ""))

    # ------------------------------------------------------------- 用户标记
    def _mark(self, mark):
        v = self.verdicts[self._current]
        v.user_mark = mark
        self._refresh_table()
        self._show_pulse(self._current)
        self._update_summary()

    # ------------------------------------------------------------- 导出/重算
    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "导出全部原始脉冲谱图", "pulses_raw.csv",
            "CSV 文件 (*.csv)")
        if not path:
            return
        save_pulses_csv(path, self.pulse_data)
        QMessageBox.information(
            self, "已导出",
            f"全部 {self.pulse_data.n_pulses} 个脉冲原始谱图已保存：\n{path}")

    def reaverage(self):
        avg, n_valid = average_valid_pulses(self.pulse_data, self.verdicts)
        self.main.spectrum = avg
        self.main._data_file = None
        self.main.run_analysis()
        QMessageBox.information(
            self, "重算完成",
            f"已用 {n_valid} 个有效脉冲生成平均谱并重新分析。\n"
            f"全部 {self.pulse_data.n_pulses} 个原始脉冲仍完整保留，"
            "可随时在此查看。")
        self._update_summary()


def np_median(pd):
    """脉冲数据中位数参考谱（局部导入避免顶层依赖）。"""
    import numpy as np
    return np.median(pd.intensities, axis=0)


def _qcolor(hex_str):
    h = hex_str.lstrip("#")
    return QColor(*(int(h[i:i + 2], 16) for i in (0, 2, 4)))
