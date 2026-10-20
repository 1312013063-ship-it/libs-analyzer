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
核心逻辑自检（无需 GUI）：数据加载、峰值检测、元素匹配、演示数据生成。
运行: python -m unittest discover -s tests -v
"""
import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs_analyzer.data_io import load_spectrum, save_spectrum_csv  # noqa: E402
from libs_analyzer.peak_detect import detect_peaks  # noqa: E402
from libs_analyzer.element_lines import match_lines  # noqa: E402
from libs_analyzer.demo_data import generate_demo_spectrum  # noqa: E402


class TestDataIO(unittest.TestCase):
    def _write(self, text, suffix):
        fd, path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_csv_with_header_comma(self):
        p = self._write("wavelength,intensity\n200,100\n201,110\n202,120\n", ".csv")
        spec = load_spectrum(p)
        self.assertEqual(spec.n_points, 3)
        np.testing.assert_allclose(spec.wl, [200, 201, 202])
        np.testing.assert_allclose(spec.intensity, [100, 110, 120])
        os.remove(p)

    def test_txt_space_separated_unsorted(self):
        p = self._write("300.5 50\n299.0 40\n301.0 60\n", ".txt")
        spec = load_spectrum(p)
        self.assertEqual(spec.n_points, 3)
        # 应按波长排序
        np.testing.assert_allclose(spec.wl, [299.0, 300.5, 301.0])
        os.remove(p)

    def test_save_roundtrip(self):
        wl = np.arange(200, 205, 1.0)
        it = np.arange(5, dtype=float)
        tmp = os.path.join(tempfile.gettempdir(), "libs_rt.csv")
        save_spectrum_csv(tmp, type("S", (), {"wl": wl, "intensity": it})())
        spec = load_spectrum(tmp)
        self.assertEqual(spec.n_points, 5)
        np.testing.assert_allclose(spec.intensity, it)
        os.remove(tmp)


class TestPeakDetect(unittest.TestCase):
    def test_known_peaks(self):
        wl = np.arange(380.0, 430.0, 0.05)
        base = 10.0 * np.ones_like(wl)
        for center in (393.37, 405.78, 422.67):
            base += 500.0 * np.exp(-((wl - center) ** 2) / (2 * 0.1 ** 2))
        rng = np.random.default_rng(1)
        base += rng.normal(0, 0.8, wl.shape)
        peaks, info = detect_peaks(wl, base, prominence_frac=0.01, min_width_pts=3)
        got = sorted(round(p["wl"], 2) for p in info)
        self.assertEqual(len(got), 3)
        for expect in (393.37, 405.78, 422.67):
            self.assertTrue(any(abs(g - expect) < 0.1 for g in got),
                            f"未检出峰 {expect}，实际 {got}")


class TestElementMatch(unittest.TestCase):
    def test_match_known(self):
        c = match_lines(373.49, 0.3)
        self.assertTrue(any(x["element"] == "Fe" for x in c))
        self.assertEqual(c[0]["element"], "Fe")

    def test_match_na(self):
        c = match_lines(588.99, 0.3)
        self.assertEqual(c[0]["element"], "Na")

    def test_no_match(self):
        c = match_lines(450.12, 0.1)
        self.assertEqual(c, [])


class TestDemoData(unittest.TestCase):
    def test_generate(self):
        spec = generate_demo_spectrum(seed=7)
        self.assertEqual(spec.n_points, int((900 - 200) / 0.1) + 1)
        self.assertGreater(spec.intensity.max(), 5000)
        peaks, info = detect_peaks(spec.wl, spec.intensity,
                                   prominence_frac=0.01, min_width_pts=3)
        self.assertGreater(len(info), 20)
        self.assertGreater(spec.intensity.min(), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
