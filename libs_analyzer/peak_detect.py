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
峰值检测与峰参数计算，基于 scipy.signal.find_peaks。
"""
import numpy as np
from scipy.signal import find_peaks


def detect_peaks(wl, intensity, prominence_frac=0.01, min_width_pts=3):
    """
    检测光谱峰。

    参数
    ----
    wl : np.ndarray            波长 (nm)
    intensity : np.ndarray     强度
    prominence_frac : float    最小显著度（相对最大强度的比例）
    min_width_pts : int        最小峰宽（数据点个数）

    返回
    ----
    peaks : np.ndarray         峰索引
    info : list[dict]          每个峰的 {index, wl, intensity, prominence,
                                width_pts, fwhm_nm, left_ips, right_ips}
    """
    if intensity is None or len(intensity) == 0:
        return np.array([], dtype=int), []

    threshold = prominence_frac * float(np.nanmax(intensity))
    peaks, props = find_peaks(
        intensity,
        prominence=threshold,
        width=min_width_pts,
    )

    step = float(np.median(np.diff(wl))) if len(wl) > 1 else 1.0

    info = []
    prom = np.atleast_1d(props.get("prominences", []))
    widths = np.atleast_1d(props.get("widths", []))
    left_ips = np.atleast_1d(props.get("left_ips", []))
    right_ips = np.atleast_1d(props.get("right_ips", []))

    for i, idx in enumerate(peaks):
        info.append({
            "index": int(idx),
            "wl": float(wl[idx]),
            "intensity": float(intensity[idx]),
            "prominence": float(prom[i]) if i < len(prom) else 0.0,
            "width_pts": float(widths[i]) if i < len(widths) else 0.0,
            "fwhm_nm": float(widths[i]) * step if i < len(widths) else 0.0,
            "left_ips": float(left_ips[i]) if i < len(left_ips) else 0.0,
            "right_ips": float(right_ips[i]) if i < len(right_ips) else 0.0,
        })
    return peaks, info


def estimate_noise(intensity):
    """简单噪声估计：取强度差分绝对值的中位数。"""
    if intensity is None or len(intensity) < 4:
        return 0.0
    d = np.abs(np.diff(np.asarray(intensity, dtype=float)))
    return float(np.median(d))
