# -*- coding: utf-8 -*-

# Copyright (C) 2026 Libs通用测试软件 作者
# SPDX-License-Identifier: GPL-3.0-or-later
#
# 本软件是自由软件：你可以依据 GNU 通用公共许可证（GPL v3 或更新版本）
# 的条款再分发和/或修改它。详见项目根目录 LICENSE 文件。
#
# 本软件按“现状”分发，不附带任何明示或默示担保；
# 详情请参阅 GNU GPL v3：<https://www.gnu.org/licenses/>。

"""合金牌号匹配（Grade Match）单元测试。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs_analyzer.grade_library import match_grades, grade_penalty, BASES  # noqa: E402


class TestGradePenalty(unittest.TestCase):
    def test_in_range(self):
        self.assertEqual(grade_penalty(16.5, 16.0, 18.0), 0.0)

    def test_below(self):
        self.assertAlmostEqual(grade_penalty(8.0, 10.0, 14.0), 20.0, delta=1e-6)

    def test_above(self):
        self.assertAlmostEqual(grade_penalty(15.0, 10.0, 14.0), 7.142857, delta=1e-3)

    def test_zero_measured_required(self):
        self.assertEqual(grade_penalty(0.0, 2.0, 3.0), 100.0)
        self.assertEqual(grade_penalty(0.0, 0.0, 2.0), 0.0)


class TestGradeMatch(unittest.TestCase):
    def test_304_chemistry(self):
        chem = {"Fe": (68.0, 2.0), "Cr": (18.5, 0.5), "Ni": (9.0, 0.4),
                "Mn": (1.5, 0.2), "Si": (0.5, 0.1)}
        res = match_grades(chem, top_n=3)
        self.assertEqual(res[0]["grade"], "304")
        self.assertGreater(res[0]["score"], 95)

    def test_316_chemistry(self):
        chem = {"Fe": (66.0, 2.0), "Cr": (16.5, 0.5), "Ni": (11.0, 0.4),
                "Mo": (2.5, 0.3), "Mn": (1.5, 0.2)}
        res = match_grades(chem, top_n=3)
        self.assertEqual(res[0]["grade"], "316")
        self.assertGreater(res[0]["score"], 95)

    def test_304_vs_316_distinguish(self):
        # 无 Mo 的 304 组成不应被匹配成 316
        chem = {"Fe": (68.0, 2.0), "Cr": (18.5, 0.5), "Ni": (9.0, 0.4),
                "Mn": (1.5, 0.2), "Si": (0.5, 0.1)}
        res = match_grades(chem, top_n=8)
        s304 = next(r for r in res if r["grade"] == "304")["score"]
        s316 = next(r for r in res if r["grade"] == "316")["score"]
        self.assertGreater(s304, s316)

    def test_6061_aluminum(self):
        chem = {"Al": (97.5, 1.0), "Mg": (1.0, 0.2), "Si": (0.6, 0.1),
                "Cu": (0.3, 0.1), "Cr": (0.2, 0.05), "Fe": (0.4, 0.1)}
        res = match_grades(chem, bases=["aluminum"], top_n=3)
        self.assertEqual(res[0]["grade"], "6061")
        self.assertGreater(res[0]["score"], 90)

    def test_wrong_grade_low_score(self):
        # 用 6061 铝组成去匹配不锈钢，分数应很低
        chem = {"Al": (97.5, 1.0), "Mg": (1.0, 0.2), "Si": (0.6, 0.1)}
        res = match_grades(chem, bases=["stainless"], top_n=3)
        self.assertLess(res[0]["score"], 60)

    def test_base_filter(self):
        chem = {"Fe": (68.0, 2.0), "Cr": (18.5, 0.5), "Ni": (9.0, 0.4)}
        res = match_grades(chem, bases=["aluminum"], top_n=5)
        # 铝基体里没有 Fe 基牌号规格（1100 等用 Al/Cu/Mn...），分数会低
        self.assertTrue(all(r["base"] == "aluminum" for r in res))


if __name__ == "__main__":
    unittest.main(verbosity=2)
