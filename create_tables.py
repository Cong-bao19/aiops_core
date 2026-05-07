from app.db.database import engine, Base
# Bắt buộc phải import model vào thì SQLAlchemy mới nhận diện được để tạo
from app.models import alert_model 

print("⏳ Đang kết nối tới PostgreSQL...")

# Lệnh này sẽ quét toàn bộ các class kế thừa từ Base và tạo bảng
Base.metadata.create_all(bind=engine)

print("✅ Đã tạo xong toàn bộ các bảng trong Database 'aiops_db'!")