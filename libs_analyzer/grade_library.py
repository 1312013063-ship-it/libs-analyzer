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
合金牌号库与 Grade Match（牌号匹配）引擎。

牌号匹配算法参照 SciAps Z-902：对每个候选牌号，检查其规格元素
（含量范围 lo–hi wt%），对每个实测浓度：
  - 在规格范围内           -> 不扣分
  - 低于下限 lo           -> 惩罚 += (lo - 实测)/lo * 100
  - 高于上限 hi           -> 惩罚 += (实测 - hi)/hi * 100
最后  score = max(0, 100 - 各元素惩罚之和)  （100 = 完美匹配）

注：牌号组成取常见典型范围（参考 ASTM/UNS 常用值），供软件演示与
日常快速鉴定参考；正式放行/放行判定请以权威标准为准。
"""
import os
import json

# 基体（对应 Z902 Alloy Family）
BASES = {
    "aluminum":    "铝基",
    "steel":       "碳钢/低合金钢",
    "stainless":   "不锈钢",
    "nickel":      "镍基",
    "copper":      "铜基",
    "titanium":    "钛基",
    "cobalt":      "钴基",
}

# 各基体的元素套件（Element Suite，参考 Z902 Alloy Mode）
BASE_SUITES = {
    "aluminum":  ["Be", "Mg", "Al", "Si", "Ti", "V", "Cr", "Mn",
                  "Fe", "Ni", "Cu", "Zn", "Zr", "Pb", "Bi", "Ag"],
    "steel":     ["Al", "Si", "Ti", "V", "Cr", "Mn", "Fe", "Co",
                  "Cu", "Ni", "Nb", "Mo", "W", "Pb"],
    "stainless": ["Al", "Si", "Ti", "V", "Cr", "Mn", "Fe", "Co",
                  "Ni", "Cu", "Se", "Nb", "Mo", "W"],
    "nickel":    ["Al", "Si", "Ti", "Cr", "Mn", "Fe", "Co",
                  "Ni", "Cu", "Nb", "Mo", "W", "Hf", "Ta", "Re"],
    "copper":    ["Be", "Al", "Si", "Cr", "Mn", "Fe", "Co",
                  "Ni", "Cu", "Zn", "Se", "Ag", "Sn", "Pb", "Bi"],
    "titanium":  ["Al", "Si", "Ti", "V", "Cr", "Mn", "Fe",
                  "Ni", "Zr", "Nb", "Mo", "Sn"],
    "cobalt":    ["Al", "Si", "Ti", "Cr", "Mn", "Fe", "Co",
                  "Ni", "Cu", "Nb", "Mo", "W"],
}

# 牌号库：基体 -> {牌号: {元素: (下限%, 上限%), "base": 基体元素}}
# 仅列典型规格元素；"base" 为基体元素（不参与扣分，仅用于过滤）。
GRADE_LIBRARY = {
    "stainless": {
        "304":  {"base": "Fe", "Cr": (18.0, 20.0), "Ni": (8.0, 10.5),
                 "Mn": (0.0, 2.0), "Si": (0.0, 0.75), "C": (0.0, 0.08),
                 "P": (0.0, 0.045), "S": (0.0, 0.03)},
        "304L": {"base": "Fe", "Cr": (18.0, 20.0), "Ni": (8.0, 10.5),
                 "Mn": (0.0, 2.0), "Si": (0.0, 0.75), "C": (0.0, 0.03)},
        "316":  {"base": "Fe", "Cr": (16.0, 18.0), "Ni": (10.0, 14.0),
                 "Mo": (2.0, 3.0), "Mn": (0.0, 2.0), "Si": (0.0, 0.75),
                 "C": (0.0, 0.08)},
        "316L": {"base": "Fe", "Cr": (16.0, 18.0), "Ni": (10.0, 14.0),
                 "Mo": (2.0, 3.0), "Mn": (0.0, 2.0), "Si": (0.0, 0.75),
                 "C": (0.0, 0.03)},
        "321":  {"base": "Fe", "Cr": (17.0, 19.0), "Ni": (9.0, 12.0),
                 "Mn": (0.0, 2.0), "Si": (0.0, 0.75), "C": (0.0, 0.08),
                 "Ti": (0.0, 0.7)},
        "410":  {"base": "Fe", "Cr": (11.5, 13.5), "C": (0.0, 0.15),
                 "Ni": (0.0, 0.75), "Mn": (0.0, 1.0), "Si": (0.0, 1.0)},
        "430":  {"base": "Fe", "Cr": (16.0, 18.0), "C": (0.0, 0.12),
                 "Mn": (0.0, 1.0), "Si": (0.0, 1.0), "Ni": (0.0, 0.6)},
        "17-4PH": {"base": "Fe", "Cr": (15.0, 17.5), "Ni": (3.0, 5.0),
                   "Cu": (3.0, 5.0), "Mn": (0.0, 1.0), "Si": (0.0, 1.0),
                   "C": (0.0, 0.07)},
        "2205": {"base": "Fe", "Cr": (22.0, 23.0), "Ni": (4.5, 6.5),
                 "Mo": (3.0, 3.5), "Mn": (0.0, 2.0), "Si": (0.0, 1.0),
                 "N": (0.14, 0.2)},
    },
    "steel": {
        "A36":  {"base": "Fe", "C": (0.0, 0.26), "Mn": (0.6, 0.9),
                 "Si": (0.0, 0.4), "P": (0.0, 0.04), "S": (0.0, 0.05)},
        "1010": {"base": "Fe", "C": (0.08, 0.13), "Mn": (0.3, 0.6)},
        "1020": {"base": "Fe", "C": (0.18, 0.23), "Mn": (0.3, 0.6)},
        "1045": {"base": "Fe", "C": (0.43, 0.50), "Mn": (0.6, 0.9)},
        "4130": {"base": "Fe", "C": (0.28, 0.33), "Cr": (0.8, 1.1),
                 "Mo": (0.15, 0.25), "Mn": (0.4, 0.6), "Si": (0.0, 0.35)},
        "4140": {"base": "Fe", "C": (0.38, 0.43), "Cr": (0.8, 1.1),
                 "Mo": (0.15, 0.25), "Mn": (0.75, 1.0), "Si": (0.0, 0.35)},
        "8620": {"base": "Fe", "C": (0.18, 0.23), "Cr": (0.4, 0.6),
                 "Ni": (0.4, 0.7), "Mo": (0.15, 0.25), "Mn": (0.7, 0.9)},
    },
    "aluminum": {
        "1100": {"base": "Al", "Cu": (0.0, 0.2), "Mn": (0.0, 0.05),
                 "Zn": (0.0, 0.1), "Si": (0.0, 0.95), "Fe": (0.0, 0.95)},
        "2024": {"base": "Al", "Cu": (3.8, 4.9), "Mg": (1.2, 1.8),
                 "Mn": (0.3, 0.9), "Si": (0.0, 0.5), "Fe": (0.0, 0.5),
                 "Zn": (0.0, 0.25)},
        "5052": {"base": "Al", "Mg": (2.2, 2.8), "Cr": (0.15, 0.35),
                 "Si": (0.0, 0.25), "Fe": (0.0, 0.4), "Mn": (0.0, 0.1)},
        "6061": {"base": "Al", "Mg": (0.8, 1.2), "Si": (0.4, 0.8),
                 "Cu": (0.15, 0.4), "Cr": (0.04, 0.35), "Fe": (0.0, 0.7),
                 "Mn": (0.0, 0.15), "Zn": (0.0, 0.25), "Ti": (0.0, 0.15)},
        "6063": {"base": "Al", "Mg": (0.45, 0.9), "Si": (0.2, 0.6),
                 "Fe": (0.0, 0.35), "Cu": (0.0, 0.1), "Mn": (0.0, 0.1),
                 "Zn": (0.0, 0.1)},
        "7075": {"base": "Al", "Zn": (5.1, 6.1), "Mg": (2.1, 2.9),
                 "Cu": (1.2, 2.0), "Cr": (0.18, 0.28), "Si": (0.0, 0.4),
                 "Fe": (0.0, 0.5), "Mn": (0.0, 0.3), "Ti": (0.0, 0.2)},
    },
    "nickel": {
        "Inconel 600": {"base": "Ni", "Cr": (14.0, 17.0), "Fe": (6.0, 10.0),
                        "Mn": (0.0, 1.0), "Si": (0.0, 0.5), "Cu": (0.0, 0.5)},
        "Inconel 625": {"base": "Ni", "Cr": (20.0, 23.0), "Mo": (8.0, 10.0),
                        "Nb": (3.15, 4.15), "Fe": (0.0, 5.0), "Mn": (0.0, 0.5),
                        "Si": (0.0, 0.5)},
        "Inconel 718": {"base": "Ni", "Cr": (17.0, 21.0), "Mo": (2.8, 3.3),
                        "Nb": (4.75, 5.5), "Fe": (0.0, 22.0),
                        "Ti": (0.65, 1.15), "Al": (0.2, 0.8), "Mn": (0.0, 0.35)},
        "Hastelloy C-276": {"base": "Ni", "Mo": (15.0, 17.0),
                            "Cr": (14.5, 16.5), "Fe": (4.0, 7.0),
                            "W": (3.0, 4.5), "Mn": (0.0, 1.0), "Si": (0.0, 0.08)},
        "Monel 400": {"base": "Ni", "Cu": (28.0, 34.0), "Fe": (0.0, 2.5),
                      "Mn": (0.0, 2.0), "Si": (0.0, 0.5)},
    },
    "copper": {
        "C11000": {"base": "Cu", "Zn": (0.0, 0.1), "Pb": (0.0, 0.005)},
        "C26000": {"base": "Cu", "Zn": (28.5, 31.5), "Pb": (0.0, 0.07),
                   "Fe": (0.0, 0.05)},
        "C36000": {"base": "Cu", "Zn": (35.5, 38.5), "Pb": (2.5, 3.7),
                   "Fe": (0.0, 0.35)},
        "C17200": {"base": "Cu", "Be": (1.8, 2.0), "Co": (0.0, 0.6),
                   "Ni": (0.0, 0.6)},
    },
    "titanium": {
        "TA2 (Grade 2)": {"base": "Ti", "Fe": (0.0, 0.3), "C": (0.0, 0.08),
                          "N": (0.0, 0.03), "O": (0.0, 0.25)},
        "TC4 (Grade 5)": {"base": "Ti", "Al": (5.5, 6.75), "V": (3.5, 4.5),
                          "Fe": (0.0, 0.4), "C": (0.0, 0.08)},
    },
    "cobalt": {
        "Stellite 6": {"base": "Co", "Cr": (27.0, 32.0), "W": (4.0, 6.0),
                       "C": (0.9, 1.4), "Mo": (0.0, 1.0),
                       "Ni": (0.0, 3.0), "Fe": (0.0, 3.0)},
    },
}


def all_grades():
    """全部牌号：{牌号: {规格..., "base":...}}"""
    out = {}
    for grades in GRADE_LIBRARY.values():
        out.update(grades)
    return out


# ------------------------------------------------------------- 用户自定义牌号
def parse_grade_specs(text, base_el="Fe"):
    """
    解析元素规格字符串 -> {元素: (下限, 上限)}。
    格式："Cr:16-18;Ni:8-10.5;Mo:2-3"，分隔符支持 ; / , / 换行。
    """
    specs = {}
    for seg in text.replace("\n", ";").replace(",", ";").split(";"):
        seg = seg.strip()
        if not seg:
            continue
        if ":" not in seg:
            continue
        el, rng = seg.split(":", 1)
        el = el.strip()
        rng = rng.replace("～", "-").replace("~", "-").strip()
        if not el or not rng:
            continue
        try:
            if "-" in rng:
                lo, hi = rng.split("-", 1)
                specs[el] = (float(lo.strip()), float(hi.strip()))
            else:
                v = float(rng.strip())
                specs[el] = (0.0, v)
        except ValueError:
            continue
    if base_el:
        specs["base"] = base_el
    return specs


def load_user_grades(path):
    """加载用户自定义牌号：{基体: {牌号: 规格字典}}。"""
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        out = {}
        for base, grades in data.items():
            out[base] = {}
            for name, spec in grades.items():
                specs = parse_grade_specs("", spec.get("base", "Fe"))
                specs = {"base": spec.get("base", "Fe")}
                for el, (lo, hi) in spec.get("elements", {}).items():
                    specs[el] = (float(lo), float(hi))
                out[base][name] = specs
        return out
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return {}


def save_user_grades(path, user_grades):
    """保存用户自定义牌号。"""
    if not path:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {}
    for base, grades in user_grades.items():
        data[base] = {}
        for name, spec in grades.items():
            data[base][name] = {
                "base": spec.get("base", "Fe"),
                "elements": {el: list(rng) for el, rng in spec.items()
                             if el != "base"},
            }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def grade_penalty(measured, lo, hi):
    """单个元素惩罚分（相对超出量 * 100，封顶 100）。"""
    if measured <= 0.0:
        # 未检出/接近零：若牌号要求该元素含量，按缺失处理
        if lo <= 0.0:
            return 0.0
        return 100.0
    if measured < lo:
        return min(100.0, (lo - measured) / lo * 100.0)
    if measured > hi:
        return min(100.0, (measured - hi) / hi * 100.0)
    return 0.0


def match_grades(chemistry, bases=None, top_n=5, extra_grades=None):
    """
    牌号匹配。chemistry: {元素: (浓度%, 标准误)}；可只含部分元素。
    bases: 限定基体列表（None = 全部）。
    extra_grades: 用户自定义牌号 {基体: {牌号: 规格}}，与内置合并。
    返回 [(牌号, score, base, penalties, specs), ...] 按分数降序。
      penalties: {元素: 惩罚分}
      specs:     {元素: (lo, hi)}

    除规格元素扣分外，还做基体冲突检查：若测得的主成分元素
    （浓度 > 50%）既不是牌号的基体元素、也不在该牌号规格中，
    视为基体不匹配，直接大扣分。
    """
    library = dict(GRADE_LIBRARY)
    if extra_grades:
        for base, grades in extra_grades.items():
            library.setdefault(base, {}).update(grades)

    # 测得的主成分元素（> 50%，可多个）
    majors = {el for el, (c, _) in chemistry.items() if c > 50.0}

    results = []
    for base, grades in library.items():
        if bases and base not in bases:
            continue
        for grade, spec in grades.items():
            penalties = {}
            total = 0.0
            base_el = spec.get("base")
            for el, (lo, hi) in spec.items():
                if el == "base":
                    continue
                if el not in chemistry:
                    continue
                val = chemistry[el][0]
                p = grade_penalty(val, lo, hi)
                penalties[el] = p
                total += p
            # 基体冲突检查
            for el in majors:
                if el == base_el:
                    continue
                if el not in spec:
                    penalties[f"基体{el}"] = 80.0
                    total += 80.0
            score = max(0.0, 100.0 - total)
            results.append({
                "grade": grade, "base": base, "base_cn": BASES[base],
                "score": score, "penalties": penalties, "spec": spec,
            })
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_n]
