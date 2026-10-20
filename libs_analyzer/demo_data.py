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
演示光谱生成：模拟典型 LIBS 光谱（多元素特征峰 + 连续背景 + 噪声），
方便在没有真实数据时体验软件功能。

背景强度按波长呈类黑体辐射形状，峰形为高斯（FWHM ~ 0.25-0.8 nm），
噪声含散粒噪声成分，接近真实 CCD 信号。
"""
import numpy as np

from .data_io import SpectrumData

# 演示用的典型元素特征线：(波长nm, 相对振幅比例)
_DEMO_LINES = [
    (247.86, 0.10),   # C
    (257.61, 0.25),   # Mn
    (259.37, 0.18),   # Mn
    (279.55, 0.20),   # Mg
    (285.21, 0.30),   # Mg
    (288.16, 0.28),   # Si
    (308.22, 0.22),   # Al
    (309.27, 0.30),   # Al
    (324.75, 0.35),   # Cu
    (327.40, 0.22),   # Cu
    (334.19, 0.20),   # Ti
    (357.87, 0.45),   # Cr
    (373.49, 0.60),   # Fe
    (373.71, 0.50),   # Fe
    (393.37, 0.90),   # Ca
    (396.85, 0.75),   # Ca
    (403.08, 0.30),   # Mn
    (405.78, 0.25),   # Pb
    (407.77, 0.28),   # Sr
    (421.55, 0.25),   # Sr
    (422.67, 0.55),   # Ca
    (438.35, 0.28),   # Fe
    (460.73, 0.22),   # Sr
    (489.15, 0.20),   # Fe
    (516.75, 0.25),   # Fe
    (518.36, 0.30),   # Mg
    (520.60, 0.22),   # Cr
    (588.99, 0.85),   # Na
    (589.59, 0.45),   # Na
    (616.22, 0.20),   # Ca
    (643.91, 0.35),   # Ca
    (656.28, 0.40),   # H
    (670.78, 0.30),   # Li
    (766.49, 0.65),   # K
    (769.90, 0.45),   # K
    (777.19, 0.35),   # O
]


def generate_demo_spectrum(wl_min=200.0, wl_max=900.0, step=0.1, seed=2026):
    """
    生成模拟 LIBS 光谱。

    返回 SpectrumData，波长单位 nm。
    """
    rng = np.random.default_rng(seed)
    wl = np.arange(wl_min, wl_max + step, step)

    # 连续背景（类黑体 + 轻微多项式漂移）
    baseline = (
        150.0
        + 260.0 * np.exp(-((wl - 660.0) ** 2) / (2.0 * 180.0 ** 2))
        + 0.12 * (wl - wl_min)
    )

    intensity = baseline.copy()

    # 元素特征峰（高斯）
    for line_wl, amp_scale in _DEMO_LINES:
        if not (wl_min < line_wl < wl_max):
            continue
        fwhm = float(rng.uniform(0.25, 0.75))
        sigma = fwhm / (2.0 * np.sqrt(2.0 * np.log(2.0)))
        amp = float(rng.uniform(0.6, 1.4)) * amp_scale * 14000.0
        intensity += amp * np.exp(-((wl - line_wl) ** 2) / (2.0 * sigma ** 2))

    # 散粒噪声 + 读出噪声
    shot = rng.normal(0.0, 1.0, size=wl.shape) * np.sqrt(np.maximum(intensity, 0.0)) * 1.6
    readout = rng.normal(0.0, 1.0, size=wl.shape) * 18.0
    intensity = np.maximum(intensity + shot + readout, 0.0)

    return SpectrumData(wl, intensity, name="演示光谱（模拟 LIBS）")


def _pulse_once(rng, wl, wl_min, noise_scale=1.0, amp_scale=1.0,
                wl_offset=0.0):
    """生成一个单脉冲谱（与 generate_demo_spectrum 同构，可复现）。"""
    baseline = (
        150.0
        + 260.0 * np.exp(-((wl - 660.0) ** 2) / (2.0 * 180.0 ** 2))
        + 0.12 * (wl - wl_min)
    )
    y = baseline.copy()
    for line_wl, amp_scale_base in _DEMO_LINES:
        lw = line_wl + wl_offset
        if not (200.0 < lw < 900.0):
            continue
        fwhm = float(rng.uniform(0.25, 0.75))
        sigma = fwhm / (2.0 * np.sqrt(2.0 * np.log(2.0)))
        amp = float(rng.uniform(0.6, 1.4)) * amp_scale_base * 14000.0 * amp_scale
        y += amp * np.exp(-((wl - lw) ** 2) / (2.0 * sigma ** 2))
    shot = rng.normal(0.0, 1.0, size=wl.shape) * np.sqrt(
        np.maximum(y, 0.0)) * 1.6 * noise_scale
    readout = rng.normal(0.0, 1.0, size=wl.shape) * 18.0 * noise_scale
    return np.maximum(y + shot + readout, 0.0)


def generate_demo_pulses(n_pulses=12, seed=9102):
    """
    生成模拟多脉冲 LIBS 数据（一次测量的多个激光脉冲）。

    故意包含典型无效/疑似脉冲，用于体验 AI 无效脉冲甄别：
      - 前 8 个：正常脉冲（脉冲间随机波动）
      - P9   ：信号饱和（削顶到探测器满量程）
      - P10  ：弱信号 / 疑似未击穿
      - P11  ：背景噪声过高
      - P12  ：光谱漂移（最强峰偏移，疑似）

    返回 PulseData（全部原始谱图如实保留）。
    """
    from .pulse_quality import PulseData
    rng = np.random.default_rng(seed)
    wl = np.arange(200.0, 900.1, 0.1)
    wl_min = 200.0

    pulses = []
    for _ in range(8):
        pulses.append(_pulse_once(rng, wl, wl_min))

    # P9 饱和：放大 4 倍后削顶
    sat = _pulse_once(rng, wl, wl_min, amp_scale=4.0)
    sat = np.clip(sat, 0.0, 65000.0)
    pulses.append(sat)

    # P10 弱信号
    weak = _pulse_once(rng, wl, wl_min, amp_scale=0.04)
    pulses.append(weak)

    # P11 高噪声
    noisy = _pulse_once(rng, wl, wl_min, noise_scale=25.0)
    pulses.append(noisy)

    # P12 光谱漂移：特征峰整体偏移 0.6nm（模拟波长漂移）
    drift = _pulse_once(rng, wl, wl_min, wl_offset=0.6)
    pulses.append(drift)

    mat = np.array(pulses, dtype=float)
    names = [f"P{i + 1}" for i in range(n_pulses)]
    return PulseData(wl, mat, names=names)

