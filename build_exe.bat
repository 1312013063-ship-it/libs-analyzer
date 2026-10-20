@echo off
rem ============================================================
rem  Libs通用测试软件 - PyInstaller 免安装版打包脚本
rem  用法: build_exe.bat
rem  产物: dist\LibsAnalyzer\LibsAnalyzer.exe（免安装，双击即用）
rem  说明: 收集 PIL 全部资源并补充 conda 版 Pillow 依赖的 DLL
rem        （_imaging.pyd 需要 zlib/tiff/openjp2/freetype 等）
rem ============================================================
setlocal

set PY=C:\ProgramData\Anaconda3\python.exe
set DLLDIR=C:\ProgramData\Anaconda3\Library\bin

%PY% -m PyInstaller --noconfirm --clean --windowed --name LibsAnalyzer ^
  --collect-all PIL ^
  --add-binary "%DLLDIR%\zlib.dll;." ^
  --add-binary "%DLLDIR%\zlib-ng2.dll;." ^
  --add-binary "%DLLDIR%\libjpeg.dll;." ^
  --add-binary "%DLLDIR%\libpng16.dll;." ^
  --add-binary "%DLLDIR%\libtiff.dll;." ^
  --add-binary "%DLLDIR%\tiff.dll;." ^
  --add-binary "%DLLDIR%\libwebp.dll;." ^
  --add-binary "%DLLDIR%\libwebpdecoder.dll;." ^
  --add-binary "%DLLDIR%\libwebpdemux.dll;." ^
  --add-binary "%DLLDIR%\libwebpmux.dll;." ^
  --add-binary "%DLLDIR%\zopflipng.dll;." ^
  --add-binary "%DLLDIR%\lcms2.dll;." ^
  --add-binary "%DLLDIR%\openjp2.dll;." ^
  --add-binary "%DLLDIR%\freetype.dll;." ^
  --add-binary "%DLLDIR%\Qt5Core_conda.dll;." ^
  --add-binary "%DLLDIR%\Qt5Gui_conda.dll;." ^
  --add-binary "%DLLDIR%\Qt5Widgets_conda.dll;." ^
  --add-binary "%DLLDIR%\Qt5Network_conda.dll;." ^
  --add-binary "%DLLDIR%\Qt5PrintSupport_conda.dll;." ^
  --add-binary "%DLLDIR%\Qt5Svg_conda.dll;." ^
  --add-binary "%DLLDIR%\Qt5Xml_conda.dll;." ^
  --add-binary "%DLLDIR%\Qt5OpenGL_conda.dll;." ^
  --add-binary "%DLLDIR%\Qt5WinExtras_conda.dll;." ^
  --exclude-module tkinter ^
  --exclude-module IPython ^
  --exclude-module pytest ^
  run.py

if errorlevel 1 (
  echo [打包失败] 请检查上方 PyInstaller 输出
  exit /b 1
)
echo [打包成功] dist\LibsAnalyzer\LibsAnalyzer.exe
endlocal
