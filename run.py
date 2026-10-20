# -*- coding: utf-8 -*-
"""启动入口：python run.py"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from libs_analyzer.main_window import main

if __name__ == "__main__":
    raise SystemExit(main())
