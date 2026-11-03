# Phần 3 – Kiểm thử tự động backend (Nhóm 10)

**Nhánh đề xuất:** `test/phien-va-so-do-qr`

## Phạm vi

Thêm `test_phien_va_so_do_qr.py` tại **thư mục gốc** repo, ngang `app.py` và `test_completion_flow.py`. Giữ nguyên các file backend và những test hiện có.

File mới dùng `unittest`, Flask `test_client` và **database SQLite tạm** từ fixture có sẵn trong `test_completion_flow.py`. Không sửa `instance/smartlogistics.db`.

Các tình huống:

1. Đang có lượt chờ: API đóng phiên trả `409 session_busy`, không phát sinh lịch sử.
2. Phiên đã đóng: API chuẩn bị lượt mới trả `409 session_closed`.
3. Gửi số đo QR hợp lệ: lưu một bản ghi; gọi lại `complete` không tạo lịch sử hoặc sửa số đo.
4. Nhập thủ công: hoàn tất bình thường nhưng không tạo bản ghi `qr_measurements`.
5. Nhập thủ công mà cố gửi số đo QR: trả lỗi `400 invalid_input`, không ghi dữ liệu; vẫn có thể hoàn tất lại hợp lệ.
6. Số đo âm, chuỗi, bool, NaN, infinity, sai mode/hash, pipeline thiếu nhất quán, trường thừa, thiếu lý do gián đoạn: `400 invalid_measurement`; không ghi lịch sử hoặc số đo.
7. Số đo QR gián đoạn (`valid=false`) có lý do: lưu dấu `invalid`, thời gian có thể để `null`.
8. Body `complete` sai cấu trúc: `400 invalid_input`, không ghi dữ liệu.

## Chạy tại VS Code / PowerShell

Mở Terminal **đúng thư mục có `app.py` và `requirements.txt`**, rồi dùng môi trường `.venv` đã cài. Nếu `.venv` nằm thư mục cha thì thay đường dẫn lệnh Python bằng `..\.venv\Scripts\python.exe`.

```powershell
python -m unittest -v test_phien_va_so_do_qr.py
```

Hoặc dùng Python trong môi trường:

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_phien_va_so_do_qr.py
```

Chạy toàn bộ test backend hiện có:

```powershell
python -m unittest -v test_completion_flow.py test_concurrent_requests.py test_destination_errors.py test_phien_va_so_do_qr.py
```

> **Lưu ý:** Một số test gốc (`test_destination_errors`, `test_concurrent_requests`) **đọc** database chính để sao chép sang database tạm. Vì thế để chạy cả bộ phải khởi tạo database bằng phần 2 từ trước. Riêng file test mới sử dụng fixture tự khởi tạo, không cần database chính.

## Ghi nhận nghiệm thu

Khi chạy xong, lưu **kết quả Terminal thật** (không điền PASS trước khi chạy). Các thông tin cần lưu: thời điểm, Python version, lệnh đã chạy, số test, số lỗi, trạng thái `OK/FAILED`, bản commit.

Ví dụ mẫu cấu trúc kết quả:

```text
Lệnh: python -m unittest -v test_phien_va_so_do_qr.py
Kết quả: [điền sau khi chạy]
Số test: [điền sau khi chạy]
Thời gian: [điền sau khi chạy]
```

Nếu lỗi xuất hiện, không tự sửa API backend trong nhánh test. Ghi thông báo lỗi, bước tái hiện, kỳ vọng và kết quả thực tế; mở Issue để thành viên phụ trách backend xử lý.

## An toàn dữ liệu

Không xóa/chỉnh sửa `instance/smartlogistics.db`. Không commit `.venv/`, file `.db`, bản backup hay báo cáo sinh tự động. Trước Pull Request, kiểm tra `Files changed` chỉ có file test mới (và hướng dẫn nếu nhóm yêu cầu).
