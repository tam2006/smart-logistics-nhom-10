# Phần 2 – Khởi tạo project bằng một lệnh

**Nhánh:** `feature/khoi-tao-project`  
**Dự án:** Smart Logistics – Nhóm 10

## 1. Mục tiêu

Tạo `khoi_tao_project.py` để kiểm tra dữ liệu nguồn rồi chạy bốn chương trình **đúng thứ tự**, dùng **đúng Python hiện hành**, dừng ngay khi có lỗi và không ghi đè/xóa database cũ.

1. `chuan_bi_du_lieu_ung_dung.py`
2. `init_db.py`
3. `init_tracking.py`
4. `nang_cap_xu_ly.py`

Đường dẫn database của repo: `instance/smartlogistics.db`.

## 2. Cài đặt (Windows PowerShell, tại thư mục gốc repo)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 3. Chạy khởi tạo độc lập – nghiệm thu đúng yêu cầu phần 2

Khi database **chưa tồn tại**:

```powershell
.\.venv\Scripts\python.exe khoi_tao_project.py
```

Chương trình kiểm tra sự tồn tại các file Python và `requirements.txt`, đọc CSV tại `data/reference/demo/parcels.csv` và `data/reference/final_test/parcels.csv`, đảm bảo mỗi bộ có đúng 30 kiện, không thiếu cột/trường quan trọng, không trùng mã kiện/mã đơn và điểm đến thuộc ba quy tắc phân loại hiện có. Sau đó thực thi 4 bước bằng `sys.executable` với thư mục làm việc là thư mục project. Nếu bất kỳ bước nào lỗi, in số thứ tự, tên bước và mã thoát, rồi dừng.

Nếu **database đã tồn tại**, lệnh độc lập trả về mã lỗi `1` và giữ nguyên database. **Không xóa database thật để thử nghiệm.**

## 4. Tích hợp để nhóm trưởng chỉ chạy app.py

Trong `app.py`, tại phần cuối `if __name__ == "__main__":`, gọi `dam_bao_san_sang_cho_web()` **trước** `app.run()` theo nội dung file `app_integration.patch` kèm theo. Sau khi nhóm trưởng duyệt bản sửa `app.py`, người dùng chạy:

```powershell
.\.venv\Scripts\python.exe app.py
```

- Database chưa có: tự khởi tạo 4 bước rồi mở web.
- Database tồn tại và đầy đủ: sử dụng trực tiếp, không gọi 4 bước.
- Database đã tồn tại nhưng thiếu bảng/bị lỗi: dừng an toàn và hướng dẫn xử lý, không chỉnh sửa/xóa.

Mở `http://127.0.0.1:5000`, kiểm tra `http://127.0.0.1:5000/api/health`: mong đợi JSON có `status: "ok"`, `database: "connected"`, `parcels: 60`, `routing_rules: 3`, `sessions: 0`, `history: 0` khi chưa chạy phiên nào. Chỉ số phiên/lịch sử có thể lớn hơn 0 khi đã vận hành.

## 5. Kiểm thử nghiệm thu

**Thực hiện trên bản sao thư mục dự án riêng**, không thử lỗi trên database đang sử dụng.

| Mã | Điều kiện | Kết quả mong đợi |
|---|---|---|
| TC01 | Database chưa có, dữ liệu đầy đủ | Chạy đủ 4 bước, tạo DB, kiểm tra cấu trúc thành công |
| TC02 | Thiếu một CSV nguồn | Báo chính xác đường dẫn thiếu, chưa chạy bước 1 |
| TC03 | Một CSV có ít/hơn 30 kiện | Báo bộ dữ liệu không đủ 30; chưa tạo DB |
| TC04 | Trùng `code` hoặc `order_id` giữa 2 bộ | Báo mã trùng; chưa tạo DB |
| TC05 | Database đã tồn tại (chạy lệnh khởi tạo riêng) | Báo lỗi, thoát mã `1`, DB giữ nguyên |
| TC06 | Thiếu một file `.py` trong 4 file | Báo tên file thiếu; chưa tạo DB |
| TC07 | Một bước trả mã lỗi khác `0` | Dừng ngay, in bước/mã lỗi; không chạy bước tiếp |
| TC08 | Mở `app.py` với DB hợp lệ | Không khởi tạo lại, web chạy bình thường |
| TC09 | Mở `app.py` với DB thiếu bảng | Báo lỗi, không sửa/xóa DB, web không khởi động |
| TC10 | DB chưa có, mở `app.py` | Tự khởi tạo, sau đó web chạy; `/api/health` báo `ok` |

**Lưu ý:** Bước `nang_cap_xu_ly.py` vốn tự tạo bản sao lưu SQLite. File điều phối không can thiệp hay xóa bản sao lưu này. Nếu khởi tạo lỗi sau bước 2, database tạo dở được giữ nguyên để người phụ trách kiểm tra; lần chạy sau sẽ bị chặn, tránh ghi đè dữ liệu.

## 6. Bàn giao

- `khoi_tao_project.py` (code mới)
- `docs/khoi-tao.md` (hướng dẫn và test case)
- `app_integration.patch` (đề xuất chỉnh sửa rất nhỏ vào `app.py`, cần nhóm trưởng duyệt)

Trước khi tạo Pull Request: chạy thử trong thư mục clone mới, lưu ảnh terminal của TC01/TC05, ảnh `/api/health`, rồi gửi PR `feature/khoi-tao-project` → `main`.
