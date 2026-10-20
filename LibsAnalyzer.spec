# -*- mode: python ; coding: utf-8 -*-

import os

from PyInstaller.utils.hooks import collect_all

# Pillow：matplotlib 保存 PNG 时间接依赖，须完整收集 C 扩展/DLL
pil_datas, pil_binaries, pil_hiddenimports = collect_all('PIL')

# Anaconda 运行库：Pillow _imaging 等 C 扩展依赖 Library\bin 下的
# 独立 DLL（libjpeg/zlib/libtiff/libpng/libwebp…），一并打包
CONDA_BIN = r"C:\ProgramData\Anaconda3\Library\bin"
conda_dlls = []
if os.path.isdir(CONDA_BIN):
    conda_dlls = [(os.path.join(CONDA_BIN, f), ".") for f in os.listdir(CONDA_BIN)
                  if f.lower().endswith(".dll")]
    print(f"[spec] 收集 conda DLL: {len(conda_dlls)} 个")


a = Analysis(
    ['run.py'],
    pathex=['.'],
    binaries=pil_binaries + conda_dlls,
    datas=pil_datas,
    hiddenimports=pil_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 本软件未使用的 Qt 模块（PyQt5 全量 hook 会收集，排除以缩小体积/加快构建）
        'PyQt5.QtWebEngineCore', 'PyQt5.QtWebEngineWidgets',
        'PyQt5.QtWebChannel', 'PyQt5.QtQml', 'PyQt5.QtQuick',
        'PyQt5.QtQuickWidgets', 'PyQt5.QtMultimedia',
        'PyQt5.QtMultimediaWidgets', 'PyQt5.QtSql', 'PyQt5.QtTest',
        'PyQt5.QtXmlPatterns', 'PyQt5.QtDesigner', 'PyQt5.QtHelp',
        'PyQt5.QtOpenGL', 'PyQt5.QtPrintSupport', 'PyQt5.QtBluetooth',
        'PyQt5.QtNfc', 'PyQt5.QtLocation', 'PyQt5.QtSensors',
        'PyQt5.QtSerialPort', 'PyQt5.QtPositioning',
        # 未使用的科学库
        'tkinter', 'PyQt5.QtDBus',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LibsAnalyzer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['resources/icon.ico'],
)
