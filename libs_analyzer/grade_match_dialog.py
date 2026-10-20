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
合金鉴定对话框（参照 SciAps Z-902 Results 界面）：
- Chemistry：元素浓度表（浓度 ± 标准误 / 牌号规格 / ND 判定）
- Grade Match：牌号匹配分数（100 分制），Top 匹配牌号大字显示
- Grade Compare：选中牌号时，各元素实测值 vs 规格范围对比图
浓度来源：优先从已保存的定标曲线自动反推；未定标元素可手动输入。
"""
import os

import matplotlib
matplotlib.use("Qt5Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QLabel, QComboBox, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMessageBox, QFileDialog, QSplitter,
    QFrame,
)

from .element_lines import ELEMENT_NAMES
from .grade_library import match_grades, BASES

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

_COLORS = {"good": "#1e8e3e", "warn": "#f9a825", "bad": "#d93025", "nd": "#9e9e9e"}


class GradeMatchDialog(QDialog):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        self.chem = {}            # 元素 -> {"conc", "se", "source"}
        self.grade_results = []
        self._build_ui()
        self.resize(1080, 760)
        self.refresh_base()

    # ------------------------------------------------------------- UI
    def _build_ui(self):
        self.setWindowTitle("合金鉴定 · Grade Match（参照 SciAps Z-902）")

        root = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel("基体过滤："))
        self.cmb_base = QComboBox()
        self.cmb_base.addItem("全部基体", None)
        for k, v in BASES.items():
            self.cmb_base.addItem(v, k)
        self.cmb_base.currentIndexChanged.connect(self.run_match)
        top.addWidget(self.cmb_base)
        top.addStretch(1)
        self.btn_import = QPushButton("从定标导入浓度")
        self.btn_import.clicked.connect(self.import_from_calibration)
        top.addWidget(self.btn_import)
        self.btn_match = QPushButton("匹配牌号")
        self.btn_match.clicked.connect(self.run_match)
        self.btn_match.setStyleSheet("font-weight:bold; padding:4px 14px;")
        top.addWidget(self.btn_match)
        root.addLayout(top)

        split = QSplitter(Qt.Horizontal)

        # 左：Chemistry 表
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 4, 0)

        gb_chem = QGroupBox("Chemistry · 元素浓度（双击浓度单元格可编辑）")
        cv = QVBoxLayout(gb_chem)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["元素", "浓度 (wt%)", "± 标准误", "牌号规格", "状态"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.table.setAlternatingRowColors(True)
        self.table.itemChanged.connect(self._on_cell_edited)
        cv.addWidget(self.table)

        self.lbl_hint = QLabel(
            "提示：先为元素建立定标曲线（定量分析），点“从定标导入浓度”；"
            "未定标元素可直接双击浓度单元格手动输入。")
        self.lbl_hint.setWordWrap(True)
        self.lbl_hint.setStyleSheet("color:#666;")
        cv.addWidget(self.lbl_hint)
        lv.addWidget(gb_chem)

        # 左下：匹配结果
        gb_grades = QGroupBox("Grade Match · 匹配结果")
        gv = QVBoxLayout(gb_grades)
        self.lbl_top = QLabel("—")
        self.lbl_top.setStyleSheet(
            "background:#0f1720; color:#e8eef5; border-radius:8px;"
            "padding:14px; font-size:22px; font-weight:bold;")
        self.lbl_top.setMinimumHeight(64)
        gv.addWidget(self.lbl_top)

        self.grade_table = QTableWidget(0, 4)
        self.grade_table.setHorizontalHeaderLabels(
            ["排名", "牌号", "分数", "基体"])
        self.grade_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.grade_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.grade_table.setAlternatingRowColors(True)
        self.grade_table.itemSelectionChanged.connect(self._on_grade_selected)
        gv.addWidget(self.grade_table)
        lv.addWidget(gb_grades, 1)

        # 右：规格对比图
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(4, 0, 0, 0)
        self.fig = plt.Figure(figsize=(5.4, 7.0), dpi=100)
        self.fig.patch.set_facecolor("white")
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvas(self.fig)
        rv.addWidget(self.canvas)
        self.btn_export = QPushButton("导出鉴定结果 CSV…")
        self.btn_export.clicked.connect(self.export_csv)
        rv.addWidget(self.btn_export)

        split.addWidget(left)
        split.addWidget(right)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        root.addWidget(split, 1)

    def refresh_base(self):
        base = self.main.base_metal
        if base:
            idx = self.cmb_base.findData(base)
            if idx >= 0:
                self.cmb_base.setCurrentIndex(idx)

    # ------------------------------------------------------------- 浓度数据
    def _nd(self, d):
        """ND 判定：浓度 < n×σ（n 在 Settings 配置，默认 3）判未检出。"""
        sigma = self.main.nd_sigma
        return (d["se"] > 0 and d["conc"] < sigma * d["se"]) or d["conc"] <= 0

    def _row_element(self, row):
        item = self.table.item(row, 0)
        return item.text() if item else ""

    def import_from_calibration(self):
        """对每个已保存定标的元素，用当前光谱峰强度反推浓度。"""
        if not self.main.calibrations:
            QMessageBox.information(
                self, "暂无定标",
                "尚未保存任何定标曲线。\n请先在「定量分析」中为标准样品建立定标曲线，"
                "或手动在表格中输入浓度。")
            return
        n_ok = 0
        for el, model in self.main.calibrations.items():
            peak = self._peak_for_element(el)
            if peak is None:
                self.chem[el] = {"conc": 0.0, "se": 0.0, "source": "未检出"}
                continue
            try:
                conc, se = model.predict(peak["intensity"])
            except ValueError:
                continue
            self.chem[el] = {"conc": conc, "se": se, "source": "定标"}
            n_ok += 1
        self._fill_table()
        self.run_match()
        if n_ok == 0:
            QMessageBox.warning(self, "导入失败",
                                "当前光谱中未找到已定标元素的峰，请检查光谱与谱线。")

    def _peak_for_element(self, element):
        for m in self.main.matches:
            if m["element"] == element:
                return {"wl": m["wl"], "intensity": m["intensity"]}
        return None

    def _fill_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.chem))
        for i, (el, d) in enumerate(self.chem.items()):
            name = ELEMENT_NAMES.get(el, el)
            conc = d["conc"]
            se = d["se"]
            nd = self._nd(d)
            self.table.setItem(i, 0, QTableWidgetItem(f"{el} ({name})"))
            if nd:
                item = QTableWidgetItem("ND")
                item.setForeground(Qt.gray)
                self.table.setItem(i, 1, item)
            else:
                item = QTableWidgetItem(f"{conc:.4f}")
                self.table.setItem(i, 1, item)
            self.table.setItem(i, 2, QTableWidgetItem(f"±{se:.4f}" if se else ""))
            # 牌号规格与状态在匹配后填
            self.table.setItem(i, 3, QTableWidgetItem(""))
            self.table.setItem(i, 4, QTableWidgetItem(""))
        self.table.blockSignals(False)

    def _on_cell_edited(self, item):
        if item.column() != 1:
            return
        el = self._row_element(item.row()).split(" ")[0]
        if not el:
            return
        try:
            val = float(item.text())
        except ValueError:
            QMessageBox.warning(self, "格式错误", "浓度必须是数字。")
            self.table.blockSignals(True)
            item.setText(f"{self.chem.get(el, {}).get('conc', 0):.4f}")
            self.table.blockSignals(False)
            return
        if el not in self.chem:
            self.chem[el] = {"conc": val, "se": 0.0, "source": "手动"}
        else:
            self.chem[el]["conc"] = val
            self.chem[el]["source"] = "手动"
        self.run_match()

    # ------------------------------------------------------------- 匹配
    def run_match(self):
        base = self.cmb_base.currentData()
        chem = {el: (d["conc"], d["se"]) for el, d in self.chem.items()}
        if not chem:
            self.lbl_top.setText("— 无浓度数据，请先导入或输入")
            self.grade_table.setRowCount(0)
            self._plot_compare(None)
            return
        self.grade_results = match_grades(
            chem, bases=[base] if base else None, top_n=5,
            extra_grades=getattr(self.main, "user_grades", None) or None)

        # 顶部大字：Top1
        if self.grade_results:
            top = self.grade_results[0]
            score = top["score"]
            if score >= 90:
                color = _COLORS["good"]
            elif score >= 70:
                color = _COLORS["warn"]
            else:
                color = _COLORS["bad"]
            self.lbl_top.setText(
                f"牌号匹配：{top['grade']}   分数：{score:.0f}/100"
                f"    （{top['base_cn']}）")
            self.lbl_top.setStyleSheet(
                f"background:#0f1720; color:{color}; border-radius:8px;"
                "padding:14px; font-size:22px; font-weight:bold;")
        else:
            self.lbl_top.setText("— 无匹配结果")

        # 列表
        self.grade_table.blockSignals(True)
        self.grade_table.setRowCount(len(self.grade_results))
        for i, r in enumerate(self.grade_results):
            self.grade_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.grade_table.setItem(i, 1, QTableWidgetItem(r["grade"]))
            self.grade_table.setItem(i, 2, QTableWidgetItem(f"{r['score']:.0f}"))
            self.grade_table.setItem(i, 3, QTableWidgetItem(r["base_cn"]))
            if r["penalties"]:
                bad = sorted(r["penalties"].items(), key=lambda x: -x[1])[0]
                self.grade_table.setItem(
                    i, 1, QTableWidgetItem(f"{r['grade']}  ({bad[0]} 超差 {bad[1]:.0f} 分)"))
        self.grade_table.blockSignals(False)

        self._update_spec_column()
        if self.grade_table.rowCount() > 0:
            self.grade_table.selectRow(0)
        else:
            self._plot_compare(None)

    def _update_spec_column(self):
        """把 Top1 牌号的规格写进 Chemistry 表第 4 列，并标记状态颜色。"""
        if not self.grade_results:
            return
        top_spec = self.grade_results[0]["spec"]
        self.table.blockSignals(True)
        for i, el in enumerate(self.chem):
            if el not in top_spec:
                self.table.item(i, 3).setText("—")
                self.table.item(i, 4).setText("")
                continue
            lo, hi = top_spec[el]
            self.table.item(i, 3).setText(f"{lo:.2f} – {hi:.2f}")
            d = self.chem[el]
            nd = self._nd(d)
            if nd:
                self.table.item(i, 4).setText("ND")
                self.table.item(i, 4).setForeground(Qt.gray)
            elif d["conc"] < lo:
                self.table.item(i, 4).setText("偏低")
                self.table.item(i, 4).setForeground(Qt.red)
            elif d["conc"] > hi:
                self.table.item(i, 4).setText("偏高")
                self.table.item(i, 4).setForeground(Qt.red)
            else:
                self.table.item(i, 4).setText("在规格内")
                self.table.item(i, 4).setForeground(Qt.darkGreen)
        self.table.blockSignals(False)

    # ------------------------------------------------------------- 对比图
    def _on_grade_selected(self):
        rows = self.grade_table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        if 0 <= idx < len(self.grade_results):
            self._plot_compare(self.grade_results[idx])

    def _plot_compare(self, result):
        ax = self.ax
        ax.clear()
        if result is None:
            ax.set_title("牌号规格对比（选择匹配结果后显示）")
            ax.axis("off")
            self.canvas.draw_idle()
            return
        spec = result["spec"]
        chem = self.chem
        elems = [el for el in spec if el != "base"]
        if not elems:
            elems = list(chem)
        y = range(len(elems))
        for i, el in enumerate(elems):
            lo, hi = spec.get(el, (None, None))
            if lo is not None:
                w = max(hi - lo, 0.02)
                ax.barh(i, w, left=lo, height=0.55,
                        color="#cfd8dc", edgecolor="#90a4ae", zorder=1)
            d = chem.get(el)
            if d and d["conc"] > 0:
                nd = self._nd(d)
                color = _COLORS["nd"] if nd else (
                    _COLORS["good"] if lo is None or lo <= d["conc"] <= hi
                    else _COLORS["bad"])
                ax.plot(d["conc"], i, "o", ms=9, color=color, zorder=3)
        ax.set_yticks(list(y))
        ax.set_yticklabels(elems)
        ax.set_xlabel("浓度 (wt%)")
        ax.set_title(f"{result['grade']} 规格对比 · 分数 {result['score']:.0f}")
        ax.grid(True, axis="x", alpha=0.3)
        self.fig.tight_layout()
        self.canvas.draw_idle()

    # ------------------------------------------------------------- 导出
    def export_csv(self):
        if not self.chem:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出鉴定结果", "grade_match.csv", "CSV 文件 (*.csv)")
        if not path:
            return
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write("grade,score,base\n")
            for r in self.grade_results:
                f.write(f"{r['grade']},{r['score']:.2f},{r['base_cn']}\n")
            f.write("\nelement,concentration_wt,se_wt,source\n")
            for el, d in self.chem.items():
                f.write(f"{el},{d['conc']:.6f},{d['se']:.6f},{d['source']}\n")
        QMessageBox.information(self, "已导出", f"鉴定结果已保存：\n{path}")
