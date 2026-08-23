import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from app.database import init_db, SessionLocal
from app.seed import seed_data

if __name__ == "__main__":
    init_db()
    db = SessionLocal()
    try:
        seed_data(db)
        print("SaaS Pro 数据库初始化完成")
    finally:
        db.close()
