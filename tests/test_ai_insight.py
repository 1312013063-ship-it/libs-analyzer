# -*- coding: utf-8 -*-

# Copyright (C) 2026 Libs通用测试软件 作者
# SPDX-License-Identifier: GPL-3.0-or-later
#
# 本软件是自由软件：你可以依据 GNU 通用公共许可证（GPL v3 或更新版本）
# 的条款再分发和/或修改它。详见项目根目录 LICENSE 文件。
#
# 本软件按“现状”分发，不附带任何明示或默示担保；
# 详情请参阅 GNU GPL v3：<https://www.gnu.org/licenses/>。

"""AI 分析图谱引擎单元测试（置信度评分 / 材料推断 / 图谱生成）。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs_analyzer.ai_insight import (  # noqa: E402
    analyze_elements, infer_materials, build_summary, analyze_insight,
    build_insight_figure, confidence_level,
)
from libs_analyzer.demo_data import generate_demo_spectrum  # noqa: E402
from libs_analyzer.peak_detect import detect_peaks  # noqa: E402
from libs_analyzer.element_lines import match_lines  # noqa: E402


def _matches_from_spectrum(spec, prom=0.03, width=2, tol=0.3):
    """用真实检测流程构造 matches，模拟主窗口 run_analysis。"""
    peaks_idx, peaks_info = detect_peaks(
        spec.wl, spec.intensity, prominence_frac=prom,
        min_width_pts=width)
    matches = []
    for i, info in enumerate(peaks_info):
        cands = match_lines(info["wl"], tol)
        row = {"peak_no": i + 1, "wl": info["wl"],
               "intensity": info["intensity"],
               "fwhm_nm": info["fwhm_nm"],
               "element": "", "element_cn": "", "line": "",
               "delta": "", "rel": ""}
        if cands:
            top = cands[0]
            row.update({"element": top["element"],
                        "element_cn": top["name"],
                        "line": top["line"],
                        "delta": top["delta"], "rel": top["rel"]})
        matches.append(row)
    return matches


class TestConfidence(unittest.TestCase):
    def test_level_boundaries(self):
        self.assertEqual(confidence_level(0.80), "确认")
        self.assertEqual(confidence_level(0.60), "较强")
        self.assertEqual(confidence_level(0.40), "疑似")
        self.assertEqual(confidence_level(0.10), "弱")

    def test_delta_scoring(self):
        # 偏差越小置信度越高
        els = analyze_elements([
            {"element": "Fe", "wl": 371.99, "delta": 0.01, "rel": 85,
             "intensity": 5000},
            {"element": "Fe", "wl": 373.49, "delta": 0.02, "rel": 90,
             "intensity": 4500},
        ])
        self.assertEqual(len(els), 1)
        self.assertGreater(els[0].confidence, 0.7)   # 多线 + 小偏差
        self.assertEqual(els[0].n_lines, 2)

    def test_poor_delta_low_confidence(self):
        els = analyze_elements([
            {"element": "Si", "wl": 288.16, "delta": 0.28, "rel": 100,
             "intensity": 1000},
        ])
        self.assertEqual(len(els), 1)
        self.assertLess(els[0].confidence, 0.3)       # 大偏差 -> 弱

    def test_calibration_concentration(self):
        from libs_analyzer.quant import CalibrationModel
        m = CalibrationModel(element="Cr", line_nm=357.87)
        m.add_point(1.0, 1000.0)
        m.add_point(5.0, 5000.0)
        m.add_point(10.0, 10000.0)
        els = analyze_elements([
            {"element": "Cr", "wl": 357.87, "delta": 0.01, "rel": 100,
             "intensity": 5000.0},
        ], calibrations={"Cr": m})
        self.assertEqual(len(els), 1)
        self.assertIsNotNone(els[0].conc)
        self.assertAlmostEqual(els[0].conc, 5.0, delta=0.5)


class TestMaterial(unittest.TestCase):
    def test_stainless_steel(self):
        els = analyze_elements([
            {"element": "Fe", "wl": 371.99, "delta": 0.01, "rel": 85,
             "intensity": 9000},
            {"element": "Cr", "wl": 357.87, "delta": 0.01, "rel": 100,
             "intensity": 6000},
            {"element": "Ni", "wl": 341.48, "delta": 0.01, "rel": 100,
             "intensity": 5000},
        ])
        mats = infer_materials(els)
        self.assertTrue(mats)
        self.assertEqual(mats[0].name, "Stainless Steel")
        self.assertGreaterEqual(mats[0].confidence, 0.6)

    def test_aluminum_alloy(self):
        els = analyze_elements([
            {"element": "Al", "wl": 396.15, "delta": 0.01, "rel": 95,
             "intensity": 9000},
            {"element": "Mg", "wl": 285.21, "delta": 0.01, "rel": 90,
             "intensity": 3000},
            {"element": "Si", "wl": 288.16, "delta": 0.01, "rel": 100,
             "intensity": 2500},
        ])
        mats = infer_materials(els)
        self.assertTrue(mats)
        self.assertEqual(mats[0].name, "Aluminum Alloy")

    def test_base_preference(self):
        els = analyze_elements([
            {"element": "Fe", "wl": 371.99, "delta": 0.01, "rel": 85,
             "intensity": 9000},
            {"element": "Cr", "wl": 357.87, "delta": 0.01, "rel": 100,
             "intensity": 6000},
            {"element": "Ni", "wl": 341.48, "delta": 0.01, "rel": 100,
             "intensity": 5000},
            {"element": "Cu", "wl": 324.75, "delta": 0.01, "rel": 100,
             "intensity": 7000},
        ])
        mats = infer_materials(els, base="Cu")
        self.assertEqual(mats[0].elements[0], "Cu")   # 基体优先置顶


class TestInsightPipeline(unittest.TestCase):
    def test_demo_spectrum_pipeline(self):
        spec = generate_demo_spectrum()
        matches = _matches_from_spectrum(spec)
        self.assertTrue(matches)
        ins = analyze_insight(matches, spec)
        self.assertIsNotNone(ins.summary)
        self.assertGreaterEqual(len(ins.elements), 1)
        # 解读文本应含关键段落
        self.assertTrue(any(k in ins.summary for k in
                            ("材料推断", "主要成分")))

    def test_empty_matches(self):
        ins = analyze_insight([], generate_demo_spectrum())
        self.assertEqual(len(ins.elements), 0)
        self.assertIn("未匹配", ins.summary)

    def test_figure_generation(self):
        spec = generate_demo_spectrum()
        matches = _matches_from_spectrum(spec)
        ins = analyze_insight(matches, spec)
        fig = build_insight_figure(ins)
        self.assertIsNotNone(fig)
        self.assertEqual(len(fig.axes), 2)            # 网络 + 条形
        import matplotlib
        self.assertEqual(fig.patch.get_facecolor()[:3],
                         (0.06274509803921569, 0.0784313725490196,
                          0.09411764705882353))       # #101418
        fig.savefig(os.path.join(
            os.path.dirname(__file__), "..", "_selfcheck",
            "smoke_ai_graph.png"), dpi=80)


class TestSummaryText(unittest.TestCase):
    def test_env_warning(self):
        els = analyze_elements([
            {"element": "Ar", "wl": 763.51, "delta": 0.01, "rel": 100,
             "intensity": 8000},
        ])
        summary = build_summary(els, infer_materials(els))
        self.assertIn("环境元素", summary)
        self.assertIn("Ar", summary)


if __name__ == "__main__":
    unittest.main()
