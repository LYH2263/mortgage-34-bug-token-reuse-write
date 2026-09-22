import os
import tempfile

# 必须在任何 app.* 模块导入前指定独立的测试数据库：
# app.config / app.db 在导入时即绑定 DATA_DIR 并建目录。
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="mortgage-test-"))
