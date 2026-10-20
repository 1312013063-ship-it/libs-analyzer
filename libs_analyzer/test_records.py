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
测试记录系统（参照 SciAps Z-902 Results）：
- TestRecord：一次测试的完整信息（编号/时间/模式/参数/化学/牌号/照片）
- RecordsStore：JSON 持久化（data/records.json）
- calc_ce：碳当量（IIW 公式）
- average_records：多次测试平均（Analysis Averaging）
"""
import json
import os
import datetime
from dataclasses import dataclass, field, asdict


@dataclass
class TestRecord:
    number: int
    timestamp: str
    mode: str = "Alloy"          # Alloy / QuickSort / AVG
    base: str = ""               # 基体 key
    spectrum_name: str = ""
    spectrum_path: str = ""
    n_peaks: int = 0
    operator: str = ""
    params: dict = field(default_factory=dict)
    chemistry: dict = field(default_factory=dict)   # {el: {"conc","se","source"}}
    grades: list = field(default_factory=list)      # [{"grade","score","base","base_cn"}]
    photo_path: str = ""
    is_avg: bool = False

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d):
        return TestRecord(**{k: v for k, v in d.items() if k in
                             TestRecord.__dataclass_fields__})

    @property
    def date_str(self):
        try:
            return self.timestamp[:10]
        except Exception:
            return ""


def now_iso():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def calc_ce(chem):
    """
    碳当量 CE（IIW 公式）：
        CE = C + Mn/6 + (Cr + Mo + V)/5 + (Ni + Cu)/15
    仅当化学中含 C 且铁基（Fe 浓度最高）时计算。
    chem: {el: {"conc":..., ...}} 或 {el: (conc, se)}
    返回 {"formula": "IIW", "value": float, "elements": {...}} 或 None。
    """
    def conc(el):
        d = chem.get(el)
        if not d:
            return 0.0
        return d["conc"] if isinstance(d, dict) else d[0]

    c = conc("C")
    if c <= 0:
        return None
    fe = conc("Fe")
    # 铁基判定：Fe 含量最高（或基体 Fe）
    if not chem or fe <= 0:
        return None
    top_el = max(chem, key=lambda el: conc(el))
    if top_el != "Fe" and fe < 50:
        return None
    ce = (c + conc("Mn") / 6.0 + (conc("Cr") + conc("Mo") + conc("V")) / 5.0
          + (conc("Ni") + conc("Cu")) / 15.0)
    return {"formula": "IIW", "value": float(ce),
            "elements": {"C": c, "Mn": conc("Mn"), "Cr": conc("Cr"),
                         "Mo": conc("Mo"), "V": conc("V"),
                         "Ni": conc("Ni"), "Cu": conc("Cu")}}


def average_records(records):
    """
    对多条测试记录求平均（Analysis Averaging）。
    返回 (chemistry, n)，chemistry 为各元素平均浓度（标准误取均值）。
    只平均具有 chemistry 的记录。
    """
    chem_recs = [r.chemistry for r in records if r.chemistry]
    if not chem_recs:
        return {}, 0
    elements = {}
    for d in chem_recs:
        for el in d:
            elements.setdefault(el, []).append(d[el])
    out = {}
    for el, lst in elements.items():
        cons = [x["conc"] if isinstance(x, dict) else x[0] for x in lst]
        ses = [x["se"] if isinstance(x, dict) and x.get("se") else 0.0 for x in lst]
        out[el] = {"conc": sum(cons) / len(cons),
                   "se": sum(ses) / len(ses),
                   "source": "AVG"}
    return out, len(chem_recs)


class RecordsStore:
    """测试记录持久化（JSON）。"""

    def __init__(self, path):
        self.path = path
        self.records = []
        self.load()

    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.records = [TestRecord.from_dict(d) for d in data]
            except (json.JSONDecodeError, TypeError, KeyError):
                self.records = []
        else:
            self.records = []

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump([r.to_dict() for r in self.records], f,
                      ensure_ascii=False, indent=1)

    def next_number(self):
        nums = [r.number for r in self.records]
        return (max(nums) + 1) if nums else 1

    def add(self, **fields):
        rec = TestRecord(number=self.next_number(), timestamp=now_iso(), **fields)
        self.records.append(rec)
        self.save()
        return rec

    def get(self, number):
        for r in self.records:
            if r.number == number:
                return r
        return None

    def update(self, number, **fields):
        r = self.get(number)
        if r:
            for k, v in fields.items():
                if hasattr(r, k):
                    setattr(r, k, v)
            self.save()
            return r
        return None

    def delete(self, numbers):
        self.records = [r for r in self.records if r.number not in numbers]
        self.save()

    def clear(self):
        self.records = []
        self.save()

    def filter_by_date(self, d0=None, d1=None):
        """d0/d1: datetime.date。返回筛选后的记录（含端点）。"""
        if d0 is None and d1 is None:
            return list(self.records)
        out = []
        for r in self.records:
            try:
                d = datetime.datetime.strptime(r.timestamp[:10], "%Y-%m-%d").date()
            except ValueError:
                continue
            if d0 and d < d0:
                continue
            if d1 and d > d1:
                continue
            out.append(r)
        return out

    def sorted_desc(self):
        return sorted(self.records, key=lambda r: r.number, reverse=True)
