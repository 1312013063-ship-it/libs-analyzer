# -*- coding: utf-8 -*-

# Copyright (C) 2026 Libs通用测试软件 作者
# SPDX-License-Identifier: GPL-3.0-or-later
#
# 本软件是自由软件：你可以依据 GNU 通用公共许可证（GPL v3 或更新版本）
# 的条款再分发和/或修改它。详见项目根目录 LICENSE 文件。
#
# 本软件按“现状”分发，不附带任何明示或默示担保；
# 详情请参阅 GNU GPL v3：<https://www.gnu.org/licenses/>。

"""测试记录系统 / CE 碳当量 / 平均化 / 用户牌号解析 单元测试。"""
import os
import sys
import tempfile
import unittest
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs_analyzer.test_records import (  # noqa: E402
    TestRecord, RecordsStore, calc_ce, average_records, now_iso,
)
from libs_analyzer.grade_library import (  # noqa: E402
    parse_grade_specs, save_user_grades, load_user_grades, match_grades,
)


class TestRecordsStore(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.gettempdir(), "libs_test_records.json")
        if os.path.exists(self.path):
            os.remove(self.path)

    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_add_and_numbering(self):
        s = RecordsStore(self.path)
        r1 = s.add(mode="Alloy", spectrum_name="A", operator="张三")
        r2 = s.add(mode="QuickSort", spectrum_name="B")
        self.assertEqual(r1.number, 1)
        self.assertEqual(r2.number, 2)
        self.assertEqual(len(s.records), 2)

    def test_persistence(self):
        s = RecordsStore(self.path)
        s.add(mode="Alloy", spectrum_name="A",
              chemistry={"Fe": {"conc": 66.0, "se": 2.0, "source": "定标"}})
        s2 = RecordsStore(self.path)
        self.assertEqual(len(s2.records), 1)
        self.assertEqual(s2.records[0].chemistry["Fe"]["conc"], 66.0)

    def test_update_and_delete(self):
        s = RecordsStore(self.path)
        r = s.add(mode="Alloy")
        s.update(r.number, grades=[{"grade": "316", "score": 96.0}])
        self.assertEqual(s.get(r.number).grades[0]["grade"], "316")
        s.delete([r.number])
        self.assertEqual(len(s.records), 0)


class TestCE(unittest.TestCase):
    def test_iiw_ce(self):
        chem = {"Fe": {"conc": 94.0}, "C": {"conc": 0.30},
                "Mn": {"conc": 1.2}, "Cr": {"conc": 0.8},
                "Mo": {"conc": 0.2}, "V": {"conc": 0.05},
                "Ni": {"conc": 0.3}, "Cu": {"conc": 0.3}}
        ce = calc_ce(chem)
        self.assertIsNotNone(ce)
        # CE = 0.30 + 1.2/6 + (0.8+0.2+0.05)/5 + (0.3+0.3)/15
        expect = 0.30 + 0.2 + 0.21 + 0.04
        self.assertAlmostEqual(ce["value"], expect, delta=1e-6)
        self.assertEqual(ce["formula"], "IIW")

    def test_ce_requires_carbon(self):
        chem = {"Fe": {"conc": 95.0}, "Cr": {"conc": 1.0}}
        self.assertIsNone(calc_ce(chem))

    def test_ce_requires_iron_base(self):
        chem = {"Al": {"conc": 97.0}, "C": {"conc": 0.3}}
        self.assertIsNone(calc_ce(chem))


class TestAverage(unittest.TestCase):
    def test_average_records(self):
        recs = [
            TestRecord(number=1, timestamp="t",
                       chemistry={"Fe": {"conc": 66.0, "se": 2.0, "source": "a"}}),
            TestRecord(number=2, timestamp="t",
                       chemistry={"Fe": {"conc": 68.0, "se": 1.0, "source": "a"}}),
        ]
        chem, n = average_records(recs)
        self.assertEqual(n, 2)
        self.assertAlmostEqual(chem["Fe"]["conc"], 67.0)
        self.assertAlmostEqual(chem["Fe"]["se"], 1.5)

    def test_average_skips_empty(self):
        recs = [TestRecord(number=1, timestamp="t", chemistry={}),
                TestRecord(number=2, timestamp="t", chemistry={})]
        chem, n = average_records(recs)
        self.assertEqual(chem, {})
        self.assertEqual(n, 0)


class TestUserGrades(unittest.TestCase):
    def test_parse_specs(self):
        specs = parse_grade_specs("Cr:16-18;Ni:8-10.5;Mo:2-3", base_el="Fe")
        self.assertEqual(specs["Cr"], (16.0, 18.0))
        self.assertEqual(specs["Ni"], (8.0, 10.5))
        self.assertEqual(specs["base"], "Fe")

    def test_save_load_roundtrip(self):
        path = os.path.join(tempfile.gettempdir(), "libs_test_grades.json")
        if os.path.exists(path):
            os.remove(path)
        grades = {"steel": {"MY-500": {"base": "Fe",
                                       "Cr": (1.0, 2.0), "Mo": (0.3, 0.6)}}}
        save_user_grades(path, grades)
        loaded = load_user_grades(path)
        self.assertEqual(loaded["steel"]["MY-500"]["Cr"], (1.0, 2.0))
        # 用户牌号参与匹配
        # 补充 Mn/Si 浓度，使 A36/1010 等牌号因 Mn 超上限而扣分
        chem = {"Fe": (95.2, 1.0), "Cr": (1.5, 0.2), "Mo": (0.45, 0.1),
                "Mn": (1.8, 0.2), "Si": (0.5, 0.1)}
        res = match_grades(chem, bases=["steel"], top_n=3, extra_grades=loaded)
        self.assertEqual(res[0]["grade"], "MY-500")
        os.remove(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
