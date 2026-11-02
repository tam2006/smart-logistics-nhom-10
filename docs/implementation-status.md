## 6. Kết quả kiểm thử backend ngày 02/11/2026

Lệnh chạy:

python -m unittest -v test_completion_flow test_concurrent_requests test_destination_errors

Kết quả: 11 bài kiểm thử đạt, không có lỗi.

Đã kiểm chứng trong phạm vi bộ thử:

- Prepare chưa tạo lịch sử hoàn tất.
- Complete và gửi lại không nhân đôi lịch sử.
- Quét lại kiện không tăng số thành công.
- Khôi phục yêu cầu đang chờ.
- Chặn yêu cầu khác khi phiên đang bận.
- Từ chối request_id có nội dung xung đột.
- Chặn đóng phiên khi còn lượt chưa hoàn tất.
- Cho phép lấy lại kết quả cũ sau khi đóng phiên.
- Chặn yêu cầu mới trong phiên đã đóng.
- Xử lý yêu cầu đồng thời theo các kịch bản đã thử.
- Ghi nhận đúng các lỗi nghiệp vụ đã thử.
- Nâng cấp lặp lại và bản sao lưu giữ được lịch sử thử nghiệm.

Chưa bao phủ: xác thực số đo QR, hoàn tác khi ghi dữ liệu
thất bại, phân trang nhiều trang và hành vi giao diện trình duyệt.

Kết quả này không thay thế nghiệm thu toàn bộ F06–F09.