# -*- coding: utf-8 -*-

# Copyright (C) 2026 Libs通用测试软件 作者
# SPDX-License-Identifier: GPL-3.0-or-later
#
# 本软件是自由软件：你可以依据 GNU 通用公共许可证（GPL v3 或更新版本）
# 的条款再分发和/或修改它。详见项目根目录 LICENSE 文件。
#
# 本软件按“现状”分发，不附带任何明示或默示担保；
# 详情请参阅 GNU GPL v3：<https://www.gnu.org/licenses/>。

"""定量分析（定标曲线）单元测试。"""
import json
import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs_analyzer.quant import CalibrationModel, CalibrationStore  # noqa: E402


class TestCalibration(unittest.TestCase):
    def _linear_points(self, slope=100.0, intercept=50.0, cs=(0.1, 0.5, 1.0, 2.0, 5.0),
                       noise=0.0, seed=0):
        rng = np.random.default_rng(seed)
        model = CalibrationModel(element="Fe", line_nm=373.49, unit="wt%")
        for c in cs:
            i = slope * c + intercept + (rng.normal(0, noise) if noise else 0.0)
            model.add_point(c, i, label=f"S{c}")
        return model, slope, intercept

    def test_fit_recovers_params(self):
        m, slope, intercept = self._linear_points()
        f = m.fit()
        self.assertAlmostEqual(f["slope"], slope, delta=1e-6)
        self.assertAlmostEqual(f["intercept"], intercept, delta=1e-6)
        self.assertAlmostEqual(f["r2"], 1.0, delta=1e-9)
        self.assertEqual(f["n"], 5)

    def test_predict_recovers_concentration(self):
        m, slope, intercept = self._linear_points()
        m.fit()
        for c in (0.3, 1.8, 4.2):
            i = slope * c + intercept
            c_pred, se = m.predict(i)
            self.assertAlmostEqual(c_pred, c, delta=1e-6)
            self.assertGreaterEqual(se, 0.0)

    def test_insufficient_points(self):
        m = CalibrationModel(element="Na", line_nm=588.99)
        m.add_point(1.0, 100.0)
        with self.assertRaises(ValueError):
            m.fit()
        with self.assertRaises(ValueError):
            m.predict(120.0)

    def test_clear(self):
        m, _, _ = self._linear_points()
        m.clear()
        self.assertEqual(m.n_points, 0)

    def test_to_csv_rows(self):
        m, _, _ = self._linear_points(cs=(0.5, 1.0))
        m.fit()
        rows = m.to_csv_rows()
        # 头1 + 标准样2 + slope + intercept + r2 = 6 行
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0][0], "type")
        self.assertEqual(rows[3][0], "fit_slope")


class TestCalibrationPersistence(unittest.TestCase):
    """定标序列化与持久化（新功能：跨会话保存/加载）。"""

    def test_roundtrip(self):
        m = CalibrationModel(element="Fe", line_nm=373.49, unit="wt%")
        m.add_point(0.5, 100.0, label="S1")
        m.add_point(1.0, 150.0, label="S2")
        m.add_point(2.0, 250.0, label="S3")
        d = m.to_dict()
        m2 = CalibrationModel.from_dict(d)
        self.assertEqual(m2.element, "Fe")
        self.assertEqual(m2.line_nm, 373.49)
        self.assertEqual(m2.unit, "wt%")
        self.assertEqual(m2.n_points, 3)
        m2.fit()
        f1, f2 = m.ensure_fit(), m2.ensure_fit()
        self.assertAlmostEqual(f1["slope"], f2["slope"], delta=1e-9)
        self.assertAlmostEqual(f1["intercept"], f2["intercept"], delta=1e-9)

    def test_store_save_load(self):
        path = os.path.join(tempfile.gettempdir(), "libs_test_calibrations.json")
        if os.path.exists(path):
            os.remove(path)
        store = CalibrationStore(path)
        m = CalibrationModel(element="Cr", line_nm=425.43, unit="wt%")
        m.add_point(1.0, 200.0, label="S1")
        m.add_point(2.0, 300.0, label="S2")
        store.save({"Cr": m})
        loaded = CalibrationStore(path).load()
        self.assertIn("Cr", loaded)
        self.assertEqual(loaded["Cr"].n_points, 2)
        c_pred, _ = loaded["Cr"].predict(250.0)
        self.assertAlmostEqual(c_pred, 1.5, delta=1e-6)
        os.remove(path)

    def test_store_load_missing_ok(self):
        path = os.path.join(tempfile.gettempdir(), "libs_missing_cal.json")
        if os.path.exists(path):
            os.remove(path)
        self.assertEqual(CalibrationStore(path).load(), {})

    def test_store_skips_bad_entries(self):
        path = os.path.join(tempfile.gettempdir(), "libs_bad_cal.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"Fe": {"element": "Fe", "points": []}}, f)
        self.assertEqual(CalibrationStore(path).load(), {})
        os.remove(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
