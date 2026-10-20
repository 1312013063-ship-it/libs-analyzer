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
HTML 报告生成（参照 SciAps Z-902 报告功能）。
生成可打印的测试报告：Test Info + 光谱图（内嵌 PNG）+ Chemistry + Grade Match。
"""
import base64
import os
import datetime


def _img_base64(path):
    if not path or not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def build_html_report(out_path, title, info_lines, spectrum_png=None,
                      chemistry=None, grades=None, ce=None):
    """
    生成 HTML 报告。
    info_lines: [(字段, 值), ...]
    spectrum_png: 光谱图 PNG 路径（内嵌）
    chemistry:    {元素: {"conc","se","source"}} 或 None
    grades:       [{"grade","score","base_cn"}] 或 None
    ce:           {"formula","value"} 或 None
    """
    html = ["<!DOCTYPE html><html lang='zh'><head><meta charset='utf-8'>",
            "<title>LIBS 分析报告</title><style>",
            "body{font-family:'Microsoft YaHei',sans-serif;margin:32px;color:#222}",
            "h1{color:#0f1720;border-bottom:3px solid #1f6fb4;padding-bottom:8px}",
            "h2{color:#1f6fb4;margin-top:28px}",
            "table{border-collapse:collapse;margin:10px 0;width:100%}",
            "th,td{border:1px solid #cbd5e1;padding:6px 10px;font-size:14px}",
            "th{background:#f1f5f9}",
            "img{max-width:100%;border:1px solid #ddd;margin:8px 0}",
            ".info td{background:#f8fafc}",
            ".good{color:#1e8e3e;font-weight:bold}",
            ".bad{color:#d93025;font-weight:bold}",
            "</style></head><body>"]
    html.append(f"<h1>LIBS 分析报告 · {title}</h1>")
    html.append(f"<p>生成时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>")

    if info_lines:
        html.append("<h2>测试信息（Test Info）</h2>")
        html.append("<table class='info'>")
        for k, v in info_lines:
            html.append(f"<tr><th style='width:180px'>{k}</th><td>{v}</td></tr>")
        html.append("</table>")

    if spectrum_png:
        b64 = _img_base64(spectrum_png)
        if b64:
            html.append("<h2>光谱（Spectrum）</h2>")
            html.append(f"<img src='data:image/png;base64,{b64}'>")

    if chemistry:
        html.append("<h2>化学结果（Chemistry）</h2>")
        html.append("<table><tr><th>元素</th><th>浓度 (wt%)</th>"
                    "<th>± 标准误</th><th>来源</th></tr>")
        for el, d in chemistry.items():
            conc = d.get("conc")
            se = d.get("se")
            disp = f"{conc:.4f}" if conc is not None else "ND"
            html.append(f"<tr><td>{el}</td><td>{disp}</td>"
                        f"<td>{f'±{se:.4f}' if se else ''}</td>"
                        f"<td>{d.get('source', '')}</td></tr>")
        html.append("</table>")

    if grades:
        html.append("<h2>牌号匹配（Grade Match）</h2>")
        html.append("<table><tr><th>排名</th><th>牌号</th><th>分数</th>"
                    "<th>基体</th></tr>")
        for i, g in enumerate(grades):
            cls = "good" if g["score"] >= 90 else ("bad" if g["score"] < 70 else "")
            html.append(f"<tr><td>{i + 1}</td><td>{g['grade']}</td>"
                        f"<td class='{cls}'>{g['score']:.0f}/100</td>"
                        f"<td>{g['base_cn']}</td></tr>")
        html.append("</table>")

    if ce:
        html.append("<h2>碳当量（CE）</h2>")
        html.append(f"<p>公式：{ce['formula']} 　"
                    f"<b>CE = {ce['value']:.3f}%</b></p>")

    html.append("<p style='color:#888;font-size:12px;margin-top:40px'>"
                "由 Libs通用测试软件生成（参照 SciAps Z-902）</p>")
    html.append("</body></html>")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("".join(html))
    return out_path
