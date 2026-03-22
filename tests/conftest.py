"""测试配置 —— 使用临时文件数据库，避免 SQLite :memory: 连接隔离问题"""

import os
import tempfile
import pytest

# 在任何 import 之前设置，确保 db.py 模块级代码使用测试路径
_tmpdir = tempfile.mkdtemp()
_test_db = os.path.join(_tmpdir, "test_hive.db")

os.environ["HIVE_DB_PATH"]       = _test_db
os.environ["HIVE_DATABASE_URL"]  = f"sqlite+aiosqlite:///{_test_db}"
