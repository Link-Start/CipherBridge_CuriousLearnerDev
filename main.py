"""入口 — 使用新架构.

命令行:
  mitmdump -s main.py -p 8080

Profile 匹配 → 自动加载对应插件.
"""

import sys, os, logging

sys.path.insert(0, os.path.dirname(__file__))
logging.basicConfig(level=logging.INFO, format="%(message)s")

from core.mitm_engine import MitmEngine
addons = [MitmEngine()]
