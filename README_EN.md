# Libs General Testing Software (Libs通用测试软件)

A desktop **Laser-Induced Breakdown Spectroscopy (LIBS)** analysis application built with **PyQt5** — one-stop workflow from spectrum loading and element identification to quantitative calibration, alloy grade matching, AI-powered insight graphs, and invalid-pulse screening. Interface and features are modeled after the **SciAps Z-902** handheld LIBS analyzer, with a dark industrial theme.

> ⚠️ This repository contains **no** SciAps trademarks, logos, or official assets. The software is provided "as is"; analysis results are for scientific reference only.

## ✨ Features

| Module | Description |
|---|---|
| Spectrum Analysis | Wavelength–intensity plots, tunable peak detection, matching against a 40-element NIST line library with on-plot annotations |
| Multi-Pulse Screening | **All raw pulse spectra are preserved as-is**; AI automatically flags invalid pulses (saturation / weak signal / high noise / spectral drift / inconsistency) and **suggests actionable improvements**; users can review each pulse, manually mark valid/invalid (overriding AI), and recompute the averaged spectrum |
| Quantitative Analysis | Calibration-curve method (equation / R² / standard error / 95% confidence interval); calibrations persist across sessions; back-calculates unknown-sample concentrations |
| Alloy Identification | Chemistry concentration table + Grade Match scoring (100-point) against 30+ common grades; user-defined grades supported |
| AI Insight Graph | Element-confidence scoring, material/base-metal inference, element–material relationship graph, confidence bars — fully offline rule-based engine |
| Data Management | Test history records, multi-measurement averaging (AVG/SD/RSD), QuickSort fast sorting, HTML reports, Excel template export |
| Profile Switching | Method profiles: operator / base metal / detection parameters / ND rule applied in one click |

## 🖥 Screenshots

| Main window | AI Insight Graph |
|---|---|
| ![Main](screenshots/main.png) | ![AI Graph](screenshots/ai_graph.png) |

| Multi-pulse loaded | Pulse Quality · AI Screening |
|---|---|
| ![Pulse loaded](screenshots/pulse_loaded.png) | ![Pulse quality](screenshots/pulse_quality.png) |

## 🚀 Quick Start

```bash
# 1. Install dependencies (Python 3.8+, Anaconda3 recommended)
pip install -r requirements.txt

# 2. Run
python run.py
```

On Windows you can also double-click `run.bat`. A demo spectrum and a test record are generated automatically on first launch.

## 📁 Project Structure

```
LIBS_Analyzer/
├── run.py / run.bat            # Entry points
├── libs_analyzer/              # Core modules (main window, line library, peak detection,
│                               #   data I/O, quant, grades, AI insight, pulse quality…)
├── tests/                      # Unit tests (65)
├── screenshots/                # Screenshots for the README
└── _selfcheck/                 # GUI smoke-test scripts (incl. real-window validation)
```

## ✅ Self-Check

- Unit tests: 65/65 pass (data / peak detection / matching / quant / grades / records / CE / AI insight / pulse quality)
- GUI smoke tests: Analyze / Results / Settings, AI graph, pulse screening, Excel & HTML export — all PASS

```bash
python -m unittest discover -s tests
```

## 📄 License

[GNU GPL v3](LICENSE) or (at your option) any later version. Modified redistributions must remain open source and retain this license notice.

---

## For Chinese Users

中文完整说明见 [README.md](README.md)（简体中文版）。功能、操作与许可说明一致，包含脉冲质量甄别、AI 分析图谱、定量定标等模块的详细用法。
