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
Libs通用测试软件 - 主窗口（PyQt5 + matplotlib）

三大模块（参照 SciAps Z-902 Launch Screen）：
  Analyze  分析：光谱 / 峰检测 / 元素匹配 / 定量 / 合金鉴定 / Matrix / QuickSort
  Results  结果：测试历史（编号/时间/牌号/筛选/删除/导出/照片/平均化）
  Settings 设置：操作者 / ND 规则 / 检测参数 / 牌号库管理 / 方法(Profile)
"""
import os
import sys

import numpy as np

import matplotlib
matplotlib.use("Qt5Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTabWidget,
    QLabel, QPushButton, QDoubleSpinBox, QSpinBox, QCheckBox, QComboBox,
    QGroupBox, QFormLayout, QTableWidget, QTableWidgetItem,
    QFileDialog, QMessageBox, QApplication, QHeaderView, QAbstractItemView,
)

from . import __appname__, __version__
from .element_lines import match_lines, ELEMENT_NAMES
from .peak_detect import detect_peaks
from .data_io import (load_spectrum, save_spectrum_csv, save_peaks_csv,
                      SpectrumData, load_pulse_series, load_pulse_folder)
from .demo_data import generate_demo_spectrum, generate_demo_pulses
from .pulse_quality import PulseData, analyze_pulses, average_valid_pulses
from .pulse_quality_dialog import PulseQualityDialog
from .quant_dialog import QuantDialog
from .quant import CalibrationStore
from .grade_match_dialog import GradeMatchDialog
from .matrix_dialog import MatrixDialog
from .quicksort_dialog import QuickSortDialog
from .results_page import ResultsPage
from .settings_page import SettingsPage
from .grade_library import BASE_SUITES, BASES, load_user_grades
from .test_records import RecordsStore
from .report import build_html_report
from .ai_graph_dialog import AIGraphDialog
from .z902_style import (Z902_QSS, BRAND, BG, BG_PANEL, BG_CARD, PLOT_BG,
                         PLOT_GRID, TEXT, TEXT_DIM, TEXT_FAINT, ACCENT,
                         OK, WARN, DANGER, qcolor)

# 中文字体
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

_TABLE_HEADERS = ["峰号", "波长(nm)", "强度", "FWHM(nm)",
                  "元素", "谱线(nm)", "偏差(nm)", "相对强度"]

# 应用数据目录：源码运行=项目根；PyInstaller 打包运行=exe 所在目录
if getattr(sys, "frozen", False):
    _APP_DIR = os.path.dirname(sys.executable)
else:
    _APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{__appname__} v{__version__}")
        self.resize(1360, 860)

        self.spectrum = None          # SpectrumData
        self.pulse_data = None        # PulseData（多脉冲；所有原始脉冲谱图保留）
        self.peaks_info = []          # list[dict]
        self.matches = []             # list[dict] 合并后的分析结果行
        self._data_file = None
        self.base_metal = None        # 当前基体（None=全部）
        self.calibrations = {}        # 元素 -> CalibrationModel（定量定标）
        # Z-902 风格：结果记录 / 设置
        self.data_dir = os.path.join(_APP_DIR, "data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.records = RecordsStore(os.path.join(self.data_dir, "records.json"))
        self.user_grades = load_user_grades(
            os.path.join(self.data_dir, "user_grades.json"))
        self.calibrations = CalibrationStore(
            os.path.join(self.data_dir, "calibrations.json")).load()
        self.operator = ""
        self.nd_sigma = 3             # ND 判定：浓度 < n×σ 判未检出
        self.mode = "Alloy"           # Alloy / QuickSort

        self._build_ui()
        self._create_menu()
        self.statusBar().showMessage("就绪：请打开光谱文件或生成演示光谱")

        # 启动时自动载入演示光谱
        self.load_demo()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        # 外层容器：品牌横幅 + 三大模块标签页
        central = QWidget()
        cv = QVBoxLayout(central)
        cv.setContentsMargins(10, 10, 10, 6)
        cv.setSpacing(8)
        cv.addWidget(self._build_banner())

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # ---------- Analyze 页
        tab_analyze = QWidget()
        root = QHBoxLayout(tab_analyze)
        root.setContentsMargins(4, 4, 4, 4)

        split = QSplitter(Qt.Horizontal)

        # ---- 左侧控制面板
        panel = QWidget()
        panel.setFixedWidth(272)
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(0, 0, 4, 0)

        gb_data = QGroupBox("数据")
        f = QFormLayout(gb_data)
        self.btn_open = QPushButton("打开光谱文件…")
        self.btn_demo = QPushButton("生成演示光谱")
        self.btn_demo_pulses = QPushButton("生成演示多脉冲")
        self.btn_pulse_file = QPushButton("打开多脉冲文件…")
        self.btn_open.clicked.connect(self.open_file)
        self.btn_demo.clicked.connect(self.load_demo)
        self.btn_demo_pulses.clicked.connect(self.load_demo_pulses)
        self.btn_pulse_file.clicked.connect(self.open_pulse_file)
        self.btn_demo_pulses.setToolTip(
            "生成一次测量的多个激光脉冲（含饱和/弱信号/噪声/漂移样例），"
            "AI 自动甄别无效脉冲")
        self.btn_pulse_file.setToolTip(
            "多列文本：第一列波长，其余每列一个脉冲")
        f.addRow(self.btn_open)
        f.addRow(self.btn_demo)
        f.addRow(self.btn_demo_pulses)
        f.addRow(self.btn_pulse_file)
        pl.addWidget(gb_data)

        gb_mode = QGroupBox("检测模式")
        fm = QFormLayout(gb_mode)
        self.cmb_base = QComboBox()
        self.cmb_base.addItem("全部元素", None)
        for k, v in BASES.items():
            self.cmb_base.addItem(v, k)
        self.cmb_base.currentIndexChanged.connect(self._on_base_changed)
        fm.addRow("合金基体", self.cmb_base)
        pl.addWidget(gb_mode)

        gb_peak = QGroupBox("峰值检测")
        f = QFormLayout(gb_peak)
        self.sp_min_prom = QDoubleSpinBox()
        self.sp_min_prom.setRange(0.05, 50.0)
        self.sp_min_prom.setValue(1.0)
        self.sp_min_prom.setSuffix(" %")
        self.sp_min_prom.setToolTip("峰显著度阈值（相对最高峰强度的百分比）")
        self.sp_min_width = QSpinBox()
        self.sp_min_width.setRange(1, 30)
        self.sp_min_width.setValue(3)
        self.sp_min_width.setToolTip("峰最小宽度（数据点个数）")
        f.addRow("最小峰高", self.sp_min_prom)
        f.addRow("最小峰宽", self.sp_min_width)
        pl.addWidget(gb_peak)

        gb_match = QGroupBox("元素匹配")
        f = QFormLayout(gb_match)
        self.sp_tol = QDoubleSpinBox()
        self.sp_tol.setRange(0.01, 2.0)
        self.sp_tol.setValue(0.30)
        self.sp_tol.setSuffix(" nm")
        self.sp_tol.setToolTip("峰与元素谱线的最大波长偏差")
        self.cb_annotate = QCheckBox("图上标注元素符号")
        self.cb_annotate.setChecked(True)
        f.addRow("匹配容差", self.sp_tol)
        f.addRow("", self.cb_annotate)
        pl.addWidget(gb_match)

        self.btn_analyze = QPushButton("执行分析（开始测试）")
        self.btn_analyze.clicked.connect(self.run_analysis)
        self.btn_analyze.setMinimumHeight(34)
        pl.addWidget(self.btn_analyze)

        gb_apps = QGroupBox("应用")
        fa = QFormLayout(gb_apps)
        self.btn_ai = QPushButton("AI 分析图谱")
        self.btn_ai.setObjectName("primary")
        self.btn_ai.setToolTip("智能解读本次测试：元素置信度 + 材料推断 + 关系图谱")
        self.btn_ai.clicked.connect(self.open_ai_insight)
        fa.addRow(self.btn_ai)
        self.btn_quant = QPushButton("定量分析 · 定标曲线")
        self.btn_quant.setToolTip("标准样建立定标曲线，反推未知样品浓度")
        self.btn_quant.clicked.connect(self.open_quant)
        self.btn_grade = QPushButton("合金鉴定 · 牌号匹配")
        self.btn_grade.setToolTip("参照 SciAps Z-902：Chemistry + Grade Match")
        self.btn_grade.clicked.connect(self.open_grade_match)
        self.btn_matrix = QPushButton("多次测量平均 · Matrix")
        self.btn_matrix.setToolTip("同一样品多次测量汇总：AVG/SD/RSD")
        self.btn_matrix.clicked.connect(self.open_matrix)
        self.btn_quicksort = QPushButton("QuickSort 快速分拣")
        self.btn_quicksort.setToolTip("加载光谱即自动鉴定牌号，适合快速分类")
        self.btn_quicksort.clicked.connect(self.open_quicksort)
        self.btn_pulse = QPushButton("脉冲质量 · AI 甄别")
        self.btn_pulse.setObjectName("primary")
        self.btn_pulse.setToolTip(
            "多脉冲数据：全部原始谱图如实保留，AI 自动识别无效脉冲"
            "并提示改进方向；可手动标记无效谱图后重算平均谱")
        self.btn_pulse.clicked.connect(self.open_pulse_quality)
        self.btn_pulse.setEnabled(False)
        for b in (self.btn_ai, self.btn_quant, self.btn_grade, self.btn_matrix,
                  self.btn_quicksort, self.btn_pulse):
            b.setMinimumHeight(30)
            fa.addRow(b)
        pl.addWidget(gb_apps)

        gb_out = QGroupBox("导出")
        f = QFormLayout(gb_out)
        self.btn_png = QPushButton("光谱图 PNG")
        self.btn_peaks = QPushButton("结果 CSV")
        self.btn_report = QPushButton("HTML 报告")
        self.btn_png.clicked.connect(self.export_png)
        self.btn_peaks.clicked.connect(self.export_csv)
        self.btn_report.clicked.connect(self.export_report)
        f.addRow(self.btn_png)
        f.addRow(self.btn_peaks)
        f.addRow(self.btn_report)
        pl.addWidget(gb_out)

        self.lbl_info = QLabel("未加载数据")
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setStyleSheet(
            f"background:{BG_CARD}; color:{TEXT_DIM}; border-radius:6px;"
            "padding:8px;")
        pl.addWidget(self.lbl_info)
        pl.addStretch(1)

        # ---- 右侧：图 + 表格
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(4, 0, 0, 0)

        self.fig = plt.Figure(figsize=(9, 4.6), dpi=100)
        self.fig.patch.set_facecolor(BG)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setStyleSheet(f"background:{BG};")
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor(PLOT_BG)

        self.table = QTableWidget(0, len(_TABLE_HEADERS))
        self.table.setHorizontalHeaderLabels(_TABLE_HEADERS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)

        split_right = QSplitter(Qt.Vertical)
        split_right.addWidget(self.toolbar)
        split_right.addWidget(self.canvas)
        split_right.addWidget(self.table)
        split_right.setStretchFactor(1, 3)
        split_right.setStretchFactor(2, 2)
        split_right.setSizes([36, 470, 280])

        rl.addWidget(split_right)

        split.addWidget(panel)
        split.addWidget(right)
        split.setStretchFactor(1, 1)
        root.addWidget(split)

        self.tabs.addTab(tab_analyze, "Analyze · 分析")

        # ---------- Results / Settings 页
        self.results_page = ResultsPage(self)
        self.settings_page = SettingsPage(self)
        self.tabs.addTab(self.results_page, "Results · 结果")
        self.tabs.addTab(self.settings_page, "Settings · 设置")

        cv.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

    def _build_banner(self):
        """Z-902 风格顶部品牌条：软件名 + 当前测试状态。"""
        banner = QWidget()
        banner.setStyleSheet(
            f"background:{BG_PANEL}; border:1px solid {BRAND};"
            "border-radius:8px;")
        bl = QHBoxLayout(banner)
        bl.setContentsMargins(14, 8, 14, 8)

        left = QVBoxLayout()
        left.setSpacing(0)
        title = QLabel(f"{__appname__}  ·  Z-902 Series Compatible")
        title.setStyleSheet(
            f"color:{BRAND}; font-size:17px; font-weight:bold;"
            "background:transparent;")
        sub = QLabel("激光诱导击穿光谱分析 · Analyze / Results / Settings · "
                     "AI 分析图谱")
        sub.setStyleSheet(
            f"color:{TEXT_DIM}; font-size:11px; background:transparent;")
        left.addWidget(title)
        left.addWidget(sub)
        bl.addLayout(left)
        bl.addStretch(1)

        self.lbl_banner_status = QLabel("就绪")
        self.lbl_banner_status.setStyleSheet(
            f"color:{ACCENT}; background:transparent; font-weight:bold;")
        bl.addWidget(self.lbl_banner_status)
        return banner

    def _create_menu(self):
        mb = self.menuBar()
        m_file = mb.addMenu("文件(&F)")
        act_open = m_file.addAction("打开光谱文件…")
        act_open.setShortcut(QKeySequence.Open)
        act_open.triggered.connect(self.open_file)
        m_file.addSeparator()
        act_quit = m_file.addAction("退出")
        act_quit.setShortcut(QKeySequence.Quit)
        act_quit.triggered.connect(self.close)

        m_data = mb.addMenu("数据(&D)")
        act_demo = m_data.addAction("生成演示光谱")
        act_demo.triggered.connect(self.load_demo)
        act_demo_pulses = m_data.addAction("生成演示多脉冲（含无效样例）")
        act_demo_pulses.triggered.connect(self.load_demo_pulses)
        act_pulse_file = m_data.addAction("打开多脉冲文件…")
        act_pulse_file.triggered.connect(self.open_pulse_file)
        act_pulse_folder = m_data.addAction("打开脉冲文件夹…")
        act_pulse_folder.triggered.connect(self.open_pulse_folder)
        act_ana = m_data.addAction("执行分析")
        act_ana.setShortcut("F5")
        act_ana.triggered.connect(self.run_analysis)
        m_data.addSeparator()
        act_pulse_q = m_data.addAction("脉冲质量 · AI 甄别…")
        act_pulse_q.triggered.connect(self.open_pulse_quality)
        act_ai = m_data.addAction("AI 分析图谱…")
        act_ai.triggered.connect(self.open_ai_insight)
        act_quant = m_data.addAction("定量分析（定标曲线）…")
        act_quant.triggered.connect(self.open_quant)
        act_grade = m_data.addAction("合金鉴定 · 牌号匹配…")
        act_grade.triggered.connect(self.open_grade_match)
        act_matrix = m_data.addAction("多次测量平均 · Matrix…")
        act_matrix.triggered.connect(self.open_matrix)
        act_qs = m_data.addAction("QuickSort 快速分拣…")
        act_qs.triggered.connect(self.open_quicksort)

        m_res = mb.addMenu("结果(&R)")
        act_show = m_res.addAction("打开 Results（历史记录）")
        act_show.triggered.connect(lambda: self.tabs.setCurrentIndex(1))
        act_rep = m_res.addAction("导出 HTML 报告…")
        act_rep.triggered.connect(self.export_report)

        m_exp = mb.addMenu("导出(&E)")
        act_png = m_exp.addAction("导出光谱图 PNG…")
        act_png.triggered.connect(self.export_png)
        act_peaks = m_exp.addAction("导出结果 CSV…")
        act_peaks.triggered.connect(self.export_csv)

        m_help = mb.addMenu("帮助(&H)")
        act_about = m_help.addAction("关于")
        act_about.triggered.connect(self.about)

    # ------------------------------------------------------------- 数据加载
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
        self.spectrum = spec
        self._data_file = path
        self.run_analysis()
        self.statusBar().showMessage(f"已加载: {path}", 5000)

    def load_demo(self):
        spec = generate_demo_spectrum()
        self.spectrum = spec
        self.pulse_data = None
        self.btn_pulse.setEnabled(False)
        self._data_file = None
        self.run_analysis()
        self.statusBar().showMessage("已生成演示光谱（模拟 LIBS 信号）", 5000)

    # ------------------------------------------------------------- 多脉冲
    def load_demo_pulses(self):
        """生成演示多脉冲（含饱和/弱信号/噪声/漂移无效样例）并做平均分析。"""
        try:
            pd = generate_demo_pulses()
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "生成失败", str(e))
            return
        self._set_pulse_data(pd, "演示多脉冲（12 个脉冲，含无效样例）")

    def open_pulse_file(self):
        """打开多脉冲文件：第一列波长，其余每列一个脉冲。"""
        path, _ = QFileDialog.getOpenFileName(
            self, "打开多脉冲文件", "",
            "多脉冲文件 (*.txt *.csv *.asc *.dat);;所有文件 (*.*)")
        if not path:
            return
        try:
            pd = load_pulse_series(path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "打开失败", str(e))
            return
        self._set_pulse_data(pd, os.path.basename(path))

    def open_pulse_folder(self):
        """打开脉冲文件夹：目录下每个光谱文件视为一个脉冲。"""
        folder = QFileDialog.getExistingDirectory(
            self, "选择脉冲文件夹（每个文件 = 一个脉冲）")
        if not folder:
            return
        try:
            pd = load_pulse_folder(folder)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "打开失败", str(e))
            return
        self._set_pulse_data(pd, os.path.basename(folder))

    def _set_pulse_data(self, pd, label):
        """载入多脉冲数据：平均谱回填分析流程，原始谱全部保留。"""
        self.pulse_data = pd
        verdicts = analyze_pulses(pd)
        avg, n_valid = average_valid_pulses(pd, verdicts)
        avg.name = f"{label}（平均谱，有效 {n_valid}/{pd.n_pulses}）"
        self.spectrum = avg
        self._data_file = None
        self.btn_pulse.setEnabled(True)
        self.run_analysis()
        n_invalid = sum(1 for v in verdicts
                        if v.level in ("无效", "疑似"))
        self.statusBar().showMessage(
            f"多脉冲已载入：{pd.n_pulses} 个脉冲全部保留；"
            f"AI 甄别 {n_invalid} 个无效/疑似（可点击「脉冲质量 · AI 甄别」"
            "查看原始谱图并手动标记）", 8000)

    def open_pulse_quality(self):
        """打开脉冲质量甄别对话框（查看/标记无效脉冲/重算平均谱）。"""
        if self.pulse_data is None:
            QMessageBox.information(
                self, "提示",
                "请先生成演示多脉冲或打开多脉冲文件。")
            return
        PulseQualityDialog(self).exec_()
        # 对话框内重算平均谱后，保持主窗口与对话框一致
        self.run_analysis()

    # ------------------------------------------------------------- 分析
    def run_analysis(self):
        if self.spectrum is None:
            return
        prom_frac = self.sp_min_prom.value() / 100.0
        min_w = self.sp_min_width.value()
        tol = self.sp_tol.value()

        peaks_idx, self.peaks_info = detect_peaks(
            self.spectrum.wl, self.spectrum.intensity,
            prominence_frac=prom_frac, min_width_pts=min_w)

        suite = BASE_SUITES.get(self.base_metal) if self.base_metal else None
        self.matches = []
        for i, info in enumerate(self.peaks_info):
            cands = match_lines(info["wl"], tol)
            if suite:
                cands = [c for c in cands if c["element"] in suite]
            row = {
                "peak_no": i + 1,
                "wl": info["wl"],
                "intensity": info["intensity"],
                "fwhm_nm": info["fwhm_nm"],
                "element": "", "element_cn": "",
                "line": "", "delta": "", "rel": "",
            }
            if cands:
                top = cands[0]
                row.update({
                    "element": top["element"],
                    "element_cn": top["name"],
                    "line": top["line"],
                    "delta": top["delta"],
                    "rel": top["rel"],
                })
            self.matches.append(row)

        self._fill_table()
        self._plot()
        self._update_info()

        # 自动保存一条测试记录（Z-902 Results）
        rec = self.records.add(
            mode=self.mode,
            base=self.base_metal or "",
            spectrum_name=self.spectrum.name,
            spectrum_path=self._data_file or "",
            n_peaks=len(self.matches),
            operator=self.operator,
            params={"prom": prom_frac, "width": min_w, "tol": tol})
        self.results_page.refresh()
        self.statusBar().showMessage(
            f"分析完成，已记录为测试 #{rec.number}", 4000)

    def _fill_table(self):
        self.table.setRowCount(len(self.matches))
        for i, m in enumerate(self.matches):
            vals = [
                str(m["peak_no"]),
                f"{m['wl']:.3f}",
                f"{m['intensity']:.1f}",
                f"{m['fwhm_nm']:.3f}",
                f"{m['element']} {m['element_cn']}".strip(),
                f"{m['line']:.3f}" if m["line"] != "" else "",
                f"{m['delta']:.3f}" if m["delta"] != "" else "",
                str(m["rel"]) if m["rel"] != "" else "",
            ]
            for j, v in enumerate(vals):
                item = QTableWidgetItem(v)
                if j == 4 and m["element"]:
                    item.setForeground(qcolor(ACCENT))
                self.table.setItem(i, j, item)

    def _plot(self):
        ax = self.ax
        ax.clear()
        wl = self.spectrum.wl
        it = self.spectrum.intensity
        ax.plot(wl, it, lw=0.9, color=BRAND, label="光谱")

        if self.peaks_info and self.cb_annotate.isChecked():
            for info, m in zip(self.peaks_info, self.matches):
                ax.plot(info["wl"], info["intensity"], "v",
                        color=ACCENT, ms=7, zorder=5)
                if m["element"]:
                    ax.annotate(
                        m["element"],
                        xy=(info["wl"], info["intensity"]),
                        xytext=(0, 6), textcoords="offset points",
                        ha="center", fontsize=8, color=ACCENT,
                        bbox=dict(boxstyle="round,pad=0.15",
                                  fc="#101418", ec=BRAND, alpha=0.85,
                                  lw=0.6),
                        zorder=6)

        ax.set_xlabel("波长 (nm)", color=TEXT_DIM)
        ax.set_ylabel("强度 (a.u.)", color=TEXT_DIM)
        ax.set_title(self.spectrum.name, color=TEXT, fontsize=12,
                     fontweight="bold")
        ax.grid(True, alpha=0.35, lw=0.5, color=PLOT_GRID)
        ax.margins(x=0.01)
        ax.tick_params(colors=TEXT_DIM, labelsize=9)
        for s in ax.spines.values():
            s.set_color(PLOT_GRID)
        ax.set_facecolor(PLOT_BG)
        self.fig.tight_layout()
        self.canvas.draw_idle()

    def _update_info(self):
        lo, hi = self.spectrum.wl_range
        n_match = sum(1 for m in self.matches if m["element"])
        self.lbl_info.setText(
            f"{self.spectrum.name}\n"
            f"点数: {self.spectrum.n_points}   范围: {lo:.1f}–{hi:.1f} nm\n"
            f"检测峰: {len(self.matches)}   匹配元素: {n_match}\n"
            f"模式: {self.mode}   操作者: {self.operator or '—'}")
        self.lbl_banner_status.setText(
            f"{len(self.matches)} 峰 / {n_match} 元素匹配 ｜ "
            f"模式 {self.mode} ｜ 基体 {BASES.get(self.base_metal, '全部') if self.base_metal else '全部'}")

    # ------------------------------------------------------------- 应用
    def open_ai_insight(self):
        if self.spectrum is None:
            QMessageBox.information(self, "提示",
                                    "请先生成演示光谱或打开一个光谱文件，"
                                    "再使用 AI 分析图谱。")
            return
        dlg = AIGraphDialog(self, parent=self)
        dlg.exec_()

    def open_quant(self):
        if self.spectrum is None:
            QMessageBox.information(self, "提示",
                                    "请先生成演示光谱或打开一个光谱文件，"
                                    "再进入定量分析。")
            return
        dlg = QuantDialog(self, parent=self)
        dlg.exec_()

    def save_calibration(self, model):
        """保存（或更新）某元素的定标曲线，供合金鉴定使用，并持久化到磁盘。"""
        if model and model.element and model.n_points >= 2:
            try:
                model.ensure_fit()
            except ValueError:
                return
            self.calibrations[model.element] = model
            CalibrationStore(
                os.path.join(self.data_dir, "calibrations.json")).save(
                    self.calibrations)

    def open_grade_match(self):
        if self.spectrum is None:
            QMessageBox.information(self, "提示",
                                    "请先加载或生成一个光谱。")
            return
        dlg = GradeMatchDialog(self, parent=self)
        dlg.exec_()
        # 写回最近一条测试记录的化学/牌号结果（Z-902 Results）
        if dlg.chem:
            grades = [{k: g[k] for k in ("grade", "score", "base", "base_cn")}
                      for g in dlg.grade_results]
            last = self.records.sorted_desc()
            if last:
                self.records.update(last[0].number, chemistry=dlg.chem,
                                    grades=grades, base=self.base_metal or "")
            else:
                self.records.add(mode=self.mode, base=self.base_metal or "",
                                 spectrum_name=self.spectrum.name,
                                 operator=self.operator,
                                 chemistry=dlg.chem, grades=grades)
            self.results_page.refresh()

    def open_matrix(self):
        dlg = MatrixDialog(self, parent=self)
        dlg.exec_()

    def open_quicksort(self):
        dlg = QuickSortDialog(self, parent=self)
        dlg.exec_()
        self.results_page.refresh()

    def _on_base_changed(self):
        data = self.cmb_base.currentData()
        self.base_metal = data
        if self.spectrum is not None:
            self.run_analysis()

    # ------------------------------------------------------------- 结果
    def show_test_detail(self, number):
        rec = self.records.get(number)
        if rec is None:
            return
        self.tabs.setCurrentIndex(0)
        self.statusBar().showMessage(
            f"查看测试 #{rec.number}（{rec.timestamp}）："
            f"{rec.grades[0]['grade'] if rec.grades else '无牌号匹配'}",
            6000)

    # ------------------------------------------------------------- 导出
    def export_png(self):
        if self.spectrum is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出光谱图", "libs_spectrum.png", "PNG 图片 (*.png)")
        if not path:
            return
        self.fig.savefig(path, dpi=200, bbox_inches="tight")
        self.statusBar().showMessage(f"已导出: {path}", 5000)

    def export_csv(self):
        if self.spectrum is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出分析结果", "libs_peaks.csv", "CSV 文件 (*.csv)")
        if not path:
            return
        save_peaks_csv(path, self.matches)
        self.statusBar().showMessage(f"已导出: {path}", 5000)

    def export_report(self):
        """生成 HTML 报告（Test Info + 光谱图 + Chemistry + Grade Match）。"""
        if self.spectrum is None:
            QMessageBox.information(self, "提示", "请先加载或生成一个光谱。")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 HTML 报告",
            os.path.join(self.data_dir, "reports", f"report_{self.records.next_number()}.html"),
            "HTML 文件 (*.html)")
        if not path:
            return
        # 保存当前光谱图为 PNG（供报告内嵌）
        png_path = os.path.join(self.data_dir, "reports",
                                f"spectrum_{self.records.next_number()}.png")
        os.makedirs(os.path.dirname(png_path), exist_ok=True)
        self.fig.savefig(png_path, dpi=150, bbox_inches="tight")

        last = self.records.sorted_desc()
        rec = last[0] if last else None
        info_lines = [
            ("测试编号", f"#{rec.number}" if rec else "—"),
            ("时间", rec.timestamp if rec else "—"),
            ("模式", rec.mode if rec else self.mode),
            ("光谱", self.spectrum.name),
            ("操作者", self.operator or "—"),
            ("基体", BASES.get(self.base_metal, "全部") if self.base_metal else "全部"),
            ("检测峰数", str(len(self.matches))),
        ]
        chem = rec.chemistry if rec else None
        grades = rec.grades if rec else None
        from .test_records import calc_ce
        ce = calc_ce(chem) if chem else None
        build_html_report(path, self.spectrum.name, info_lines,
                          spectrum_png=png_path, chemistry=chem,
                          grades=grades, ce=ce)
        QMessageBox.information(self, "已导出",
                                f"HTML 报告已保存：\n{path}\n\n"
                                "用浏览器打开即可查看/打印。")

    # ------------------------------------------------------------- 其他
    def about(self):
        QMessageBox.about(
            self, "关于",
            f"<b>{__appname__}</b> v{__version__}<br><br>"
            "激光诱导击穿光谱（LIBS）数据查看与定性/定量分析软件，"
            "功能参照 SciAps Z-902 手持 LIBS 分析仪软件：<br>"
            "· Analyze：光谱 / 峰检测 / 元素匹配 / 定量定标 / "
            "合金鉴定(Grade Match) / Matrix / QuickSort / AI 分析图谱<br>"
            "· Results：测试历史 / 牌号结果 / CE 碳当量 / 样品照片 / 平均化<br>"
            "· Settings：操作者 / ND 规则 / 牌号库管理 / 方法(Profile)<br><br>"
            "AI 分析图谱：本地规则引擎对元素匹配做置信度评分、"
            "材料/基体推断并输出关系图谱，辅助未知样品快速判读。<br><br>"
            "内置常用元素特征谱线库（NIST 强线）与常见合金牌号库。"
            "谱线强度与牌号组成为参考值，正式判定请以权威标准为准。")


def run_app():
    app = QApplication.instance() or QApplication([])
    app.setApplicationName(__appname__)
    app.setStyleSheet(Z902_QSS)
    win = MainWindow()
    win.show()
    return app, win


def main():
    app, win = run_app()
    rc = app.exec_()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
