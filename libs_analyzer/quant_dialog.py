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
定量分析对话框：定标曲线法。
流程：选择目标谱线 -> 逐个加载标准样（已知浓度）-> 拟合定标曲线 ->
      加载未知样品光谱 -> 自动计算浓度（含标准误）。
"""
import os

import matplotlib
matplotlib.use("Qt5Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QLabel, QComboBox, QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QFileDialog, QInputDialog, QMessageBox, QHeaderView, QAbstractItemView,
    QSplitter,
)

from .element_lines import ELEMENT_NAMES
from .peak_detect import detect_peaks
from .data_io import load_spectrum
from .quant import CalibrationModel

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

_MANUAL = "手动输入波长…"


class QuantDialog(QDialog):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        self.model = CalibrationModel()
        self._build_ui()
        self.resize(920, 720)
        self.refresh_lines()

    # ------------------------------------------------------------- UI
    def _build_ui(self):
        self.setWindowTitle("定量分析 · 定标曲线法")

        root = QVBoxLayout(self)

        # 目标谱线
        gb_target = QGroupBox("目标谱线（用于定量）")
        f = QFormLayout(gb_target)
        row = QHBoxLayout()
        self.cmb_line = QComboBox()
        self.cmb_line.setMinimumWidth(260)
        self.btn_refresh = QPushButton("刷新列表")
        self.btn_refresh.clicked.connect(self.refresh_lines)
        row.addWidget(self.cmb_line, 1)
        row.addWidget(self.btn_refresh)
        self.ed_unit = QLineEdit("wt%")
        self.ed_unit.setMaximumWidth(90)
        f.addRow("元素谱线", row)
        f.addRow("浓度单位", self.ed_unit)
        root.addWidget(gb_target)

        split = QSplitter(Qt.Horizontal)

        # 左侧：标准样管理
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 4, 0)

        gb_std = QGroupBox("标准样品（已知浓度）")
        sv = QVBoxLayout(gb_std)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["来源", "浓度", "谱线强度"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        sv.addWidget(self.table)

        btns = QHBoxLayout()
        self.btn_add = QPushButton("添加标准样…")
        self.btn_del = QPushButton("删除选中")
        self.btn_clear = QPushButton("清空")
        self.btn_add.clicked.connect(self.add_standard)
        self.btn_del.clicked.connect(self.delete_selected)
        self.btn_clear.clicked.connect(self.clear_standards)
        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_del)
        btns.addWidget(self.btn_clear)
        btns.addStretch(1)
        sv.addLayout(btns)
        lv.addWidget(gb_std)

        self.lbl_fit = QLabel("尚未建立定标曲线（至少 2 个标准样）")
        self.lbl_fit.setWordWrap(True)
        self.lbl_fit.setStyleSheet("color:#444; padding:4px;")
        lv.addWidget(self.lbl_fit)

        # 未知样品
        gb_unk = QGroupBox("未知样品")
        uv = QVBoxLayout(gb_unk)
        self.btn_predict = QPushButton("加载未知样品并计算浓度…")
        self.btn_predict.clicked.connect(self.predict_unknown)
        self.btn_export = QPushButton("导出定标数据 CSV…")
        self.btn_export.clicked.connect(self.export_csv)
        hb = QHBoxLayout()
        hb.addWidget(self.btn_predict)
        hb.addWidget(self.btn_export)
        uv.addLayout(hb)
        self.lbl_result = QLabel("加载未知样品光谱后显示结果")
        self.lbl_result.setWordWrap(True)
        self.lbl_result.setStyleSheet(
            "background:#f4f8ff; border:1px solid #b8d0f0; padding:8px;")
        uv.addWidget(self.lbl_result)
        lv.addWidget(gb_unk)
        lv.addStretch(1)

        # 右侧：定标曲线图
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(4, 0, 0, 0)
        self.fig = plt.Figure(figsize=(5.6, 6.0), dpi=100)
        self.fig.patch.set_facecolor("white")
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvas(self.fig)
        rv.addWidget(self.canvas)

        split.addWidget(left)
        split.addWidget(right)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 4)
        root.addWidget(split, 1)

    # ------------------------------------------------------------- 目标谱线
    def refresh_lines(self):
        """从主窗口当前分析结果收集已匹配元素的峰，构建下拉列表。"""
        cur = self.cmb_line.currentData()
        self.cmb_line.clear()
        self.cmb_line.addItem(_MANUAL, None)
        seen = set()
        for m in self.main.matches:
            if m["element"] and m["line"]:
                key = (m["element"], round(m["line"], 3))
                if key not in seen:
                    seen.add(key)
                    name = ELEMENT_NAMES.get(m["element"], m["element"])
                    self.cmb_line.addItem(
                        f"{m['element']} ({name})  {m['line']:.3f} nm",
                        (m["element"], m["line"]))
        # 恢复选择
        if cur is not None:
            idx = self.cmb_line.findData(cur)
            if idx >= 0:
                self.cmb_line.setCurrentIndex(idx)

    def _current_target(self):
        """返回 (element, line_wl)。手动项时弹输入框。"""
        data = self.cmb_line.currentData()
        if data is not None:
            return data
        wl, ok = QInputDialog.getDouble(
            self, "目标谱线", "输入用于定量的谱线波长（nm）：",
            400.0, 0.0, 2000.0, 3)
        if not ok:
            return None
        return ("", wl)

    def _detect_and_pick(self, spec):
        """对光谱做峰检测，取最接近目标谱线的峰强度。返回 (intensity, peak_wl) 或 (None, None)。"""
        tol = self.main.sp_tol.value()
        prom = self.main.sp_min_prom.value() / 100.0
        minw = self.main.sp_min_width.value()
        target = self._current_target()
        if target is None:
            return None, None
        _, line_wl = target
        _, info = detect_peaks(spec.wl, spec.intensity,
                               prominence_frac=prom, min_width_pts=minw)
        if not info:
            return None, None
        best = min(info, key=lambda p: abs(p["wl"] - line_wl))
        tol_peak = max(2.0 * tol, 0.5)
        if abs(best["wl"] - line_wl) > tol_peak:
            return None, None
        return best["intensity"], best["wl"]

    # ------------------------------------------------------------- 标准样
    def add_standard(self):
        target = self._current_target()
        if target is None:
            return
        element, line_wl = target

        path, _ = QFileDialog.getOpenFileName(
            self, "选择标准样品光谱", "",
            "光谱文件 (*.txt *.csv *.asc *.dat);;所有文件 (*.*)")
        if not path:
            return
        try:
            spec = load_spectrum(path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "打开失败", str(e))
            return

        intensity, peak_wl = self._detect_and_pick(spec)
        if intensity is None:
            QMessageBox.warning(
                self, "未找到峰",
                f"在谱线 {line_wl:.3f} nm 附近（容差±{max(2.0 * self.main.sp_tol.value(), 0.5):.2f} nm）"
                "未检出峰。\n请确认目标谱线、检测参数或换一条谱线。")
            return

        unit = self.ed_unit.text().strip() or "wt%"
        label = os.path.splitext(os.path.basename(path))[0]
        conc, ok = QInputDialog.getDouble(
            self, "标准样浓度",
            f"“{label}” 的 {element or ('谱线%.3f nm' % line_wl)} 浓度（{unit}）：",
            1.0, 0.0, 1e9, 4)
        if not ok:
            return

        self.model.element = element or "未知"
        self.model.line_nm = line_wl
        self.model.unit = unit
        self.model.add_point(conc, intensity, label=label)
        self.main.save_calibration(self.model)
        self._update_table()
        self._plot_calibration()
        self.status_label(f"已添加标准样：{label}（{conc:g} {unit}，"
                          f"峰 {peak_wl:.3f} nm，强度 {intensity:.1f}）")

    def delete_selected(self):
        row = self.table.currentRow()
        if row >= 0:
            self.model.remove_point(row)
            self._update_table()
            self._plot_calibration()

    def clear_standards(self):
        if self.model.n_points == 0:
            return
        if QMessageBox.question(self, "确认", "清空所有标准样？") == QMessageBox.Yes:
            self.model.clear()
            self._update_table()
            self._plot_calibration()

    def _update_table(self):
        self.table.setRowCount(self.model.n_points)
        for i, p in enumerate(self.model.points):
            self.table.setItem(i, 0, QTableWidgetItem(p["label"]))
            self.table.setItem(i, 1, QTableWidgetItem(f"{p['concentration']:g}"))
            self.table.setItem(i, 2, QTableWidgetItem(f"{p['intensity']:.2f}"))

    def status_label(self, text):
        self.lbl_fit.setText(text)

    # ------------------------------------------------------------- 定标曲线
    def _plot_calibration(self):
        ax = self.ax
        ax.clear()
        pts = self.model.points
        if len(pts) >= 2:
            try:
                f = self.model.ensure_fit()
                cs = [p["concentration"] for p in pts]
                xs = np_linspace(min(cs), max(cs), 100)
                ys = f["slope"] * xs + f["intercept"]
                ax.plot(xs, ys, "-", color="#d62728", lw=1.6,
                        label=f"拟合 R²={f['r2']:.4f}")
            except ValueError:
                pass
        if pts:
            ax.plot([p["concentration"] for p in pts],
                    [p["intensity"] for p in pts],
                    "o", color="#1f6fb4", ms=7, label="标准样")
            ax.set_xlabel(f"浓度 ({self.model.unit})")
            ax.set_ylabel("谱线强度 (a.u.)")
            ax.set_title(f"定标曲线 · {self.model.element or '未知元素'} "
                         f"{self.model.line_nm:.3f} nm")
            ax.grid(True, alpha=0.3, lw=0.5)
            ax.legend(loc="best", fontsize=9)
        else:
            ax.set_title("定标曲线（添加标准样后显示）")
            ax.set_xlabel("浓度")
            ax.set_ylabel("谱线强度 (a.u.)")
            ax.grid(True, alpha=0.3, lw=0.5)
        self.fig.tight_layout()
        self.canvas.draw_idle()

        # 拟合信息
        if len(pts) >= 2:
            try:
                f = self.model.ensure_fit()
                self.lbl_fit.setText(
                    f"定标方程：I = {f['slope']:.4g}·C + {f['intercept']:.4g}\n"
                    f"R² = {f['r2']:.4f}，标准样数 n = {f['n']}，"
                    f"斜率标准误 = {f['se_slope']:.4g}")
            except ValueError:
                self.lbl_fit.setText("标准样不足，无法拟合（至少 2 个）")
        elif len(pts) == 1:
            self.lbl_fit.setText("已添加 1 个标准样，再添加 1 个即可拟合定标曲线")
        else:
            self.lbl_fit.setText("尚未建立定标曲线（至少 2 个标准样）")

    # ------------------------------------------------------------- 未知样
    def predict_unknown(self):
        if self.model.n_points < 2:
            QMessageBox.warning(self, "定标不足",
                                "请先添加至少 2 个标准样并建立定标曲线。")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "选择未知样品光谱", "",
            "光谱文件 (*.txt *.csv *.asc *.dat);;所有文件 (*.*)")
        if not path:
            return
        try:
            spec = load_spectrum(path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "打开失败", str(e))
            return

        intensity, peak_wl = self._detect_and_pick(spec)
        if intensity is None:
            QMessageBox.warning(
                self, "未找到峰",
                f"在谱线 {self.model.line_nm:.3f} nm 附近未检出峰，无法计算浓度。")
            return

        conc, se = self.model.predict(intensity)
        label = os.path.splitext(os.path.basename(path))[0]
        self.lbl_result.setText(
            f"<b>{label}</b><br>"
            f"目标谱线：{self.model.element or '未知元素'} "
            f"{self.model.line_nm:.3f} nm（实测峰 {peak_wl:.3f} nm）<br>"
            f"峰强度：{intensity:.2f} a.u.<br><br>"
            f"<b>浓度 C = {conc:.4g} {self.model.unit}</b><br>"
            f"标准误 SE = {se:.4g} {self.model.unit}"
            f"（约 95% 置信区间：{conc - 2 * se:.4g} ~ {conc + 2 * se:.4g} {self.model.unit}）")

    # ------------------------------------------------------------- 导出
    def export_csv(self):
        if self.model.n_points == 0:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出定标数据", "calibration.csv", "CSV 文件 (*.csv)")
        if not path:
            return
        rows = self.model.to_csv_rows()
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            for row in rows:
                f.write(",".join(str(v) for v in row) + "\n")
        QMessageBox.information(self, "已导出", f"定标数据已保存：\n{path}")


def np_linspace(a, b, n):
    import numpy as np
    return np.linspace(a, b, n)
