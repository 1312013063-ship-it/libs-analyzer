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
AI 分析图谱引擎（本地规则驱动，离线可用）

对一次 LIBS 测试（峰匹配 + 可选定量定标）做智能分析：
  1. 元素级置信度评分（多线确认 / 波长偏差 / 谱线强度）
  2. 材料/基体推断（常见合金组合知识库）
  3. 生成可读的智能解读（主要/次要/痕量/异常提示）
  4. 输出关系图谱（networkx 布局 + matplotlib 深色画布）

说明：本模块为启发式辅助分析，结论仅供参考，
正式判定请结合标样与权威标准。
"""
import numpy as np

import matplotlib
matplotlib.use("Qt5Agg")
import matplotlib.pyplot as plt
import networkx as nx

from .element_lines import ELEMENT_NAMES

# 中文字体（与主窗口一致；独立使用本模块时也保证图谱中文可渲染）
plt.rcParams["font.sans-serif"] = [
    "SimHei", "Microsoft YaHei", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

# ---------------------------------------------------------------- 知识库
# 常见材料类别：主元素 + 关键共存元素组合（用于基体/材料推断）
ALLOY_KNOWLEDGE = [
    # (材料名, 中文名, 主元素, 关键共存元素集合, 说明)
    ("Stainless Steel", "不锈钢", "Fe", {"Cr", "Ni"},
     "Fe-Cr-Ni 系，Cr≥10.5% 耐蚀"),
    ("Carbon Steel", "碳钢", "Fe", {"C", "Mn", "Si"},
     "Fe 基 + C/Mn/Si 常规合金元素"),
    ("Aluminum Alloy", "铝合金", "Al", {"Mg", "Si", "Cu", "Mn", "Zn"},
     "Al 基，Mg/Si/Cu/Mn/Zn 常见强化元素"),
    ("Brass", "黄铜", "Cu", {"Zn"},
     "Cu-Zn 二元合金"),
    ("Bronze", "青铜", "Cu", {"Sn", "Al", "Si", "Pb"},
     "Cu-Sn 或 Cu-Al 系"),
    ("Titanium Alloy", "钛合金", "Ti", {"Al", "V", "Mo", "Sn"},
     "Ti 基，Al/V 常见 α+β 稳定元素"),
    ("Nickel Base", "镍基合金", "Ni", {"Cr", "Fe", "Mo", "Co"},
     "Ni 基高温合金，Cr/Fe/Mo 强化"),
    ("Zinc Alloy", "锌合金", "Zn", {"Al", "Cu", "Mg"},
     "Zn-Al-Cu 压铸合金"),
    ("Copper Alloy", "铜合金", "Cu", {"Ni", "Pb", "Fe"},
     "Cu 基多元素合金"),
    ("Precious Metal", "贵金属", "Au", {"Ag", "Cu", "Pd", "Pt"},
     "Au-Ag-Cu 系金合金"),
    ("Silver Alloy", "银合金", "Ag", {"Cu", "Zn", "Cd"},
     "Ag 基，Cu/Zn 硬化"),
    ("Lead Base", "铅基合金", "Pb", {"Sb", "Sn", "Cu"},
     "Pb-Sb/Sn 系轴承/焊料"),
    ("Magnesium Alloy", "镁合金", "Mg", {"Al", "Zn", "Mn"},
     "Mg 基轻合金"),
]

# 空气/环境常见干扰元素（匹配到时要提示）
ENV_ELEMENTS = {"Ar", "N", "O", "H"}

# 微量元素（作为合金元素的常见添加，非主成分）
TRACE_CANDIDATES = {"B", "P", "S", "Zr", "La", "Ce", "Nd", "Y",
                    "V", "Mo", "Co", "W", "Sb", "Sn", "Cd", "Hg"}


# ---------------------------------------------------------------- 分析
class ElementInsight:
    """单个检测元素的智能分析结果。"""

    __slots__ = ("element", "name", "n_lines", "best_delta", "max_rel",
                 "peak_intensity", "confidence", "level", "conc", "se")

    def __init__(self, element, name, n_lines, best_delta, max_rel,
                 peak_intensity, confidence, conc=None, se=None):
        self.element = element
        self.name = name
        self.n_lines = n_lines
        self.best_delta = best_delta
        self.max_rel = max_rel
        self.peak_intensity = peak_intensity
        self.confidence = confidence
        self.level = confidence_level(confidence)
        self.conc = conc
        self.se = se

    def __repr__(self):
        return (f"<ElementInsight {self.element} conf={self.confidence:.2f} "
                f"lines={self.n_lines} level={self.level}>")


class MaterialHypothesis:
    """材料/基体推断候选。"""

    __slots__ = ("name", "name_cn", "confidence", "elements", "note")

    def __init__(self, name, name_cn, confidence, elements, note):
        self.name = name
        self.name_cn = name_cn
        self.confidence = confidence
        self.elements = elements
        self.note = note

    def __repr__(self):
        return f"<MaterialHypothesis {self.name} conf={self.confidence:.2f}>"


class InsightResult:
    """一次 AI 分析的完整结果。"""

    def __init__(self, spectrum_name, elements, materials, summary,
                 base=None):
        self.spectrum_name = spectrum_name
        self.elements = elements                 # [ElementInsight] 按置信度降序
        self.materials = materials               # [MaterialHypothesis]
        self.summary = summary                   # 解读文本（多行）
        self.base = base

    @property
    def confirmed(self):
        return [e for e in self.elements if e.level == "确认"]

    @property
    def likely(self):
        return [e for e in self.elements if e.level == "较强"]

    @property
    def suspect(self):
        return [e for e in self.elements
                if e.level in ("疑似", "弱")]


def confidence_level(conf):
    if conf >= 0.75:
        return "确认"
    if conf >= 0.50:
        return "较强"
    if conf >= 0.30:
        return "疑似"
    return "弱"


def _delta_score(delta):
    """波长偏差质量分：≤0.05nm 满分，线性衰减到 0.30nm 为 0。"""
    if delta <= 0.05:
        return 1.0
    if delta >= 0.30:
        return 0.0
    return 1.0 - (delta - 0.05) / 0.25


def analyze_elements(matches, calibrations=None):
    """从峰匹配结果聚合元素，评分置信度，可叠加定量预测。

    matches: main_window 的 self.matches 行（含 element/wl/delta/rel/intensity）
    calibrations: {元素: CalibrationModel}，有则对该元素反推浓度
    """
    agg = {}
    for m in matches:
        el = m.get("element")
        if not el:
            continue
        d = agg.setdefault(el, {"n": 0, "best_delta": 1e9, "max_rel": 0,
                                "peak": 0.0})
        d["n"] += 1
        d["best_delta"] = min(d["best_delta"], float(m.get("delta") or 1e9))
        d["max_rel"] = max(d["max_rel"], float(m.get("rel") or 0))
        d["peak"] = max(d["peak"], float(m.get("intensity") or 0))

    out = []
    for el, d in agg.items():
        base = _delta_score(d["best_delta"])
        # 多线确认加分：2 条 ×1.12，3 条及以上 ×1.22
        mult = 1.0
        if d["n"] >= 3:
            mult = 1.22
        elif d["n"] == 2:
            mult = 1.12
        # 弱线（库相对强度 <60）匹配略打折扣
        if 0 < d["max_rel"] < 60:
            mult *= 0.9
        conf = min(1.0, base * mult)
        conc = se = None
        if calibrations and el in calibrations:
            try:
                conc, se = calibrations[el].predict(d["peak"])
            except (ValueError, ZeroDivisionError, FloatingPointError):
                conc = se = None
        out.append(ElementInsight(
            el, ELEMENT_NAMES.get(el, el), d["n"], d["best_delta"],
            d["max_rel"], d["peak"], conf, conc, se))
    out.sort(key=lambda e: e.confidence, reverse=True)
    return out


def infer_materials(elements, base=None):
    """根据元素集合与可选基体推断材料类别，返回候选列表。"""
    if not elements:
        return []
    by_el = {e.element: e for e in elements}
    # 只考虑不低于"疑似"的元素
    active = {e.element for e in elements if e.level != "弱"}
    candidates = []
    for name, cn, main_el, combo, note in ALLOY_KNOWLEDGE:
        if main_el not in active:
            continue
        main_conf = by_el[main_el].confidence
        # 主元素置信度 × 关键共存元素平均置信度
        combo_els = [c for c in combo if c in active]
        if not combo_els:
            continue
        combo_conf = np.mean([by_el[c].confidence for c in combo_els])
        conf = main_conf * 0.65 + combo_conf * 0.35
        if conf < 0.35:
            continue
        candidates.append(MaterialHypothesis(
            name, cn, min(1.0, conf),
            [main_el] + combo_els, note))
    # 基体优先（用户明确指定基体时置顶）
    if base and candidates:
        base_match = [c for c in candidates if c.elements[0] == base]
        rest = [c for c in candidates if c.elements[0] != base]
        base_match.sort(key=lambda c: c.confidence, reverse=True)
        rest.sort(key=lambda c: c.confidence, reverse=True)
        candidates = base_match + rest
    else:
        candidates.sort(key=lambda c: c.confidence, reverse=True)
    return candidates[:4]


def build_summary(elements, materials, base=None):
    """生成多行中文解读文本。"""
    lines = []
    if not elements:
        lines.append("未匹配到可信元素（降低匹配容差或检查谱线质量后重试）。")
        return "\n".join(lines)

    conf = [e for e in elements if e.level == "确认"]
    likely = [e for e in elements if e.level == "较强"]
    suspect = [e for e in elements if e.level in ("疑似", "弱")]

    if materials:
        top = materials[0]
        lines.append(f"◆ 材料推断：{top.name_cn}（{top.name}），"
                     f"置信度 {top.confidence * 100:.0f}%"
                     f"{'，依据基体 ' + base if base else ''}")
        lines.append(f"  依据：{top.name_cn} 主元素 {top.elements[0]} "
                     f"+ {', '.join(top.elements[1:])}")
        if len(materials) > 1:
            other = " / ".join(f"{m.name_cn}({m.confidence * 100:.0f}%)"
                               for m in materials[1:])
            lines.append(f"  其他候选：{other}")
    else:
        lines.append("◆ 材料推断：未找到匹配的常见材料组合，"
                     "可能为非常规合金或混合样品。")

    def fmt_els(els):
        parts = []
        for e in els:
            if e.conc is not None:
                parts.append(f"{e.element}≈{e.conc:.3g}%"
                             + (f"±{e.se:.3g}" if e.se else ""))
            else:
                parts.append(f"{e.element}({e.confidence * 100:.0f}%)")
        return ", ".join(parts)

    if conf:
        lines.append(f"◆ 主要成分（确认）：{fmt_els(conf)}")
    if likely:
        lines.append(f"◆ 次要成分（较强）：{fmt_els(likely)}")
    if suspect:
        lines.append(f"◆ 痕量/疑似（需复测确认）：{fmt_els(suspect)}")

    env = [e.element for e in elements if e.element in ENV_ELEMENTS]
    if env:
        lines.append(f"⚠ 提示：检测到环境元素 {', '.join(env)}（空气/水汽常见），"
                     "建议检查吹扫气氛与样品表面清洁度。")

    low = [e.element for e in elements
           if e.confidence < 0.30 and e.element not in ENV_ELEMENTS]
    if low:
        lines.append(f"⚠ 弱信号元素 {', '.join(low)} 置信度偏低，"
                     "可能为谱线干扰或表面沾污，建议复测确认。")
    return "\n".join(lines)


def analyze_insight(matches, spectrum, calibrations=None, base=None):
    """一站式分析：聚合元素 → 推断材料 → 生成解读。"""
    elements = analyze_elements(matches, calibrations)
    materials = infer_materials(elements, base)
    summary = build_summary(elements, materials, base)
    return InsightResult(spectrum.name if spectrum else "未知样品",
                         elements, materials, summary, base)


# ---------------------------------------------------------------- 图谱
_LEVEL_COLORS = {
    "确认": "#3FB950",
    "较强": "#00A9E0",
    "疑似": "#D29922",
    "弱":   "#5C6B7A",
}


def build_insight_figure(insight, figsize=(9.2, 6.2), dpi=110):
    """用 networkx 绘制 AI 分析图谱（深色画布 + 品牌蓝）。

    返回 matplotlib Figure。左图 = 元素-材料关系网络；
    右图 = 置信度条形（各元素按等级着色）。
    """
    fig = plt.Figure(figsize=figsize, dpi=dpi)
    fig.patch.set_facecolor("#101418")

    # ---------- 左：关系网络 ----------
    axn = fig.add_subplot(121)
    axn.set_facecolor("#0C1015")

    G = nx.Graph()
    for e in insight.elements:
        G.add_node(e.element, kind="element", conf=e.confidence,
                   level=e.level)
    for m in insight.materials:
        G.add_node(m.name, kind="material", conf=m.confidence, level="材料")
        for el in m.elements:
            if el in G:
                G.add_edge(m.name, el, weight=m.confidence)

    # 同属一个材料的元素之间加虚线弱关联
    for m in insight.materials:
        els = [el for el in m.elements if el in G]
        for i in range(len(els)):
            for j in range(i + 1, len(els)):
                if not G.has_edge(els[i], els[j]):
                    G.add_edge(els[i], els[j], weight=0.35, weak=True)

    if G.number_of_nodes() == 0:
        axn.text(0.5, 0.5, "无可视化元素", ha="center", va="center",
                 color="#93A1B0", fontsize=13, transform=axn.transAxes)
    else:
        pos = nx.spring_layout(G, seed=7, k=0.9, iterations=120)
        for kind, color, size in (
                ("element", "#93A1B0", 620),
                ("material", "#00A9E0", 900)):
            nodes = [n for n, d in G.nodes(data=True)
                     if d.get("kind") == kind]
            if nodes:
                nx.draw_networkx_nodes(
                    G, pos, nodelist=nodes, node_color=color,
                    node_size=size, ax=axn,
                    edgecolors="#101418", linewidths=1.6)

        # 元素按等级描边强调
        for lvl, ec in _LEVEL_COLORS.items():
            nodes = [n for n, d in G.nodes(data=True)
                     if d.get("kind") == "element" and d.get("level") == lvl]
            if nodes:
                nx.draw_networkx_nodes(
                    G, pos, nodelist=nodes, node_color="none",
                    node_size=620, ax=axn, node_shape="o",
                    edgecolors=ec, linewidths=2.4)

        solid = [(u, v) for u, v, d in G.edges(data=True)
                 if not d.get("weak")]
        weak = [(u, v) for u, v, d in G.edges(data=True)
                if d.get("weak")]
        if solid:
            nx.draw_networkx_edges(G, pos, edgelist=solid, ax=axn,
                                   edge_color="#2FC2F0", width=1.6,
                                   alpha=0.85)
        if weak:
            nx.draw_networkx_edges(G, pos, edgelist=weak, ax=axn,
                                   edge_color="#2C3844", width=1.0,
                                   style="dashed", alpha=0.8)

        nx.draw_networkx_labels(G, pos, ax=axn,
                                font_family=["Microsoft YaHei", "SimHei"],
                                font_size=11, font_color="#E8EEF5")

    axn.set_title("AI 元素关系图谱（元素-材料关联）",
                  color="#7DD3FC", fontsize=12, fontweight="bold",
                  pad=10)
    axn.axis("off")
    # 收紧坐标范围，避免网络图被裁剪（axis off 下 tight_layout 不可靠）
    if G.number_of_nodes() > 0:
        xs = [p[0] for p in pos.values()]
        ys = [p[1] for p in pos.values()]
        pad = 0.18
        axn.set_xlim(min(xs) - pad, max(xs) + pad)
        axn.set_ylim(min(ys) - pad, max(ys) + pad)

    # ---------- 右：置信度条形 ----------
    axb = fig.add_subplot(122)
    axb.set_facecolor("#0C1015")
    els = insight.elements[:12] if insight.elements else []
    if els:
        y = np.arange(len(els))[::-1]
        colors = [_LEVEL_COLORS[e.level] for e in els]
        axb.barh(y, [e.confidence for e in els], color=colors,
                 height=0.62, edgecolor="#101418", linewidth=1.2)
        axb.set_yticks(y)
        axb.set_yticklabels(
            [f"{e.element} {e.name}" for e in els],
            fontsize=10, color="#E8EEF5")
        axb.set_xlim(0, 1.08)
        for yi, e in zip(y, els):
            label = f"{e.confidence * 100:.0f}%"
            if e.conc is not None:
                label += f"  ≈{e.conc:.3g}%"
            axb.text(e.confidence + 0.02, yi, label, va="center",
                     fontsize=9, color="#93A1B0")
        # 置信度分级参考线
        for cut, c in ((0.75, "#3FB950"), (0.5, "#D29922"), (0.3, "#F85149")):
            axb.axvline(cut, color=c, lw=0.8, ls="--", alpha=0.6)
    else:
        axb.text(0.5, 0.5, "无元素数据", ha="center", va="center",
                 color="#93A1B0", fontsize=12, transform=axb.transAxes)

    axb.set_title("元素置信度与浓度（AI 评分）",
                  color="#7DD3FC", fontsize=12, fontweight="bold", pad=10)
    for s in axb.spines.values():
        s.set_color("#2C3844")
    axb.tick_params(colors="#93A1B0", labelsize=9)
    axb.grid(axis="x", color="#232C36", lw=0.6, alpha=0.7)
    axb.set_axisbelow(True)

    fig.subplots_adjust(left=0.06, right=0.98, top=0.93, bottom=0.07,
                        wspace=0.30)
    return fig
