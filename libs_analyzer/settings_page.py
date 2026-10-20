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
Settings 设置页（参照 SciAps Z-902 Settings）：
- 操作者 / ND 检出规则 / 默认模式 / 默认基体
- 检测参数（最小峰高、峰宽、匹配容差）
- 牌号库管理（用户自定义牌号，对应 Profile Builder 思路）
- 方法（Profile）保存与加载
"""
import json
import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QLabel,
    QLineEdit, QSpinBox, QComboBox, QDoubleSpinBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QInputDialog, QMessageBox, QFileDialog,
)

from .grade_library import BASES, parse_grade_specs, load_user_grades, save_user_grades
from .z902_style import TEXT_FAINT


class SettingsPage(QWidget):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        self._build_ui()
        self.refresh_from_main()
        self._reload_grades()
        self._reload_methods()

    # ------------------------------------------------------------- UI
    def _build_ui(self):
        root = QVBoxLayout(self)

        row = QHBoxLayout()

        # 通用
        gb_gen = QGroupBox("通用")
        f = QFormLayout(gb_gen)
        self.ed_operator = QLineEdit()
        self.ed_operator.textChanged.connect(
            lambda t: setattr(self.main, "operator", t.strip()))
        self.sp_sigma = QSpinBox()
        self.sp_sigma.setRange(1, 10)
        self.sp_sigma.setValue(3)
        self.sp_sigma.setToolTip("测量值必须大于 n×σ 才算检出（Z-902 默认 3σ）")
        self.sp_sigma.valueChanged.connect(self._on_sigma_changed)
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(["Alloy（合金）", "QuickSort（快速分拣）"])
        self.cmb_mode.currentIndexChanged.connect(self._on_mode_changed)
        self.cmb_defbase = QComboBox()
        self.cmb_defbase.addItem("全部元素", None)
        for k, v in BASES.items():
            self.cmb_defbase.addItem(v, k)
        self.cmb_defbase.currentIndexChanged.connect(self._on_defbase_changed)
        f.addRow("操作者", self.ed_operator)
        f.addRow("ND 检出 σ 倍数", self.sp_sigma)
        f.addRow("默认模式", self.cmb_mode)
        f.addRow("默认基体", self.cmb_defbase)
        row.addWidget(gb_gen)

        # 检测参数
        gb_param = QGroupBox("检测参数")
        f = QFormLayout(gb_param)
        self.sp_prom = QDoubleSpinBox()
        self.sp_prom.setRange(0.05, 50.0)
        self.sp_prom.setSuffix(" %")
        self.sp_prom.valueChanged.connect(self._on_param_changed)
        self.sp_width = QSpinBox()
        self.sp_width.setRange(1, 30)
        self.sp_width.valueChanged.connect(self._on_param_changed)
        self.sp_tol = QDoubleSpinBox()
        self.sp_tol.setRange(0.01, 2.0)
        self.sp_tol.setSuffix(" nm")
        self.sp_tol.valueChanged.connect(self._on_param_changed)
        f.addRow("最小峰高", self.sp_prom)
        f.addRow("最小峰宽", self.sp_width)
        f.addRow("匹配容差", self.sp_tol)
        self.btn_apply = QPushButton("应用参数并重新分析")
        self.btn_apply.clicked.connect(self._apply_params)
        f.addRow(self.btn_apply)
        row.addWidget(gb_param)

        # 方法（多方法切换管理）
        gb_prof = QGroupBox("方法（Profile）· 多方法切换")
        f = QFormLayout(gb_prof)
        f.addRow(QLabel("方法列表（data\\profiles\\）："))
        self.cmb_methods = QComboBox()
        f.addRow(self.cmb_methods)
        bar = QHBoxLayout()
        self.btn_apply_method = QPushButton("应用选中")
        self.btn_save_method = QPushButton("保存当前为方法…")
        self.btn_del_method = QPushButton("删除选中")
        self.btn_refresh_methods = QPushButton("刷新列表")
        self.btn_apply_method.clicked.connect(self.apply_selected_method)
        self.btn_save_method.clicked.connect(self.save_method)
        self.btn_del_method.clicked.connect(self.delete_method)
        self.btn_refresh_methods.clicked.connect(self._reload_methods)
        bar.addWidget(self.btn_apply_method)
        bar.addWidget(self.btn_save_method)
        bar.addWidget(self.btn_del_method)
        bar.addWidget(self.btn_refresh_methods)
        f.addRow(bar)
        bar2 = QHBoxLayout()
        self.btn_import_method = QPushButton("导入方法文件…")
        self.btn_export_method = QPushButton("导出方法文件…")
        self.btn_import_method.clicked.connect(self.import_method_file)
        self.btn_export_method.clicked.connect(self.export_method_file)
        bar2.addWidget(self.btn_import_method)
        bar2.addWidget(self.btn_export_method)
        f.addRow(bar2)
        lbl = QLabel("方法包含：操作者/基体/检测参数/ND 规则/默认模式")
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color:{TEXT_FAINT}; font-size:11px;")
        f.addRow(lbl)
        row.addWidget(gb_prof)

        row.addStretch(1)
        root.addLayout(row)

        # 牌号管理
        gb_grades = QGroupBox("牌号库管理（用户自定义）")
        gv = QVBoxLayout(gb_grades)
        bar = QHBoxLayout()
        self.btn_add_grade = QPushButton("添加用户牌号…")
        self.btn_del_grade = QPushButton("删除选中")
        self.btn_reload = QPushButton("刷新")
        self.btn_add_grade.clicked.connect(self.add_grade)
        self.btn_del_grade.clicked.connect(self.delete_grade)
        self.btn_reload.clicked.connect(self._reload_grades)
        bar.addWidget(self.btn_add_grade)
        bar.addWidget(self.btn_del_grade)
        bar.addWidget(self.btn_reload)
        bar.addStretch(1)
        self.lbl_grade_path = QLabel("")
        self.lbl_grade_path.setStyleSheet(f"color:{TEXT_FAINT};")
        bar.addWidget(self.lbl_grade_path)
        gv.addLayout(bar)
        self.grade_table = QTableWidget(0, 4)
        self.grade_table.setHorizontalHeaderLabels(
            ["基体", "牌号", "基体元素", "元素规格"])
        self.grade_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.grade_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.grade_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        gv.addWidget(self.grade_table)
        root.addWidget(gb_grades, 1)

    # ------------------------------------------------------------- 同步
    def refresh_from_main(self):
        """从主窗口读取当前值填入设置页。"""
        m = self.main
        self.ed_operator.setText(m.operator)
        self.sp_sigma.blockSignals(True)
        self.sp_sigma.setValue(m.nd_sigma)
        self.sp_sigma.blockSignals(False)
        self.cmb_defbase.blockSignals(True)
        if m.base_metal:
            idx = self.cmb_defbase.findData(m.base_metal)
            if idx >= 0:
                self.cmb_defbase.setCurrentIndex(idx)
        self.cmb_defbase.blockSignals(False)
        self.cmb_mode.blockSignals(True)
        self.cmb_mode.setCurrentIndex(0 if m.mode == "Alloy" else 1)
        self.cmb_mode.blockSignals(False)
        self.sp_prom.blockSignals(True)
        self.sp_prom.setValue(m.sp_min_prom.value())
        self.sp_prom.blockSignals(False)
        self.sp_width.blockSignals(True)
        self.sp_width.setValue(m.sp_min_width.value())
        self.sp_width.blockSignals(False)
        self.sp_tol.blockSignals(True)
        self.sp_tol.setValue(m.sp_tol.value())
        self.sp_tol.blockSignals(False)

    def _on_sigma_changed(self, v):
        self.main.nd_sigma = v

    def _on_mode_changed(self, i):
        self.main.mode = "Alloy" if i == 0 else "QuickSort"

    def _on_defbase_changed(self):
        self.main.base_metal = self.cmb_defbase.currentData()
        self.main.cmb_base.blockSignals(True)
        idx = self.main.cmb_base.findData(self.main.base_metal)
        self.main.cmb_base.setCurrentIndex(idx if idx >= 0 else 0)
        self.main.cmb_base.blockSignals(False)
        if self.main.spectrum is not None:
            self.main.run_analysis()

    def _on_param_changed(self):
        self.main.sp_min_prom.setValue(self.sp_prom.value())
        self.main.sp_min_width.setValue(self.sp_width.value())
        self.main.sp_tol.setValue(self.sp_tol.value())

    def _apply_params(self):
        self.main.run_analysis()

    # ------------------------------------------------------------- 牌号管理
    def user_grades_path(self):
        return os.path.join(self.main.data_dir, "user_grades.json")

    def _reload_grades(self):
        self.main.user_grades = load_user_grades(self.user_grades_path())
        rows = []
        for base, grades in self.main.user_grades.items():
            for name, spec in grades.items():
                specs = {el: rng for el, rng in spec.items() if el != "base"}
                spec_txt = "; ".join(
                    f"{el}:{lo:g}-{hi:g}" for el, (lo, hi) in specs.items())
                rows.append((BASES.get(base, base), name,
                             spec.get("base", ""), spec_txt))
        self.grade_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, v in enumerate(r):
                self.grade_table.setItem(i, j, QTableWidgetItem(str(v)))
        self.lbl_grade_path.setText(self.user_grades_path())

    def add_grade(self):
        name, ok1 = QInputDialog.getText(self, "添加牌号", "牌号名称（如 MY-500）：")
        if not ok1 or not name.strip():
            return
        base_key, ok2 = QInputDialog.getItem(
            self, "添加牌号", "选择基体：", list(BASES.keys()), 0, False)
        if not ok2:
            return
        base_el, ok3 = QInputDialog.getText(
            self, "添加牌号", "基体元素（如 Fe / Al / Ni）：", text="Fe")
        if not ok3:
            return
        spec_text, ok4 = QInputDialog.getText(
            self, "添加牌号",
            "元素规格（格式：Cr:16-18;Ni:8-10.5;Mo:2-3）：\n"
            "分号分隔，元素:下限-上限（wt%）")
        if not ok4:
            return
        specs = parse_grade_specs(spec_text, base_el.strip() or "Fe")
        if len(specs) <= 1:  # 只有 base
            QMessageBox.warning(self, "格式错误", "请至少填写一个元素规格。")
            return
        self.main.user_grades.setdefault(base_key, {})[name.strip()] = specs
        save_user_grades(self.user_grades_path(), self.main.user_grades)
        self._reload_grades()
        QMessageBox.information(self, "已添加",
                                f"牌号 {name.strip()} 已加入并保存。")

    def delete_grade(self):
        row = self.grade_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择要删除的牌号。")
            return
        base_cn = self.grade_table.item(row, 0).text()
        name = self.grade_table.item(row, 1).text()
        base_key = next((k for k, v in BASES.items() if v == base_cn), base_cn)
        if QMessageBox.question(self, "确认",
                                f"删除用户牌号 {name}（{base_cn}）？") == QMessageBox.Yes:
            if base_key in self.main.user_grades:
                self.main.user_grades[base_key].pop(name, None)
                if not self.main.user_grades[base_key]:
                    del self.main.user_grades[base_key]
                save_user_grades(self.user_grades_path(), self.main.user_grades)
                self._reload_grades()

    # ------------------------------------------------------------- 方法（多方法切换）
    def profile_dir(self):
        return os.path.join(self.main.data_dir, "profiles")

    def _current_prof(self):
        """读取当前软件状态为方法字典。"""
        return {
            "operator": self.main.operator,
            "nd_sigma": self.main.nd_sigma,
            "mode": self.main.mode,
            "base": self.main.base_metal,
            "prom": self.main.sp_min_prom.value(),
            "width": self.main.sp_min_width.value(),
            "tol": self.main.sp_tol.value(),
        }

    def _reload_methods(self):
        """扫描 data/profiles/*.json，刷新方法列表下拉框。"""
        d = self.profile_dir()
        names = []
        if os.path.isdir(d):
            names = sorted(
                f[:-5] for f in os.listdir(d)
                if f.lower().endswith(".json"))
        self.cmb_methods.clear()
        self.cmb_methods.addItems(names)
        self.cmb_methods.setEnabled(bool(names))
        self.btn_apply_method.setEnabled(bool(names))
        self.btn_del_method.setEnabled(bool(names))

    def save_method(self):
        """将当前设置保存为命名方法（多方法之一）。"""
        name, ok = QInputDialog.getText(
            self, "保存为方法", "方法名称（如：不锈钢快检 / 铝合金常规）：")
        if not ok or not name.strip():
            return
        name = name.strip()
        # 避免路径穿越与非法字符
        for ch in r'\/:*?"<>|':
            name = name.replace(ch, "_")
        path = os.path.join(self.profile_dir(), name + ".json")
        if os.path.exists(path) and QMessageBox.question(
                self, "确认覆盖", f"方法「{name}」已存在，覆盖？") != QMessageBox.Yes:
            return
        os.makedirs(self.profile_dir(), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._current_prof(), f, ensure_ascii=False, indent=1)
        self._reload_methods()
        idx = self.cmb_methods.findText(name)
        if idx >= 0:
            self.cmb_methods.setCurrentIndex(idx)
        QMessageBox.information(self, "已保存", f"方法「{name}」已保存到：\n{path}")

    def apply_selected_method(self):
        name = self.cmb_methods.currentText()
        if not name:
            QMessageBox.information(self, "提示", "请先在列表中选择方法。")
            return
        self._apply_profile_file(os.path.join(self.profile_dir(), name + ".json"))

    def delete_method(self):
        name = self.cmb_methods.currentText()
        if not name:
            QMessageBox.information(self, "提示", "请先在列表中选择方法。")
            return
        path = os.path.join(self.profile_dir(), name + ".json")
        if QMessageBox.question(self, "确认",
                                f"删除方法「{name}」？") == QMessageBox.Yes:
            try:
                os.remove(path)
            except OSError:
                pass
            self._reload_methods()
            QMessageBox.information(self, "已删除", f"方法「{name}」已删除。")

    def export_method_file(self):
        """将当前设置导出为外部 JSON 文件。"""
        path, _ = QFileDialog.getSaveFileName(
            self, "导出方法文件", os.path.join(self.profile_dir(), "method.json"),
            "JSON 文件 (*.json)")
        if not path:
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._current_prof(), f, ensure_ascii=False, indent=1)
        QMessageBox.information(self, "已导出", f"方法文件已导出：\n{path}")

    def import_method_file(self):
        """导入外部方法 JSON 文件并应用。"""
        path, _ = QFileDialog.getOpenFileName(
            self, "导入方法文件", self.profile_dir(), "JSON 文件 (*.json)")
        if not path:
            return
        self._apply_profile_file(path)

    def _apply_profile_file(self, path):
        """应用一个方法 JSON 文件到主窗口。"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                prof = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            QMessageBox.warning(self, "加载失败", str(e))
            return
        m = self.main
        m.operator = prof.get("operator", "")
        m.nd_sigma = int(prof.get("nd_sigma", 3))
        m.mode = prof.get("mode", "Alloy")
        m.sp_min_prom.setValue(float(prof.get("prom", 1.0)))
        m.sp_min_width.setValue(int(prof.get("width", 3)))
        m.sp_tol.setValue(float(prof.get("tol", 0.3)))
        base = prof.get("base")
        m.base_metal = base
        idx = m.cmb_base.findData(base)
        m.cmb_base.setCurrentIndex(idx if idx >= 0 else 0)
        self.refresh_from_main()
        if m.spectrum is not None:
            m.run_analysis()
        QMessageBox.information(self, "已应用", f"方法已应用：\n{path}")
