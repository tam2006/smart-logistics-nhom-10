# Cấu trúc công việc và tiến độ — Smart Logistics nhóm 10

Cập nhật: 07/11/2026  
Mốc đối chiếu source: `d39776e`

## 1. Mục đích và tài liệu liên quan

- [Define](project-description.md): Bài toán, phạm vi, yêu cầu và tiêu chí đánh giá.
- [Design](system-design.md): Kiến trúc, dữ liệu, API và luồng xử lý.
- Tài liệu này: Tiến độ, bằng chứng đã có và các bước còn lại.

Mã F01–F11 dùng thống nhất với Define và Design. Mỗi kết quả chỉ xác nhận
phạm vi đã thử. Code có trên nhánh riêng vẫn cần được kiểm tra trên bản chung.

## 2. Cấu trúc công việc

| Bước | Việc cần làm | Đầu ra |
|---|---|---|
| 1 | Xác định bài toán và yêu cầu | Define và tiêu chí nghiệm thu |
| 2 | Thiết kế dữ liệu, kiến trúc và luồng xử lý | Design |
| 3 | Chuẩn bị dữ liệu và triển khai chức năng | Ứng dụng chạy được, hai bộ dữ liệu và đáp án |
| 4 | Kiểm thử và tích hợp phần thành viên | Kết quả backend, giao diện và các tình huống lỗi |
| 5 | Chốt bản đánh giá | Kết quả tự động, đối chiếu đáp án và so sánh thủ công |
| 6 | Hoàn thiện báo cáo và demo | Báo cáo, slide và kịch bản trình bày |

## 3. Theo dõi yêu cầu chức năng

| Mã | Yêu cầu theo Define | Bằng chứng hiện có | Việc còn lại |
|---|---|---|---|
| F01 | Một trạm, một băng chuyền và ba cửa | Giao diện mô phỏng đã hiển thị ba cửa và điểm đến tương ứng. | Đưa vào kịch bản demo. |
| F02 | Đọc QR từ ảnh | Đã chạy luồng đọc ảnh trong phiên demo. | Đo riêng độ chính xác trên bộ `final_test`; thử ảnh không đọc được trên giao diện. |
| F03 | Nhập mã bằng tay | KH001 và KH005 đã hoàn tất và có nguồn “Nhập tay” trong lịch sử. | Lưu bằng chứng cùng kịch bản demo. |
| F04 | Tra cứu và xác định cửa | Phiên demo ghi nhận 30 lượt thành công; backend có kiểm thử lỗi điểm đến và quy tắc cửa. | Đối chiếu cửa của từng kiện `final_test` với đáp án độc lập. |
| F05 | Mô phỏng tuần tự | Đã chạy lô demo; backend kiểm tra lịch sử chỉ ghi sau bước hoàn tất. | Lưu bằng chứng chạy lô theo thứ tự và kết quả gắn đúng từng lượt. |
| F06 | Quản lý phiên | Đã thử chọn phiên đóng và khôi phục lượt đang chờ. Có kiểm thử quy tắc đóng phiên. | Ghi kết quả chuyển phiên trong bài thử tích hợp bộ lọc. |
| F07 | Chống phân loại trùng | Backend xác nhận quét lại trong cùng phiên không tăng số thành công. | Lưu kết quả trước và sau khi quét lại trên giao diện. |
| F08 | Xử lý lỗi | Backend đã thử các lỗi nghiệp vụ T02–T07. | Đối chiếu thông báo trên giao diện; thử riêng T08 khi backend không phản hồi. |
| F09 | Lưu lịch sử | Đã xem đủ 30 dòng qua phân trang. Backend kiểm tra gửi lại, xử lý đồng thời và hoàn tác khi ghi lỗi. | Kiểm tra phân trang và phạm vi phiên sau khi tích hợp bộ lọc. |
| F10 | Thống kê | Phiên demo có 30 thành công, 0 lỗi và 10 kiện mỗi cửa. | Kiểm tra tổng phiên khi có cả lượt thành công và lỗi, kể cả khi đang lọc lịch sử. |
| F11 | Đánh giá | Công cụ tổng hợp đã tạo được báo cáo xem thử. | Xác minh báo cáo đã lưu; hoàn tất các phép đo còn thiếu và so sánh với baseline thủ công. |

## 4. Bằng chứng đã kiểm tra

### Dữ liệu và khởi tạo

- `demo`: KH001–KH030. `final_test`: KH031–KH060. Mỗi bộ có 30 kiện,
  30 ảnh và 10 đáp án cho mỗi cửa. Hai bộ không trùng mã kiện hoặc mã đơn.
- `python kiem_tra_du_lieu.py` đã trả mã thoát 0 trên máy nhóm.
  Bước này kiểm tra quy tắc, tên và số lượng ảnh; chưa đo khả năng giải mã QR.
- Trên máy nhóm, `python app.py` chạy với database có sẵn;
  `/api/health` trả `status: ok`, 60 kiện và 3 quy tắc cửa.
  Khởi tạo SQLite mới và chạy lại cũng đã được thử trên bản sao kiểm tra.

### Phiên demo và phục hồi

- Phiên `Kiem tra demo 30 - 01` (`de8a2511`) đã đóng: 30 lượt thành công,
  0 lượt lỗi, 10 kiện mỗi cửa. Lịch sử tải 10 dòng đầu và có thể xem đủ 30 dòng.
- Phiên `Thu khoi phuc 01` (`ba58c13d`): KH001 hoàn tất ở cửa 1.
  Sau khi tải lại trang trong lúc KH005 còn chờ, nhóm bấm gửi lại và thấy
  KH005 hoàn tất ở cửa 2. Lịch sử hiển thị hai dòng, mỗi kiện một dòng.

### Kiểm thử backend

Ngày 03/11/2026, nhóm chạy trên Windows và ghi nhận **21 test đạt**:

```powershell
python -m unittest -v test_completion_flow test_concurrent_requests test_destination_errors
```

Bộ thử kiểm tra các tình huống về phiên, gửi lại, chống trùng, yêu cầu
đồng thời, lỗi nghiệp vụ, xác thực số đo QR và hoàn tác giao dịch.

### Báo cáo xem thử

```powershell
python tong_hop_danh_gia.py --preview --subset demo
```

Báo cáo đã tạo và mở được. Lần xem thử có 3 kiện được xử lý đúng lần đầu
trên 3 kiện đã thử, trong bộ demo 30 kiện. Ba mẫu thời gian từ đọc QR
đến nhận cửa có trung bình 54,933 ms, chưa gồm hoạt ảnh.

Kết quả này xác nhận công cụ tổng hợp hoạt động ở chế độ xem thử.
Lần xem thử chưa có JSON đánh giá QR độc lập và chưa đủ điều kiện
dùng làm kết quả chính thức.

## 5. Phần việc thành viên

| Phần | Nội dung | Trạng thái trên bản chung |
|---|---|---|
| 1 | Kiểm tra dữ liệu | Đã tích hợp; lệnh kiểm tra 60 kiện chạy đạt. |
| 2 | Khởi tạo hệ thống | Đã tích hợp `khoi_tao_project.py`; đã kiểm tra khởi động ứng dụng. |
| 3 | Bổ sung kiểm thử | Đã tích hợp; 21 test đạt ở mốc ghi nhận. |
| 4 | Lọc lịch sử — Phát | Đã có bản bàn giao; chờ tích hợp và kiểm tra trên bản chung. |
| 5 | Xuất lịch sử CSV trên web | Đã có bản bàn giao; chưa tích hợp. |

Lọc và xuất CSV trên web là phần mở rộng. Phân trang, lưu lịch sử,
thống kê theo phiên và các công cụ đánh giá vẫn được theo dõi theo F01–F11.

## 6. Kịch bản nghiệm thu

| Mã | Tình huống | Bằng chứng hoặc việc còn lại |
|---|---|---|
| T01 | QR hợp lệ | Đã chạy demo; cần lưu kết quả đối chiếu từng kiện với đáp án. |
| T02 | Ảnh không đọc được QR | Backend đã thử trạng thái lỗi; cần thử bằng ảnh trên giao diện. |
| T03 | Mã sai định dạng | Backend đã thử; cần lưu thông báo hiển thị. |
| T04 | Mã không tồn tại | Backend đã thử; cần lưu thông báo hiển thị. |
| T05 | Kiện thiếu điểm đến | Backend đã thử bằng dữ liệu kiểm thử. |
| T06 | Chưa có quy tắc cửa cho điểm đến | Backend đã thử bằng dữ liệu kiểm thử. |
| T07 | Quét lại kiện đã thành công | Backend đã thử; cần đối chiếu số thành công trên giao diện. |
| T08 | Backend không phản hồi | Cần thử riêng; giao diện báo lỗi kết nối và không báo kiện đã hoàn tất. |
| T09 | Gửi lại yêu cầu hoàn tất | Backend đã thử trả lại kết quả cũ, không nhân đôi lịch sử; giao diện đã thử phục hồi lượt chờ sau khi tải lại trang. |
| T10 | Đóng phiên còn lượt đang chờ | Backend đã thử từ chối đóng phiên. |
| T11 | Xử lý vào phiên đã đóng | Backend đã thử từ chối yêu cầu mới. |

## 7. Việc tiếp theo

- [ ] Tích hợp bộ lọc lịch sử: tìm theo mã, kết quả và nguồn nhập.
  Thử với một lượt nằm ngoài 10 dòng đầu; kiểm tra đổi phiên, xóa lọc
  và tổng thống kê vẫn tính trên cả phiên.
- [ ] Kiểm tra T08 và bổ sung bằng chứng giao diện còn thiếu.
- [ ] Rà xuất CSV trên web: đủ lịch sử của phiên, đúng tiếng Việt,
  xử lý dấu phẩy, dấu ngoặc kép, xuống dòng và lỗi tải.
- [ ] Kiểm tra các báo cáo đã lưu trước khi đo lại. Chốt bản code dùng
  để đánh giá và bổ sung số đo QR, độ đúng cửa, thời gian và năng suất.
- [ ] So sánh với bài phân loại thủ công trên cùng bộ `final_test`.
  Lưu thứ tự kiện, điều kiện chạy và kết quả từng lần thử.
- [ ] Đồng bộ README và cây thư mục trong Design với cách chạy thực tế.
- [ ] Hoàn thiện báo cáo, slide và kịch bản demo.