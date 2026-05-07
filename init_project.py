import os

# Định nghĩa cấu trúc thư mục và các file trống cần tạo
project_structure = {
    "app": [
        "__init__.py",
        "main.py"
    ],
    "app/controllers": ["__init__.py", "log_controller.py"],
    "app/services": ["__init__.py", "ai_service.py"],
    "app/repositories": ["__init__.py", "alert_repository.py"],
    "app/models": ["__init__.py", "alert_model.py"],
    "app/schemas": ["__init__.py", "alert_schema.py"],
    "app/db": ["__init__.py", "database.py"],
    "app/utils": ["__init__.py", "response_wrapper.py"],
}

# Tạo thư mục và file
for folder, files in project_structure.items():
    os.makedirs(folder, exist_ok=True)
    for file in files:
        file_path = os.path.join(folder, file)
        if not os.path.exists(file_path):
            with open(file_path, "w", encoding="utf-8") as f:
                pass # Chỉ tạo file rỗng

# Tạo các file ở thư mục gốc
root_files = ["requirements.txt", ".env"]
for file in root_files:
    if not os.path.exists(file):
        with open(file, "w", encoding="utf-8") as f:
            pass

print("✅ Đã tạo xong cấu trúc thư mục FastAPI chuẩn Doanh Nghiệp!")