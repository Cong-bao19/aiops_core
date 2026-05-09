from app.db.database import engine, Base
from app.models import alert_model 

print("Đang kết nối tới PostgreSQL...")

Base.metadata.create_all(bind=engine)

print(" Đã tạo xong toàn bộ các bảng trong Database 'aiops_db'")