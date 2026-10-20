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
AI 无效脉冲识别引擎（本地规则驱动，离线可用）

LIBS 一次测量 = 多次激光脉冲，每个脉冲是一条谱图。
本模块对每条脉冲谱图做质量评估：
  - 信号饱和 / 弱信号（未击穿）/ 背景噪声过高 / 数据异常（NaN·全零）
  - 光谱漂移 / 特征峰过少 / 脉冲间一致性差
  - 输出：健康度评分（0-100）+ 判定（有效/疑似/无效）+ 原因 + 改进建议
所有原始脉冲谱图如实保留（本模块只评估与标记，不删除数据）。

用法：
    from .pulse_quality import analyze_pulses, average_valid_pulses, PulseData
"""
import numpy as np

from .peak_detect import detect_peaks

# 检测参数（可调，默认值经演示数据验证）
PARAMS = {
    "sat_level": 60000.0,        # 探测器饱和阈值（强度）
    "near_sat_frac": 0.003,      # 强度>0.7×sat 的采样点占比超此值 → 接近饱和
    "weak_frac": 0.10,           # 峰值 < 参考强度的该比例 → 弱信号（未击穿）
    "weak_warn_frac": 0.25,      # 峰值 < 该比例 → 偏弱
    "noise_ratio": 8.0,          # 背景噪声 std > 参考噪声 ×该倍数 → 噪声过高
    "corr_low": 0.90,            # 与参考谱相关系数低于此 → 不一致
    "corr_bad": 0.80,            # 低于此 → 严重不一致
    "min_peaks": 3,              # 特征峰数低于此 → 疑似未击穿
    "drift_nm": 0.60,            # 最强峰位置相对参考偏移超此 → 漂移
}

# 判定分级阈值
SCORE_VALID = 70.0      # ≥70 有效
SCORE_SUSPECT = 40.0    # 40-69 疑似，<40 无效


class PulseData:
    """一组脉冲谱图：共享波长，每行一条脉冲。"""

    def __init__(self, wl, intensities, names=None):
        wl = np.asarray(wl, dtype=float)
        intensities = np.asarray(intensities, dtype=float)
        if intensities.ndim == 1:
            intensities = intensities.reshape(1, -1)
        if wl.shape[0] != intensities.shape[1]:
            raise ValueError("波长长度与脉冲数据点数不一致")
        self.wl = wl
        self.intensities = intensities
        self.n_pulses = intensities.shape[0]
        if names is None:
            names = [f"P{i + 1}" for i in range(self.n_pulses)]
        if len(names) != self.n_pulses:
            names = [f"P{i + 1}" for i in range(self.n_pulses)]
        self.names = list(names)

    def pulse(self, i):
        return self.wl, self.intensities[i]

    @property
    def mean_spectrum(self):
        """全部脉冲逐点平均（含无效脉冲；分析用请走 average_valid_pulses）。"""
        return self.wl, np.nanmean(self.intensities, axis=0)

    def __repr__(self):
        return f"<PulseData {self.n_pulses}脉冲 × {len(self.wl)}点>"


class PulseVerdict:
    """单条脉冲的质量判定结果。"""

    __slots__ = ("index", "name", "score", "level", "issues",
                 "n_peaks", "max_intensity", "corr", "drift_nm",
                 "user_mark")

    def __init__(self, index, name, score, level, issues,
                 n_peaks, max_intensity, corr, drift_nm):
        self.index = index
        self.name = name
        self.score = score
        self.level = level                 # 有效 / 疑似 / 无效
        self.issues = issues               # [(原因, 改进建议), ...]
        self.n_peaks = n_peaks
        self.max_intensity = max_intensity
        self.corr = corr
        self.drift_nm = drift_nm
        self.user_mark = None              # None / "invalid" / "valid"

    @property
    def effective_valid(self):
        """综合 AI 判定与用户标记后的最终是否有效。"""
        if self.user_mark == "valid":
            return True
        if self.user_mark == "invalid":
            return False
        return self.level != "无效"

    def __repr__(self):
        return (f"<PulseVerdict {self.name} score={self.score:.0f} "
                f"level={self.level} valid={self.effective_valid}>")


def _background_noise(intensity):
    """鲁棒噪声估计：相邻点差分的中位绝对偏差（MAD）×1.4826。

    对谱峰不敏感（峰占少数点，不影响中位数），
    对随机噪声敏感；不受信号截断（0 值堆积）影响。
    """
    if intensity.size < 4:
        return 0.0
    d = np.diff(np.asarray(intensity, dtype=float))
    if d.size == 0:
        return 0.0
    med = np.median(d)
    mad = np.median(np.abs(d - med))
    return float(mad * 1.4826)


def _strongest_peak_wl(wl, intensity, prom_frac=0.05):
    peaks_idx, _ = detect_peaks(wl, intensity,
                                prominence_frac=prom_frac,
                                min_width_pts=2)
    if len(peaks_idx) == 0:
        return None
    best = max(peaks_idx, key=lambda i: intensity[i])
    return float(wl[best])


def _cross_corr_shift(y, ref, max_shift_pts=60):
    """
    用归一化互相关检测 y 相对 ref 的整体平移（点数，正=右移）。
    返回 (shift_pts, best_corr)；信号异常时返回 (None, None)。
    """
    n = len(y)
    yv = y - np.mean(y)
    rv = ref - np.mean(ref)
    ys, rs = np.std(yv), np.std(rv)
    if ys <= 0 or rs <= 0:
        return None, None
    yv = yv / ys
    rv = rv / rs
    best_shift, best_corr = 0, float(np.mean(yv * rv))
    for s in range(1, max_shift_pts + 1):
        c1 = float(np.mean(yv[s:] * rv[:-s]))   # y 右移 s
        c2 = float(np.mean(yv[:-s] * rv[s:]))   # y 左移 s
        if c1 > best_corr:
            best_corr, best_shift = c1, s
        if c2 > best_corr:
            best_corr, best_shift = c2, -s
    return best_shift, best_corr


def analyze_pulses(pulse_data, params=None):
    """
    对一组脉冲做 AI 质量评估，返回 [PulseVerdict]（顺序与脉冲一致）。
    """
    p = dict(PARAMS)
    if params:
        p.update(params)

    wl = pulse_data.wl
    mat = pulse_data.intensities
    n = pulse_data.n_pulses
    if n == 0:
        return []

    # 参考谱：中位数谱（稳健，不受个别异常脉冲影响）
    ref = np.median(mat, axis=0)
    ref_max = float(np.nanmax(ref)) if np.isfinite(ref).all() else 1.0
    ref_noise = _background_noise(ref)
    ref_peak_wl = _strongest_peak_wl(wl, ref)
    if ref_max <= 0:
        ref_max = 1.0
    if ref_noise <= 0:
        ref_noise = 1e-9
    step_nm = float(wl[1] - wl[0]) if len(wl) > 1 else 0.1

    verdicts = []
    for i in range(n):
        y = mat[i]
        issues = []
        max_i = float(np.nanmax(y)) if np.size(y) else 0.0
        total_pts = y.size

        # 1) 数据异常（NaN/Inf/全零/负值过多）
        bad = (~np.isfinite(y)).sum()
        neg = (y < 0).sum()
        if bad / max(total_pts, 1) > 0.02 or max_i <= 0:
            issues.append(("数据异常（NaN/Inf/全零）",
                           "重新采集该脉冲，检查数据传输完整性；"
                           "若频繁出现请检修采集卡/软件接口。"))
            score = 0.0
            n_peaks = 0
            corr = 0.0
            drift = None
            verdicts.append(PulseVerdict(
                i, pulse_data.names[i], score, "无效", issues,
                n_peaks, max_i, corr, drift))
            continue
        if neg / max(total_pts, 1) > 0.05:
            issues.append(("负值基线过多（暗电流扣除异常）",
                           "检查暗电流/本底扣除设置，必要时重新采集本底。"))

        # 2) 信号饱和
        sat_pts = (y >= p["sat_level"]).sum()
        near_pts = (y >= 0.7 * p["sat_level"]).sum()
        if sat_pts > 0:
            issues.append(("信号饱和（探测器满量程）",
                           "降低激光能量或增大样品距离；加中性衰减片；"
                           "避免长时间连续激发同一位置。"))
        elif near_pts / max(total_pts, 1) > p["near_sat_frac"]:
            issues.append(("接近饱和（存在削顶风险）",
                           "适当降低激光能量或缩短积分时间，"
                           "保留峰形线性动态范围。"))

        # 3) 弱信号 / 未击穿
        if max_i < p["weak_frac"] * ref_max:
            issues.append(("弱信号 / 疑似未击穿",
                           "增大激光能量；重新对焦使光斑对准样品表面；"
                           "清洁/抛光样品表面；检查镜头与样品的距离。"))
        elif max_i < p["weak_warn_frac"] * ref_max:
            issues.append(("信号偏弱",
                           "适当增大激光能量或优化聚焦，提升信噪比。"))

        # 4) 背景噪声过高
        noise = _background_noise(y)
        if noise > p["noise_ratio"] * ref_noise:
            issues.append(("背景噪声过高",
                           "清洁透镜与窗口片；检查氩气吹扫流量与气氛；"
                           "遮蔽环境杂散光；检查高压/电磁干扰。"))

        # 5) 特征峰过少
        peaks_idx, _ = detect_peaks(wl, y, prominence_frac=0.03,
                                    min_width_pts=2)
        n_peaks = len(peaks_idx)
        if n_peaks < p["min_peaks"]:
            issues.append(("特征峰过少（疑似未击穿或聚焦不准）",
                           "重新对焦；确认样品在测量窗口正前方；"
                           "检查是否对到空气/支架而非样品。"))

        # 6) 脉冲间一致性 + 7) 光谱漂移（互相关对齐后综合判定）
        if np.std(y) > 0:
            corr = float(np.corrcoef(y, ref)[0, 1])
        else:
            corr = 0.0
        if not np.isfinite(corr):
            corr = 0.0
        shift_pts, aligned_corr = _cross_corr_shift(y, ref)
        drift = None
        if (shift_pts is not None and shift_pts != 0
                and aligned_corr is not None and aligned_corr >= 0.85):
            drift = round(abs(shift_pts) * step_nm, 3)
            if drift >= p["drift_nm"]:
                issues.append(("光谱漂移（谱峰整体偏移 "
                               f"{drift:.2f}nm）",
                               "执行波长校准；检查仪器热稳定时间；"
                               "避免温度快速变化。"))
        else:
            if corr < p["corr_bad"]:
                issues.append(("与其他脉冲严重不一致",
                               "样品表面不均匀或激光未稳定耦合；"
                               "移动样品重测；检查激光能量稳定性。"))
            elif corr < p["corr_low"]:
                issues.append(("与其他脉冲一致性偏低",
                               "样品表面可能不均或有杂质；建议复测该点。"))

        # 评分：100 - 每类问题扣分（每类只按最严重项扣一次）
        deductions = [
            ("信号饱和", 65),
            ("接近饱和", 15),
            ("弱信号", 45),
            ("信号偏弱", 15),
            ("背景噪声过高", 25),
            ("特征峰过少", 25),
            ("严重不一致", 40),
            ("一致性偏低", 20),
            ("光谱漂移", 40),
            ("负值基线过多", 10),
        ]
        score = 100.0
        for reason, _ in issues:
            for key, d in deductions:
                if key in reason:
                    score -= d
                    break
        score = max(0.0, min(100.0, score))

        level = "有效" if score >= SCORE_VALID else (
            "疑似" if score >= SCORE_SUSPECT else "无效")
        verdicts.append(PulseVerdict(
            i, pulse_data.names[i], score, level, issues,
            n_peaks, max_i, corr, drift))
    return verdicts


def average_valid_pulses(pulse_data, verdicts=None):
    """
    排除无效脉冲（AI 判定无效或用户标记无效）后逐点平均，
    返回 SpectrumData（含全部有效脉冲的均值谱）。
    """
    from .data_io import SpectrumData
    if verdicts is None:
        verdicts = analyze_pulses(pulse_data)
    valid_idx = [v.index for v in verdicts if v.effective_valid]
    if not valid_idx:
        # 全部无效时退化为中位数谱（不丢弃任何数据，n_valid=0 供提示）
        avg = np.median(pulse_data.intensities, axis=0)
        return SpectrumData(pulse_data.wl, avg, name="中位数谱（全部脉冲无效）"), 0
    sub = pulse_data.intensities[valid_idx]
    avg = np.nanmean(sub, axis=0)
    name = f"{pulse_data.n_pulses} 脉冲平均（有效 {len(valid_idx)}）"
    return SpectrumData(pulse_data.wl, avg, name=name), len(valid_idx)


def pulse_summary(verdicts):
    """生成 AI 汇总文本：总体结论 + 无效脉冲改进方向。"""
    n_valid = sum(1 for v in verdicts if v.effective_valid)
    n_suspect = sum(1 for v in verdicts if v.level == "疑似")
    n_invalid = sum(1 for v in verdicts if v.level == "无效")
    lines = [f"共 {len(verdicts)} 个脉冲：有效 {n_valid} / "
             f"疑似 {n_suspect} / 无效 {n_invalid}（AI 判定）。"]

    if n_invalid == 0 and n_suspect == 0:
        lines.append("所有脉冲质量良好，无需剔除。")
    else:
        # 统计无效/疑似原因，汇总改进方向
        cause_count = {}
        for v in verdicts:
            if v.level == "无效":
                for reason, _ in v.issues:
                    cause_count[reason] = cause_count.get(reason, 0) + 1
        if cause_count:
            top = sorted(cause_count.items(), key=lambda kv: -kv[1])[:3]
            lines.append("无效脉冲主要原因：" + "；".join(
                f"{k}（{v} 个）" for k, v in top))
            lines.append("改进方向：" +
                         "；".join(set(
                             adv for _, issues in
                             ((v, v.issues) for v in verdicts
                              if v.level == "无效")
                             for _, adv in issues)))
        else:
            lines.append("存在疑似脉冲，建议复测确认后手动标记。")
    return "\n".join(lines)
