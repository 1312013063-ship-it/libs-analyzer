# -*- coding: utf-8 -*-

# Copyright (C) 2026 Libs通用测试软件 作者
# SPDX-License-Identifier: GPL-3.0-or-later
#
# 本软件是自由软件：你可以依据 GNU 通用公共许可证（GPL v3 或更新版本）
# 的条款再分发和/或修改它。详见项目根目录 LICENSE 文件。
#
# 本软件按“现状”分发，不附带任何明示或默示担保；
# 详情请参阅 GNU GPL v3：<https://www.gnu.org/licenses/>。

"""AI 无效脉冲识别引擎单元测试。"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs_analyzer.pulse_quality import (  # noqa: E402
    PulseData, analyze_pulses, average_valid_pulses, pulse_summary,
    PulseVerdict,
)
from libs_analyzer.demo_data import generate_demo_pulses  # noqa: E402


def _make_base_pulses(n=8, wl=None):
    """构造一组正常脉冲（与演示数据同构）。"""
    if wl is None:
        wl = np.arange(200.0, 900.1, 0.5)
    rng = np.random.default_rng(7)
    mat = []
    for _ in range(n):
        base = 300.0 + 200.0 * np.exp(-((wl - 660.0) ** 2) / (2 * 180.0 ** 2))
        y = base.copy()
        for lw, amp in ((373.49, 8000.0), (393.37, 9000.0),
                        (588.99, 7000.0), (766.49, 5000.0)):
            sigma = 0.4 / (2 * np.sqrt(2 * np.log(2)))
            y += amp * np.exp(-((wl - lw) ** 2) / (2 * sigma ** 2))
        y += rng.normal(0, 15, y.shape)
        mat.append(np.maximum(y, 0))
    return np.array(mat)


class TestPulseData(unittest.TestCase):
    def test_construct_and_names(self):
        pd = PulseData(np.arange(5.0), np.zeros((3, 5)))
        self.assertEqual(pd.n_pulses, 3)
        self.assertEqual(pd.names, ["P1", "P2", "P3"])
        self.assertEqual(len(pd.wl), 5)

    def test_auto_names_fill(self):
        pd = PulseData(np.arange(5.0), np.zeros((2, 5)),
                       names=["A"])
        self.assertEqual(len(pd.names), 2)


class TestAnalyze(unittest.TestCase):
    def test_good_pulses_all_valid(self):
        mat = _make_base_pulses()
        pd = PulseData(np.arange(200.0, 900.1, 0.5), mat)
        vs = analyze_pulses(pd)
        self.assertEqual(len(vs), 8)
        for v in vs:
            self.assertEqual(v.level, "有效", f"{v.name}: {v.issues}")
            self.assertGreaterEqual(v.score, 70)

    def test_saturated_pulse(self):
        wl = np.arange(200.0, 900.1, 0.5)
        mat = _make_base_pulses(wl=wl)
        mat[3] = mat[3].copy()
        mat[3][mat[3] > 1000] = 65000.0          # 强制饱和
        pd = PulseData(wl, mat)
        vs = analyze_pulses(pd)
        sat = vs[3]
        self.assertIn("饱和", "".join(r for r, _ in sat.issues))
        self.assertEqual(sat.level, "无效")
        self.assertLessEqual(sat.score, 60)

    def test_weak_pulse(self):
        wl = np.arange(200.0, 900.1, 0.5)
        mat = _make_base_pulses(wl=wl)
        mat[1] = mat[1] * 0.05                   # 弱信号
        pd = PulseData(wl, mat)
        vs = analyze_pulses(pd)
        self.assertIn("弱信号", "".join(r for r, _ in vs[1].issues))
        self.assertEqual(vs[1].level, "无效")

    def test_noisy_pulse(self):
        wl = np.arange(200.0, 900.1, 0.5)
        mat = _make_base_pulses(wl=wl)
        mat[5] = mat[5] + np.random.default_rng(3).normal(
            0, 1200, mat[5].shape)               # 高噪声
        pd = PulseData(wl, mat)
        vs = analyze_pulses(pd)
        self.assertIn("噪声", "".join(r for r, _ in vs[5].issues))
        self.assertNotEqual(vs[5].level, "有效")

    def test_anomalous_pulse(self):
        wl = np.arange(200.0, 900.1, 0.5)
        mat = _make_base_pulses(wl=wl)
        mat[2] = np.nan * mat[2]                 # NaN 异常
        pd = PulseData(wl, mat)
        vs = analyze_pulses(pd)
        self.assertEqual(vs[2].level, "无效")
        self.assertEqual(vs[2].score, 0.0)

    def test_inconsistent_pulse(self):
        wl = np.arange(200.0, 900.1, 0.5)
        mat = _make_base_pulses(wl=wl)
        mat[6] = 200.0 + np.random.default_rng(1).normal(
            0, 400, mat[6].shape)                # 无特征峰，纯噪声
        pd = PulseData(wl, mat)
        vs = analyze_pulses(pd)
        self.assertNotEqual(vs[6].level, "有效")

    def test_user_mark_overrides(self):
        wl = np.arange(200.0, 900.1, 0.5)
        mat = _make_base_pulses(wl=wl)
        pd = PulseData(wl, mat)
        vs = analyze_pulses(pd)
        # 用户强制标记一个有效脉冲为无效 → 排除
        vs[0].user_mark = "invalid"
        self.assertFalse(vs[0].effective_valid)
        # 用户强制标记一个无效脉冲为有效 → 保留
        mat2 = mat.copy()
        mat2[1] = mat2[1] * 0.05
        pd2 = PulseData(wl, mat2)
        vs2 = analyze_pulses(pd2)
        self.assertEqual(vs2[1].level, "无效")
        vs2[1].user_mark = "valid"
        self.assertTrue(vs2[1].effective_valid)


class TestAverage(unittest.TestCase):
    def test_average_excludes_invalid(self):
        wl = np.arange(200.0, 900.1, 0.5)
        mat = _make_base_pulses(wl=wl)
        mat[3] = 65000.0 * np.ones_like(mat[3])   # 饱和
        mat[4] = mat[4] * 0.02                    # 弱
        pd = PulseData(wl, mat)
        vs = analyze_pulses(pd)
        valid_n = sum(1 for v in vs if v.effective_valid)
        avg, n = average_valid_pulses(pd, vs)
        self.assertEqual(n, valid_n)
        self.assertEqual(len(avg.wl), len(wl))
        self.assertLess(avg.intensity.max(), 15000)  # 排除饱和后不再削顶

    def test_all_invalid_fallback(self):
        wl = np.arange(200.0, 900.1, 0.5)
        mat = np.full((3, len(wl)), 65000.0)      # 全部饱和
        pd = PulseData(wl, mat)
        vs = analyze_pulses(pd)
        self.assertTrue(all(v.level == "无效" for v in vs))
        avg, n = average_valid_pulses(pd, vs)     # 退化中位数谱，不崩溃
        self.assertEqual(n, 0)                    # 0 个有效，仍返回可用谱
        self.assertEqual(len(avg.wl), len(wl))
        self.assertTrue(np.all(np.isfinite(avg.intensity)))

    def test_summary_text(self):
        pd = generate_demo_pulses()
        vs = analyze_pulses(pd)
        txt = pulse_summary(vs)
        self.assertIn("共", txt)
        self.assertIn("脉冲", txt)


class TestDemoPulses(unittest.TestCase):
    def test_demo_contains_invalid(self):
        pd = generate_demo_pulses()
        self.assertGreaterEqual(pd.n_pulses, 10)
        vs = analyze_pulses(pd)
        levels = {v.level for v in vs}
        self.assertIn("无效", levels)             # 演示数据故意含无效脉冲
        self.assertIn("有效", levels)


if __name__ == "__main__":
    unittest.main()
