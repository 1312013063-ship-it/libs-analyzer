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
光谱数据读写：支持常见两列文本格式（波长, 强度），
分隔符自动识别（逗号 / 制表符 / 空格 / 分号），自动跳过表头。
"""
import os
import numpy as np


class SpectrumData:
    """一条光谱数据。"""

    def __init__(self, wl, intensity, name="未命名光谱"):
        wl = np.asarray(wl, dtype=float)
        intensity = np.asarray(intensity, dtype=float)
        if wl.shape != intensity.shape:
            raise ValueError("波长与强度数组长度不一致")
        self.wl = wl
        self.intensity = intensity
        self.name = name

    @property
    def n_points(self):
        return len(self.wl)

    @property
    def wl_range(self):
        if len(self.wl) == 0:
            return (0.0, 0.0)
        return (float(self.wl.min()), float(self.wl.max()))

    def __repr__(self):
        lo, hi = self.wl_range
        return f"<SpectrumData {self.name}: {self.n_points}点, {lo:.1f}-{hi:.1f} nm>"


def _parse_text(path):
    """读取文本并返回 (data_lines, skipped_rows)。"""
    encoding = "utf-8-sig"
    raw = None
    for enc in ("utf-8-sig", "gbk", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                raw = f.read()
            encoding = enc
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    if raw is None:
        raise ValueError(f"无法识别文件编码: {path}")

    data_lines = []
    skipped = []
    for i, line in enumerate(raw.splitlines()):
        line = line.strip()
        if not line:
            continue
        # 统一切分：逗号/制表符/分号/多空格均可作分隔符
        tokens = [t for t in line.replace(",", " ").replace("\t", " ").replace(";", " ").split(" ") if t]
        nums = []
        ok = True
        for t in tokens:
            try:
                nums.append(float(t))
            except ValueError:
                ok = False
                break
        if ok and len(nums) >= 2:
            data_lines.append(nums)
        else:
            skipped.append(i + 1)
    return data_lines, skipped, encoding


def load_spectrum(path):
    """
    加载两列光谱文件（波长, 强度）。
    支持 .txt/.csv/.asc/.dat 等；第一列波长，第二列强度，
    多余列取前两列；自动跳过表头和非数字行。
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"文件不存在: {path}")

    data_lines, skipped, encoding = _parse_text(path)
    if len(data_lines) < 3:
        raise ValueError(
            f"有效数据点不足（仅 {len(data_lines)} 行）。"
            "请确认文件为两列数字：第一列波长(nm)，第二列强度。"
        )

    arr = np.array(data_lines, dtype=float)
    wl = arr[:, 0]
    intensity = arr[:, 1]

    # 排序去重，保证波长单调
    order = np.argsort(wl)
    wl = wl[order]
    intensity = intensity[order]
    keep = np.concatenate(([True], np.diff(wl) > 0))
    wl = wl[keep]
    intensity = intensity[keep]

    name = os.path.splitext(os.path.basename(path))[0]
    return SpectrumData(wl, intensity, name=name)


def save_spectrum_csv(path, spectrum):
    """把光谱另存为 CSV（波长,强度）。"""
    np.savetxt(path, np.column_stack([spectrum.wl, spectrum.intensity]),
               delimiter=",", fmt="%.4f,%.4f",
               header="wavelength_nm,intensity", comments="")


def save_peaks_csv(path, results):
    """导出峰检测/元素匹配结果 CSV。"""
    header = ("peak_no,wavelength_nm,intensity,fwhm_nm,"
              "element,element_cn,line_nm,delta_nm,rel_intensity")
    rows = []
    for r in results:
        rows.append((
            r["peak_no"], r["wl"], r["intensity"], r["fwhm_nm"],
            r.get("element", ""), r.get("element_cn", ""),
            r.get("line", ""), r.get("delta", ""), r.get("rel", ""),
        ))
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        f.write(header + "\n")
        for row in rows:
            f.write(",".join(str(v) for v in row) + "\n")


# ------------------------------------------------------------- 多脉冲导入
def load_pulse_series(path):
    """
    加载多脉冲文件（多列文本）：第一列波长，其余每列为一个脉冲的强度。

    支持 .csv/.txt/.asc/.dat；自动识别分隔符与表头；返回 PulseData。
    所有列原始数据如实保留。
    """
    from .pulse_quality import PulseData
    if not os.path.exists(path):
        raise FileNotFoundError(f"文件不存在: {path}")
    data_lines, skipped, _ = _parse_text(path)
    if len(data_lines) < 3:
        raise ValueError(
            f"有效数据点不足（仅 {len(data_lines)} 行）。"
            "多脉冲格式：第一列波长(nm)，其余每列一个脉冲的强度。")
    arr = np.array(data_lines, dtype=float)
    wl = arr[:, 0]
    mat = arr[:, 1:]
    if mat.shape[1] < 1:
        raise ValueError("未检测到脉冲列（至少需要 1 列强度）。")
    order = np.argsort(wl)
    wl = wl[order]
    mat = mat[order]
    keep = np.concatenate(([True], np.diff(wl) > 0))
    wl = wl[keep]
    mat = mat[keep]
    base = os.path.splitext(os.path.basename(path))[0]
    names = [f"{base}_P{i + 1}" for i in range(mat.shape[1])]
    return PulseData(wl, mat, names=names)


def load_pulse_folder(folder):
    """
    加载脉冲文件夹：目录下每个光谱文件视为一个脉冲。

    返回 PulseData（文件名去扩展名为脉冲名）。
    """
    from .pulse_quality import PulseData
    if not os.path.isdir(folder):
        raise NotADirectoryError(f"目录不存在: {folder}")
    files = sorted(
        f for f in os.listdir(folder)
        if f.lower().endswith((".txt", ".csv", ".asc", ".dat")))
    if not files:
        raise ValueError("目录内没有光谱文件（.txt/.csv/.asc/.dat）。")
    specs = []
    for f in files:
        specs.append(load_spectrum(os.path.join(folder, f)))
    wl = specs[0].wl
    mat = []
    for s in specs:
        if len(s.wl) != len(wl):
            raise ValueError(f"脉冲文件波长不一致: {f}")
        mat.append(s.intensity)
    return PulseData(wl, np.array(mat),
                     names=[os.path.splitext(f)[0] for f in files])


def save_pulses_csv(path, pulse_data):
    """把一组脉冲原始谱图导出为 CSV（波长 + 每列一个脉冲）。"""
    header = ["wavelength_nm"] + [f"pulse_{i + 1}"
                                  for i in range(pulse_data.n_pulses)]
    cols = [pulse_data.wl] + [pulse_data.intensities[i]
                              for i in range(pulse_data.n_pulses)]
    np.savetxt(path, np.column_stack(cols),
               delimiter=",", fmt="%.4f",
               header=",".join(header), comments="")
