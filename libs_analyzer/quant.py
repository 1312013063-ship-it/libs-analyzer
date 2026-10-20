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
定量分析：定标曲线（外标）法。

原理：对同一元素谱线，测量一组已知浓度标准样的谱线强度，
拟合 强度 I = a·浓度 C + b（最小二乘线性回归）；
未知样品测得其谱线强度 Ix 后，反推  Cx = (Ix - b) / a，
并按经典回归公式给出预测浓度的标准误 SE。

说明：
- 峰强度取峰高（若未来需要峰面积，可在取数处替换）。
- 适用于同一基体/相同测量条件下的系列样品；不同基体建议内标法（后续可扩展）。
"""
import json
import os

import numpy as np
from scipy import stats


class CalibrationStore:
    """定标曲线的持久化存储（JSON 文件，跨会话保存/加载）。"""

    def __init__(self, path):
        self.path = path

    def load(self):
        """加载全部定标：{元素: CalibrationModel}。"""
        if not self.path or not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            out = {}
            for el, d in data.items():
                m = CalibrationModel.from_dict(d)
                if m.n_points >= 2:
                    try:
                        m.ensure_fit()
                        out[el] = m
                    except ValueError:
                        continue
            return out
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            return {}

    def save(self, calibrations):
        """保存全部定标。"""
        if not self.path:
            return
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        data = {el: m.to_dict() for el, m in calibrations.items()}
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)


class CalibrationModel:
    """单个元素·单条谱线的定标模型。"""

    def __init__(self, element="", line_nm=0.0, unit="wt%"):
        self.element = element
        self.line_nm = line_nm
        self.unit = unit
        self.points = []          # [{"label", "concentration", "intensity"}]
        self._fit = None          # 拟合结果缓存
        self._dirty = True

    # ------------------------------------------------------------- 数据
    def add_point(self, concentration, intensity, label=""):
        self.points.append({
            "label": label or f"标准样{len(self.points) + 1}",
            "concentration": float(concentration),
            "intensity": float(intensity),
        })
        self._dirty = True

    def remove_point(self, index):
        if 0 <= index < len(self.points):
            self.points.pop(index)
            self._dirty = True

    def clear(self):
        self.points = []
        self._fit = None
        self._dirty = True

    @property
    def n_points(self):
        return len(self.points)

    # ------------------------------------------------------------- 拟合
    def fit(self):
        """线性回归 I = a*C + b。返回拟合字典；标准点不足 2 个时抛 ValueError。"""
        n = len(self.points)
        if n < 2:
            raise ValueError("标准样至少需要 2 个才能建立定标曲线")

        c = np.array([p["concentration"] for p in self.points], dtype=float)
        i = np.array([p["intensity"] for p in self.points], dtype=float)

        res = stats.linregress(c, i)
        se_b = getattr(res, "intercept_stderr", np.nan)
        mean_c = float(c.mean())
        sxx = float(((c - mean_c) ** 2).sum())

        self._fit = {
            "slope": float(res.slope),            # a：单位强度/浓度
            "intercept": float(res.intercept),    # b
            "r": float(res.rvalue),
            "r2": float(res.rvalue ** 2),
            "p": float(res.pvalue),
            "se_slope": float(res.stderr),
            "se_intercept": se_b,
            "n": n,
            "mean_c": mean_c,
            "sxx": sxx,
        }
        self._dirty = False
        return self._fit

    def ensure_fit(self):
        if self._dirty or self._fit is None:
            return self.fit()
        return self._fit

    @property
    def r_squared(self):
        return self.ensure_fit()["r2"]

    # ------------------------------------------------------------- 预测
    def predict(self, intensity):
        """
        由未知样品谱线强度反推浓度。

        返回 (concentration, se)：
            concentration : 预测浓度（单位同标准样）
            se            : 预测浓度标准误（经典回归公式，近似）
        若标准点不足，抛 ValueError。
        """
        f = self.ensure_fit()
        c = (float(intensity) - f["intercept"]) / f["slope"]
        # 经典回归：预测浓度的标准误（斜率传播近似）
        se = abs(f["se_slope"]) * np.sqrt(
            1.0 / f["n"] + (c - f["mean_c"]) ** 2 / f["sxx"])
        return float(c), float(se)

    # ------------------------------------------------------------- 输出
    def equation_str(self):
        f = self.ensure_fit()
        return (f"I = {f['slope']:.4g}·C + {f['intercept']:.4g}  "
                f"(R²={f['r2']:.4f}, n={f['n']})")

    # ------------------------------------------------------------- 序列化
    def to_dict(self):
        """序列化为可 JSON 保存的字典。"""
        return {
            "element": self.element,
            "line_nm": self.line_nm,
            "unit": self.unit,
            "points": [
                {"label": p["label"], "concentration": p["concentration"],
                 "intensity": p["intensity"]}
                for p in self.points
            ],
        }

    @staticmethod
    def from_dict(d):
        """从字典恢复定标模型。"""
        m = CalibrationModel(element=d.get("element", ""),
                             line_nm=d.get("line_nm", 0.0),
                             unit=d.get("unit", "wt%"))
        for p in d.get("points", []):
            m.add_point(p.get("concentration", 0.0), p.get("intensity", 0.0),
                        label=p.get("label", ""))
        return m

    def to_csv_rows(self):
        rows = [["type", "element", "line_nm", "unit", "concentration",
                 "intensity", "label"]]
        for p in self.points:
            rows.append(["standard", self.element, self.line_nm, self.unit,
                         p["concentration"], p["intensity"], p["label"]])
        if self._fit is not None:
            f = self._fit
            rows.append(["fit_slope", self.element, self.line_nm, "", f["slope"], "", ""])
            rows.append(["fit_intercept", self.element, self.line_nm, "", f["intercept"], "", ""])
            rows.append(["fit_r2", self.element, self.line_nm, "", f["r2"], "", ""])
        return rows
