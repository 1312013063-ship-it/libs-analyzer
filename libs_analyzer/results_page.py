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
Results 结果页（参照 SciAps Z-902 Results）：
- 测试历史列表：编号 / 时间 / 模式 / 牌号匹配 / 光谱名
- 按日期筛选、多选、删除、导出全部
- 详情：Test Info / Chemistry / Grade Match / CE / 样品照片
- 分析平均化：选中多条记录生成 AVG 记录
"""
import os

import numpy as np
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox, QInputDialog,
    QHeaderView, QAbstractItemView, QDateEdit, QGroupBox,
)

from .element_lines import ELEMENT_NAMES
from .test_records import calc_ce, average_records
from .excel_export import export_records_xlsx, templates, template_name
from .z902_style import BRAND, BG_CARD, TEXT, TEXT_DIM, TEXT_FAINT, qcolor

_HEADERS = ["编号", "时间", "模式", "牌号 (分数)", "光谱"]


class ResultsPage(QWidget):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        self._build_ui()
        self._d0 = None
        self._d1 = None

    def _build_ui(self):
        root = QVBoxLayout(self)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("日期筛选："))
        self.de_from = QDateEdit(QDate.currentDate().addDays(-30))
        self.de_from.setCalendarPopup(True)
        self.de_to = QDateEdit(QDate.currentDate())
        self.de_to.setCalendarPopup(True)
        bar.addWidget(self.de_from)
        bar.addWidget(QLabel("至"))
        bar.addWidget(self.de_to)
        self.btn_filter = QPushButton("应用")
        self.btn_filter.clicked.connect(self.apply_filter)
        self.btn_clear = QPushButton("清除")
        self.btn_clear.clicked.connect(self.clear_filter)
        bar.addWidget(self.btn_filter)
        bar.addWidget(self.btn_clear)
        bar.addSpacing(12)
        self.btn_avg = QPushButton("平均选中 → 生成 AVG")
        self.btn_avg.clicked.connect(self.average_selected)
        self.btn_photo = QPushButton("附加样品照片…")
        self.btn_photo.clicked.connect(self.attach_photo)
        self.btn_del = QPushButton("删除选中")
        self.btn_del.clicked.connect(self.delete_selected)
        self.btn_delall = QPushButton("清空全部")
        self.btn_delall.clicked.connect(self.clear_all)
        self.btn_export = QPushButton("导出 CSV…")
        self.btn_excel = QPushButton("导出 Excel…")
        self.btn_export.clicked.connect(self.export_csv)
        self.btn_excel.clicked.connect(self.export_excel)
        for b in (self.btn_avg, self.btn_photo, self.btn_del, self.btn_delall,
                  self.btn_export, self.btn_excel):
            bar.addWidget(b)
        bar.addStretch(1)
        root.addLayout(bar)

        split = QSplitter(Qt.Horizontal)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 4, 0)
        self.lbl_count = QLabel("")
        lv.addWidget(self.lbl_count)
        self.table = QTableWidget(0, len(_HEADERS))
        self.table.setHorizontalHeaderLabels(_HEADERS)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self._show_detail)
        self.table.doubleClicked.connect(self._go_to_test)
        lv.addWidget(self.table)
        split.addWidget(left)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(4, 0, 0, 0)

        self.lbl_info = QLabel("选择一条测试查看详情")
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setStyleSheet(
            f"background:{BG_CARD}; color:{TEXT}; border-radius:6px;"
            "padding:10px; font-size:14px; font-weight:bold;")
        rv.addWidget(self.lbl_info)

        gb_chem = QGroupBox("Chemistry")
        cv = QVBoxLayout(gb_chem)
        self.chem_table = QTableWidget(0, 4)
        self.chem_table.setHorizontalHeaderLabels(
            ["元素", "浓度 (wt%)", "± 标准误", "来源"])
        self.chem_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.chem_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        cv.addWidget(self.chem_table)
        self.lbl_ce = QLabel("")
        self.lbl_ce.setStyleSheet(
            f"color:{BRAND}; font-weight:bold; padding:2px;")
        cv.addWidget(self.lbl_ce)
        rv.addWidget(gb_chem, 2)

        gb_grade = QGroupBox("Grade Match")
        gv = QVBoxLayout(gb_grade)
        self.grade_table = QTableWidget(0, 3)
        self.grade_table.setHorizontalHeaderLabels(["排名", "牌号", "分数"])
        self.grade_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.grade_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        gv.addWidget(self.grade_table)
        rv.addWidget(gb_grade, 1)

        self.photo = QLabel("（无样品照片）")
        self.photo.setAlignment(Qt.AlignCenter)
        self.photo.setStyleSheet(
            f"border:1px dashed {TEXT_FAINT}; color:{TEXT_FAINT}; padding:6px;")
        self.photo.setFixedHeight(120)
        rv.addWidget(self.photo)

        split.addWidget(right)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 4)
        root.addWidget(split, 1)

    # ------------------------------------------------------------- 数据
    def apply_filter(self):
        self._d0 = self.de_from.date().toPyDate()
        self._d1 = self.de_to.date().toPyDate()
        self.refresh()

    def clear_filter(self):
        self._d0 = None
        self._d1 = None
        self.refresh()

    def visible_records(self):
        recs = self.main.records.filter_by_date(self._d0, self._d1)
        return sorted(recs, key=lambda r: r.number, reverse=True)

    def refresh(self):
        recs = self.visible_records()
        self.table.blockSignals(True)
        self.table.setRowCount(len(recs))
        for i, r in enumerate(recs):
            mode = ("AVG" if r.is_avg else r.mode)
            self.table.setItem(i, 0, QTableWidgetItem(f"#{r.number}"))
            self.table.setItem(i, 1, QTableWidgetItem(r.timestamp))
            it = QTableWidgetItem(mode)
            if r.is_avg:
                it.setForeground(qcolor(BRAND))
            self.table.setItem(i, 2, it)
            grade_txt = ""
            if r.grades:
                top = r.grades[0]
                grade_txt = f"{top['grade']}  {top['score']:.0f}"
            self.table.setItem(i, 3, QTableWidgetItem(grade_txt))
            self.table.setItem(i, 4, QTableWidgetItem(r.spectrum_name))
        self.table.blockSignals(False)
        self.lbl_count.setText(f"共 {len(recs)} 条测试记录"
                               + ("（按日期筛选）" if self._d0 else ""))
        self._show_detail()

    def _selected_numbers(self):
        rows = set()
        for idx in self.table.selectionModel().selectedRows():
            rows.add(idx.row())
        recs = self.visible_records()
        return [recs[r].number for r in sorted(rows)]

    # ------------------------------------------------------------- 详情
    def _show_detail(self):
        nums = self._selected_numbers()
        if not nums:
            self.lbl_info.setText("选择一条测试查看详情")
            self.chem_table.setRowCount(0)
            self.grade_table.setRowCount(0)
            self.lbl_ce.setText("")
            self.photo.setText("（无样品照片）")
            return
        rec = self.main.records.get(nums[0])
        if rec is None:
            return
        mode = "AVG（平均值）" if rec.is_avg else rec.mode
        self.lbl_info.setText(
            f"测试 #{rec.number} ｜ {mode} ｜ {rec.timestamp}"
            f"{(' ｜ 基体 ' + rec.base) if rec.base else ''}"
            f"{(' ｜ 操作者 ' + rec.operator) if rec.operator else ''}"
            f" ｜ 光谱：{rec.spectrum_name or '—'}"
            f"{' ｜ 峰 ' + str(rec.n_peaks) if rec.n_peaks else ''}")

        chem = rec.chemistry
        self.chem_table.setRowCount(len(chem))
        for i, (el, d) in enumerate(chem.items()):
            self.chem_table.setItem(i, 0, QTableWidgetItem(
                f"{el} ({ELEMENT_NAMES.get(el, el)})"))
            conc = d.get("conc")
            se = d.get("se")
            self.chem_table.setItem(i, 1, QTableWidgetItem(
                f"{conc:.4f}" if conc is not None else "ND"))
            self.chem_table.setItem(i, 2, QTableWidgetItem(
                f"±{se:.4f}" if se else ""))
            self.chem_table.setItem(i, 3, QTableWidgetItem(d.get("source", "")))

        ce = calc_ce(chem)
        self.lbl_ce.setText(
            f"碳当量 CE（IIW）= {ce['value']:.3f}%　( C {ce['elements']['C']:.3f}"
            f" / Mn {ce['elements']['Mn']:.3f} / Cr {ce['elements']['Cr']:.3f}"
            f" / Mo {ce['elements']['Mo']:.3f} / Ni {ce['elements']['Ni']:.3f}"
            f" )" if ce else "")

        grades = rec.grades
        self.grade_table.setRowCount(len(grades))
        for i, g in enumerate(grades):
            self.grade_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.grade_table.setItem(i, 1, QTableWidgetItem(g["grade"]))
            self.grade_table.setItem(i, 2, QTableWidgetItem(f"{g['score']:.0f}/100"))

        if rec.photo_path and os.path.exists(rec.photo_path):
            pm = QPixmap(rec.photo_path)
            if not pm.isNull():
                self.photo.setPixmap(pm.scaled(
                    self.photo.width(), self.photo.height(),
                    Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.photo.setText("（图片无法读取）")
        else:
            self.photo.setText("（无样品照片）")

    def _go_to_test(self):
        nums = self._selected_numbers()
        if nums:
            self.main.show_test_detail(nums[0])

    # ------------------------------------------------------------- 操作
    def average_selected(self):
        nums = self._selected_numbers()
        recs = [self.main.records.get(n) for n in nums]
        recs = [r for r in recs if r and r.chemistry]
        if len(recs) < 2:
            QMessageBox.information(
                self, "平均化",
                "请至少选择 2 条带化学结果（Chemistry）的测试记录。\n"
                "提示：化学结果来自「合金鉴定」的浓度导入/输入。")
            return
        chem, n = average_records(recs)
        base = self.main.base_metal or ""
        rec = self.main.records.add(
            mode="AVG", base=base,
            spectrum_name=f"平均 {n} 次测试",
            chemistry=chem, is_avg=True,
            operator=self.main.operator)
        self.refresh()
        self.table.selectRow(0)
        QMessageBox.information(self, "平均化完成",
                                f"已生成 AVG 测试 #{rec.number}（{n} 次测试平均）。\n"
                                "可在「合金鉴定」中基于平均浓度做牌号匹配。")

    def attach_photo(self):
        nums = self._selected_numbers()
        if not nums:
            QMessageBox.information(self, "提示", "请先选择一条测试记录。")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "选择样品照片", "", "图片 (*.png *.jpg *.jpeg *.bmp)")
        if not path:
            return
        for n in nums:
            self.main.records.update(n, photo_path=path)
        self._show_detail()

    def delete_selected(self):
        nums = self._selected_numbers()
        if not nums:
            QMessageBox.information(self, "提示", "请先选择要删除的测试。")
            return
        if QMessageBox.question(
                self, "确认", f"删除选中的 {len(nums)} 条测试记录？") == QMessageBox.Yes:
            self.main.records.delete(nums)
            self.refresh()

    def clear_all(self):
        if not self.main.records.records:
            return
        if QMessageBox.question(self, "确认", "清空所有测试记录？") == QMessageBox.Yes:
            self.main.records.clear()
            self.refresh()

    def export_csv(self):
        recs = self.visible_records()
        if not recs:
            QMessageBox.information(self, "提示", "没有可导出的记录。")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出测试记录", "results.csv", "CSV 文件 (*.csv)")
        if not path:
            return
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write("number,timestamp,mode,spectrum,grade,score,"
                    "operator,base,chemistry\n")
            for r in recs:
                grade = r.grades[0]["grade"] if r.grades else ""
                score = f"{r.grades[0]['score']:.1f}" if r.grades else ""
                chem_txt = ";".join(
                    f"{el}={d.get('conc', '')}" for el, d in r.chemistry.items())
                f.write(f"{r.number},{r.timestamp},{r.mode},{r.spectrum_name},"
                        f"{grade},{score},{r.operator},{r.base},{chem_txt}\n")
        QMessageBox.information(self, "已导出", f"记录已保存：\n{path}")

    def export_excel(self):
        """导出 Excel（Z-902 模板导出）：选择模板后生成 .xlsx。"""
        recs = self.visible_records()
        if not recs:
            QMessageBox.information(self, "提示", "没有可导出的记录。")
            return
        tpl_items = [template_name(t) for t in templates()]
        tpl_name, ok = QInputDialog.getItem(
            self, "选择导出模板", "Excel 模板：", tpl_items, 0, False)
        if not ok:
            return
        tpl = templates()[tpl_items.index(tpl_name)]
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 Excel", "results.xlsx", "Excel 文件 (*.xlsx)")
        if not path:
            return
        try:
            export_records_xlsx(path, recs, template=tpl)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "导出失败", str(e))
            return
        QMessageBox.information(self, "已导出",
                                f"Excel（模板：{tpl_name}）已保存：\n{path}")
