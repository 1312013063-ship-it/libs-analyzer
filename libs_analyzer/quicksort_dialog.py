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
QuickSort 快速分拣（参照 SciAps Z-902 QuickSort App）：
以最快速度对样品做材料分类/牌号鉴定——加载光谱即自动分析，
大字显示 Top 牌号与分数，可一键记录到结果。
"""
import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QFileDialog, QHeaderView,
    QAbstractItemView, QMessageBox,
)

from .element_lines import ELEMENT_NAMES, match_lines
from .peak_detect import detect_peaks
from .data_io import load_spectrum
from .grade_library import match_grades


class QuickSortDialog(QDialog):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        self.chem = {}
        self.grades = []
        self._build_ui()
        self.resize(760, 620)
        self.setWindowTitle("QuickSort 快速分拣（参照 SciAps Z-902）")

    def _build_ui(self):
        root = QVBoxLayout(self)

        bar = QHBoxLayout()
        self.btn_open = QPushButton("打开光谱文件…")
        self.btn_open.clicked.connect(self.open_file)
        self.btn_record = QPushButton("记录到结果")
        self.btn_record.clicked.connect(self.record_result)
        bar.addWidget(self.btn_open)
        bar.addWidget(self.btn_record)
        bar.addStretch(1)
        self.lbl_name = QLabel("未加载光谱")
        self.lbl_name.setStyleSheet("color:#555;")
        bar.addWidget(self.lbl_name)
        root.addLayout(bar)

        self.lbl_grade = QLabel("—\n打开光谱后自动显示牌号")
        self.lbl_grade.setAlignment(Qt.AlignCenter)
        self.lbl_grade.setStyleSheet(
            "background:#0f1720; color:#e8eef5; border-radius:10px;"
            "padding:18px; font-size:30px; font-weight:bold;")
        self.lbl_grade.setMinimumHeight(120)
        root.addWidget(self.lbl_grade)

        root.addWidget(QLabel("牌号匹配 Top 5"))
        self.grade_table = QTableWidget(0, 4)
        self.grade_table.setHorizontalHeaderLabels(["排名", "牌号", "分数", "基体"])
        self.grade_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.grade_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.grade_table.setMaximumHeight(180)
        root.addWidget(self.grade_table)

        root.addWidget(QLabel("Chemistry（有定标的元素自动反推）"))
        self.chem_table = QTableWidget(0, 3)
        self.chem_table.setHorizontalHeaderLabels(["元素", "浓度 (wt%)", "± 标准误"])
        self.chem_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.chem_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        root.addWidget(self.chem_table, 1)

    # ------------------------------------------------------------- 分析
    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "打开光谱文件", "",
            "光谱文件 (*.txt *.csv *.asc *.dat);;所有文件 (*.*)")
        if not path:
            return
        try:
            spec = load_spectrum(path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "打开失败", str(e))
            return

        m = self.main
        prom = m.sp_min_prom.value() / 100.0
        minw = m.sp_min_width.value()
        tol = m.sp_tol.value()
        _, info = detect_peaks(spec.wl, spec.intensity,
                               prominence_frac=prom, min_width_pts=minw)

        # 定标导入浓度（与合金鉴定一致）
        self.chem = {}
        for el, model in m.calibrations.items():
            peak = None
            for p in info:
                cands = match_lines(p["wl"], tol)
                if cands and cands[0]["element"] == el:
                    peak = p
                    break
            if peak is None:
                self.chem[el] = {"conc": 0.0, "se": 0.0, "source": "未检出"}
                continue
            try:
                conc, se = model.predict(peak["intensity"])
            except ValueError:
                continue
            self.chem[el] = {"conc": conc, "se": se, "source": "定标"}

        chem_flat = {el: (d["conc"], d["se"]) for el, d in self.chem.items()}
        base = m.base_metal
        self.grades = match_grades(
            chem_flat, bases=[base] if base else None, top_n=5,
            extra_grades=m.user_grades) if chem_flat else []

        self.lbl_name.setText(f"光谱：{os.path.basename(path)}　"
                              f"（峰 {len(info)} 个）")

        if self.grades:
            top = self.grades[0]
            if top["score"] >= 90:
                color = "#1e8e3e"
            elif top["score"] >= 70:
                color = "#f9a825"
            else:
                color = "#d93025"
            self.lbl_grade.setStyleSheet(
                f"background:#0f1720; color:{color}; border-radius:10px;"
                "padding:18px; font-size:30px; font-weight:bold;")
            self.lbl_grade.setText(
                f"{top['grade']}　分数 {top['score']:.0f}/100\n"
                f"（{top['base_cn']}）")
        else:
            self.lbl_grade.setStyleSheet(
                "background:#0f1720; color:#e8eef5; border-radius:10px;"
                "padding:18px; font-size:24px; font-weight:bold;")
            self.lbl_grade.setText("未匹配到牌号\n（请先建立元素定标或选择基体）")

        self.grade_table.setRowCount(len(self.grades))
        for i, g in enumerate(self.grades):
            self.grade_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.grade_table.setItem(i, 1, QTableWidgetItem(g["grade"]))
            self.grade_table.setItem(i, 2, QTableWidgetItem(f"{g['score']:.0f}"))
            self.grade_table.setItem(i, 3, QTableWidgetItem(g["base_cn"]))

        self.chem_table.setRowCount(len(self.chem))
        for i, (el, d) in enumerate(self.chem.items()):
            self.chem_table.setItem(i, 0, QTableWidgetItem(
                f"{el} ({ELEMENT_NAMES.get(el, el)})"))
            self.chem_table.setItem(i, 1, QTableWidgetItem(
                f"{d['conc']:.4f}" if d["conc"] > 0 else "ND"))
            self.chem_table.setItem(i, 2, QTableWidgetItem(
                f"±{d['se']:.4f}" if d["se"] else ""))

    # ------------------------------------------------------------- 记录
    def record_result(self):
        if not self.grades and not self.chem:
            QMessageBox.information(self, "提示", "请先打开一个光谱文件进行分析。")
            return
        m = self.main
        rec = m.records.add(
            mode="QuickSort",
            base=m.base_metal or "",
            spectrum_name=self.lbl_name.text(),
            n_peaks=0,
            operator=m.operator,
            chemistry=self.chem,
            grades=[{k: g[k] for k in ("grade", "score", "base", "base_cn")}
                    for g in self.grades])
        QMessageBox.information(
            self, "已记录",
            f"已保存为测试 #{rec.number}，可在「Results」中查看。")
