# Smart Logistics – Nhóm 10

Đồ án mô phỏng phân loại kiện hàng bằng mã QR tại một trạm,
gồm một băng tải và ba cửa phân loại.

## Công nghệ

- Giao diện: HTML, CSS, JavaScript; jsQR đọc mã QR trên trình duyệt.
- Backend: Python, Flask.
- Cơ sở dữ liệu: SQLite, lưu tại `instance/smartlogistics.db`.
- Không cần cài máy chủ MySQL.

## Dữ liệu và quy tắc

Dữ liệu ứng dụng gồm 60 kiện, chia thành hai bộ độc lập:

- `demo`: 30 kiện để phát triển và trình diễn.
- `final_test`: 30 kiện dành cho đánh giá cuối.

Dữ liệu tham chiếu nằm trong `data/reference/`.
Mã kiện và quy tắc phân cửa được tạo cho mô phỏng của nhóm.

| Điểm đến | Bang | Cửa |
|---|---|---|
| São Paulo | SP | 1 |
| Rio de Janeiro | RJ | 2 |
| Belo Horizonte | MG | 3 |

## Cài đặt lần đầu trên Windows

Mở PowerShell tại thư mục project. Máy cần có Python và pip.

Tạo môi trường riêng và cài thư viện:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Chuẩn bị dữ liệu và database, chạy lần lượt.
Nếu một lệnh báo lỗi, xử lý lỗi trước khi chạy lệnh tiếp theo:

```powershell
.\.venv\Scripts\python.exe chuan_bi_du_lieu_ung_dung.py
.\.venv\Scripts\python.exe init_db.py
.\.venv\Scripts\python.exe init_tracking.py
.\.venv\Scripts\python.exe nang_cap_xu_ly.py
```

Khởi động web:

```powershell
.\.venv\Scripts\python.exe app.py
```

Mở http://127.0.0.1:5000 trong trình duyệt.
Có thể kiểm tra kết nối database tại http://127.0.0.1:5000/api/health.

## Các lần chạy tiếp theo

Sau khi đã cài đặt và khởi tạo đầy đủ, chỉ cần chạy:

```powershell
.\.venv\Scripts\python.exe app.py
```

Nhấn Ctrl + C trong terminal để dừng web.

## Luồng xử lý

1. Tạo hoặc chọn phiên đang hoạt động.
2. Đọc ảnh QR hoặc nhập mã kiện.
3. Backend kiểm tra mã, dữ liệu, quy tắc và kiện trùng trong phiên.
4. Giao diện mô phỏng kiện di chuyển đến cửa.
5. Gọi API hoàn tất để lưu kết quả và số đo QR nếu có.
6. Đóng phiên sau khi mọi lượt đã hoàn tất.

API sử dụng hai bước `prepare` và `complete`.
Gửi lại cùng request ID không tạo thêm bản ghi lịch sử.

## Số đo và báo cáo

- Thời gian quyết định của backend khác thời gian xử lý QR trên trình duyệt.
- `pipeline_ms` không bao gồm thời gian hoạt ảnh.
- Khi tổng hợp thời gian, phải phân biệt số đo hợp lệ và bị gián đoạn.
- Chưa suy ra độ chính xác đọc QR hoặc năng suất toàn hệ thống
  chỉ từ các lượt phân loại thành công.

Các công cụ hỗ trợ gồm `xuat_va_doi_chieu.py`,
`do_phan_loai_thu_cong.py` và `tong_hop_danh_gia.py`.

## Làm việc nhóm

Mỗi thành viên làm trên nhánh riêng, push nhánh và tạo Pull Request.
Nhánh `main` được bảo vệ; thay đổi được kiểm tra trước khi hợp nhất.

## File cục bộ

Môi trường `.venv/`, database, bản sao lưu, dữ liệu thô trong
`data/raw/` và báo cáo phát sinh trong `reports/` được bỏ qua bởi Git.
Mỗi máy tự khởi tạo database theo hướng dẫn ở trên.