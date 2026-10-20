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
多次测量平均（Matrix 视图，参照 SciAps Z-902 Matrix View）。

将同一样品的多次测量光谱汇总为矩阵：
  行 = 检测到的元素，列 = 每次测量（文件），最后三列为
  AVG（平均强度）/ SD（标准偏差）/ RSD%（相对标准偏差）。
用于评估测量一致性、剔除异常测量后取平均。
"""
import os

import numpy as np

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QFileDialog, QHeaderView,
    QAbstractItemView, QMessageBox,
)

from .element_lines import ELEMENT_NAMES, match_lines
from .peak_detect import detect_peaks
from .data_io import load_spectrum


class MatrixDialog(QDialog):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        self.tests = []        # [{"label", "data": {el: intensity}}]
        self._build_ui()
        self.resize(980, 640)
        self.setWindowTitle("多次测量平均 · Matrix（参照 SciAps Z-902）")

    def _build_ui(self):
        root = QVBoxLayout(self)

        bar = QHBoxLayout()
        self.btn_add = QPushButton("添加测量文件…")
        self.btn_add.clicked.connect(self.add_files)
        self.btn_del = QPushButton("删除选中测试")
        self.btn_del.clicked.connect(self.delete_selected)
        self.btn_clear = QPushButton("清空")
        self.btn_clear.clicked.connect(self.clear_all)
        self.btn_export = QPushButton("导出矩阵 CSV…")
        self.btn_export.clicked.connect(self.export_csv)
        for b in (self.btn_add, self.btn_del, self.btn_clear, self.btn_export):
            bar.addWidget(b)
        bar.addStretch(1)
        root.addLayout(bar)

        self.lbl_info = QLabel("尚未添加测量。请添加同一样品的多次测量光谱文件。")
        self.lbl_info.setStyleSheet("color:#666;")
        root.addWidget(self.lbl_info)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["元素", "AVG", "SD"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        root.addWidget(self.table, 1)

    # ------------------------------------------------------------- 数据
    def add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择同一样品的多次测量光谱", "",
            "光谱文件 (*.txt *.csv *.asc *.dat);;所有文件 (*.*)")
        if not paths:
            return
        prom = self.main.sp_min_prom.value() / 100.0
        minw = self.main.sp_min_width.value()
        tol = self.main.sp_tol.value()
        added = 0
        for path in paths:
            try:
                spec = load_spectrum(path)
            except Exception as e:  # noqa: BLE001
                QMessageBox.warning(self, "打开失败", f"{os.path.basename(path)}: {e}")
                continue
            _, info = detect_peaks(spec.wl, spec.intensity,
                                   prominence_frac=prom, min_width_pts=minw)
            data = {}
            for p in info:
                cands = match_lines(p["wl"], tol)
                if cands:
                    el = cands[0]["element"]
                    if el not in data or p["intensity"] > data[el]:
                        data[el] = p["intensity"]
            self.tests.append({
                "label": os.path.splitext(os.path.basename(path))[0],
                "data": data,
            })
            added += 1
        self._refresh()
        self.lbl_info.setText(
            f"共 {len(self.tests)} 次测量；元素取各次最强匹配峰强度（a.u.）。"
            "RSD 超过 10% 标红提示。")

    def delete_selected(self):
        col = self.table.currentColumn()
        if col is None or col < 0:
            QMessageBox.information(self, "提示", "请先点击要删除的测试列。")
            return
        # 前 n 列是测试（AVG/SD/RSD 在最后三列）
        n_tests = len(self.tests)
        if 0 <= col < n_tests:
            self.tests.pop(col)
            self._refresh()

    def clear_all(self):
        self.tests = []
        self._refresh()

    # ------------------------------------------------------------- 渲染
    def _refresh(self):
        n = len(self.tests)
        if n == 0:
            self.table.setColumnCount(3)
            self.table.setHorizontalHeaderLabels(["元素", "AVG", "SD"])
            self.table.setRowCount(0)
            self.lbl_info.setText("尚未添加测量。请添加同一样品的多次测量光谱文件。")
            return

        # 元素并集（按出现顺序）
        elements = []
        seen = set()
        for t in self.tests:
            for el in t["data"]:
                if el not in seen:
                    seen.add(el)
                    elements.append(el)

        headers = [f"测试{i+1}\n{t['label']}" for i, t in enumerate(self.tests)]
        headers += ["AVG", "SD", "RSD%"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        self.table.setRowCount(len(elements))
        for r, el in enumerate(elements):
            self.table.setItem(r, 0, QTableWidgetItem(
                f"{el} ({ELEMENT_NAMES.get(el, el)})"))
            vals = []
            for t in self.tests:
                v = t["data"].get(el)
                if v is not None:
                    vals.append(v)
                    self.table.setItem(r, 1 + len(vals) - 1,
                                       QTableWidgetItem(f"{v:.1f}"))
                else:
                    self.table.setItem(r, 1 + len(vals), QTableWidgetItem("—"))
                    vals.append(np.nan)
            arr = np.array(vals, dtype=float)
            valid = arr[~np.isnan(arr)]
            if len(valid) >= 1:
                mean = float(valid.mean())
                self.table.setItem(r, n + 1, QTableWidgetItem(f"{mean:.1f}"))
                if len(valid) >= 2:
                    sd = float(valid.std(ddof=1))
                    rsd = sd / mean * 100.0 if mean else 0.0
                    self.table.setItem(r, n + 2, QTableWidgetItem(f"{sd:.1f}"))
                    item = QTableWidgetItem(f"{rsd:.1f}")
                    if rsd > 10.0:
                        item.setForeground(Qt.red)
                    self.table.setItem(r, n + 3, item)
                else:
                    self.table.setItem(r, n + 2, QTableWidgetItem("—"))
                    self.table.setItem(r, n + 3, QTableWidgetItem("—"))

    # ------------------------------------------------------------- 导出
    def export_csv(self):
        if not self.tests:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出矩阵", "matrix_avg.csv", "CSV 文件 (*.csv)")
        if not path:
            return
        n = len(self.tests)
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write("element," + ",".join(t["label"] for t in self.tests)
                    + ",AVG,SD,RSD%\n")
            for r in range(self.table.rowCount()):
                row = []
                for c in range(self.table.columnCount()):
                    it = self.table.item(r, c)
                    row.append(it.text() if it else "")
                f.write(",".join(row) + "\n")
        QMessageBox.information(self, "已导出", f"矩阵已保存：\n{path}")
