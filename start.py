"""快速启动脚本 —— python start.py"""
import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("HIVE_PORT", "8765"))
    uvicorn.run(
        "greyfield_hive.main:app",
        host="0.0.0.0",
        port=port,
        reload=os.environ.get("HIVE_DEV", "0") == "1",
        log_level="info",
    )
