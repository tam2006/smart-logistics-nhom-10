# Cấu trúc công việc và tiến độ — Smart Logistics nhóm 10

Cập nhật: 02/11/2026.

## 1. Mục đích và tài liệu liên quan

Nhóm dùng cấu trúc này để chia việc, triển khai và kiểm tra
demo mô phỏng một trạm phân loại kiện hàng với ba cửa.

Ba tài liệu được sử dụng cùng nhau:

- project-description.md: bài toán, phạm vi và yêu cầu.
- system-design.md: kiến trúc, module, dữ liệu, API và pipeline.
- implementation-status.md: phần việc, tiến độ và bằng chứng kiểm tra.

Không đánh dấu hoàn thành chỉ vì đã có file hoặc đã push code.
Một phần được xác nhận đạt khi có kết quả kiểm tra phù hợp.

Các nhánh của thành viên chưa được rà soát không được mặc định
đã tích hợp vào bản demo chung.

## 2. Cấu trúc công việc

| Bước | Phần việc | Đầu ra cần có | Điều kiện hoàn thành |
|---|---|---|---|
| 1 | Xác định bài toán | project-description.md | Thống nhất phạm vi, đầu vào, đầu ra và yêu cầu |
| 2 | Thiết kế hệ thống | system-design.md | Có kiến trúc, module, cấu trúc thư mục, pipeline và API |
| 3 | Chuẩn bị dữ liệu | Dữ liệu sạch, bộ demo, bộ final_test, ảnh QR và đáp án | Kiểm tra đủ bộ, không trùng giữa hai tập, đối chiếu được |
| 4 | Khởi tạo hệ thống | Script khởi tạo và database | Chạy được trên môi trường mới, bảo toàn dữ liệu khi chạy lại |
| 5 | Xây dựng luồng phân loại | Nhập mã hoặc QR, tra cứu, chọn cửa, mô phỏng, xác nhận | Kết quả đúng theo quy tắc và chỉ ghi lịch sử sau xác nhận |
| 6 | Quản lý phiên và lịch sử | Phiên, số đếm, lịch sử, phân trang | Hiển thị đúng phiên, không mất hoặc nhân đôi lượt |
| 7 | Tích hợp phần thành viên | Kiểm tra dữ liệu, khởi tạo, kiểm thử, lọc và CSV | Rà soát nhánh, giải quyết xung đột và thử trên bản chung |
| 8 | Kiểm tra tình huống lỗi | Kịch bản thử và kết quả thực tế | Đủ các tình huống bắt buộc, xử lý và thông báo đúng |
| 9 | Đánh giá hệ thống | Số đo QR, định tuyến, thời gian, năng suất và bài thủ công | Đối chiếu được với đáp án và nguồn số liệu |
| 10 | Hoàn thiện báo cáo và demo | Báo cáo, slide, hướng dẫn chạy, kịch bản trình bày | Nội dung khớp với bản code và kết quả đã kiểm tra |

Thứ tự thực hiện:

1. Thống nhất yêu cầu và thiết kế.
2. Triển khai theo từng phần việc.
3. Kiểm tra từng phần và tích hợp.
4. Chốt phiên bản để đánh giá.
5. Hoàn thiện báo cáo và trình bày demo.

Khi phát hiện thiết kế cần thay đổi, cập nhật system-design.md
và ghi lại ảnh hưởng tới các phần việc liên quan.

## 3. Quy ước trạng thái

- Chưa bắt đầu: chưa có triển khai hoặc chưa có thông tin.
- Đang làm: đã triển khai một phần, còn việc phải hoàn thiện.
- Chờ kiểm tra: đã có code hoặc kết quả bàn giao, chưa xác nhận đạt.
- Cần sửa: đã phát hiện vấn đề cần xử lý.
- Đã kiểm chứng một phần: đạt trong phạm vi được ghi rõ.
- Hoàn thành: đủ điều kiện kiểm tra của phần việc.

Trạng thái của một bài kiểm thử không đại diện cho toàn bộ hệ thống.

## 4. Theo dõi triển khai chức năng

Các mã F dùng để đối chiếu với tài liệu yêu cầu và thiết kế.
Nếu hai tài liệu thay đổi, cần cập nhật bảng này cho thống nhất.

| Mã | Phần việc | File hoặc khu vực liên quan | Trạng thái | Việc cần kiểm tra tiếp |
|---|---|---|---|---|
| F01 | Chuẩn bị và kiểm tra dữ liệu | chuan_bi_du_lieu_ung_dung.py, lam_sach_du_lieu.py, kiem_tra_du_lieu.py, data/ | Chờ kiểm tra | Rà soát dữ liệu và phần bàn giao của thành viên |
| F02 | Khởi tạo database và dữ liệu ứng dụng | init_db.py, init_tracking.py, nang_cap_xu_ly.py | Đã kiểm chứng một phần | Kiểm tra toàn bộ quy trình khởi tạo trên môi trường mới; bộ thử hiện có đã kiểm tra một số trường hợp nâng cấp và sao lưu |
| F03 | Tạo, chọn và đóng phiên | session_routes.py, static/app.js | Đã kiểm chứng một phần | Tiếp tục kiểm tra giao diện và các tình huống phục hồi; một số quy tắc đóng phiên và gửi lại đã có bài thử đạt |
| F04 | Nhập mã kiện bằng tay | templates/index.html, static/app.js, history_routes.py | Chờ kiểm tra | Thử luồng giao diện từ nhập mã tới xác nhận hoàn tất |
| F05 | Đọc ảnh QR | static/qr_decoder.js, static/app.js, static/qr_evaluation.html | Đang làm | Hoàn thiện bằng chứng đánh giá trên toàn bộ ảnh đầu vào |
| F06 | Tra cứu và quyết định cửa | history_routes.py, dữ liệu kiện và quy tắc | Đã kiểm chứng một phần | Đối chiếu đủ bộ đáp án và các trường hợp nghiệp vụ |
| F07 | Mô phỏng và xác nhận hoàn tất | static/app.js, history_routes.py | Đã kiểm chứng một phần | Kiểm tra hành vi trình duyệt khi mất mạng, tải lại trang và khôi phục lượt đang chờ |
| F08 | Xử lý lỗi, trùng và yêu cầu đồng thời | history_routes.py, các file test_*.py | Đã kiểm chứng một phần | Bổ sung kiểm tra số đo, hoàn tác giao dịch và đủ kịch bản lỗi giao diện |
| F09 | Chạy lô ảnh và lưu số đo | static/app.js, history_routes.py, nhap_so_do.py | Đã kiểm chứng một phần | Kiểm tra đầy đủ điều kiện đo chính thức, gián đoạn và đối chiếu số liệu |
| F10 | Lịch sử, số đếm, lọc và xuất CSV | history_routes.py, static/app.js, static/gate_stats.js, phần lọc và CSV của thành viên | Đã kiểm chứng một phần | Phân trang và số đếm đã được thử trên một phiên 30 lượt; lọc và CSV vẫn chờ rà soát tích hợp |
| F11 | Tổng hợp và đánh giá | xuat_va_doi_chieu.py, tong_hop_danh_gia.py, do_phan_loai_thu_cong.py, nhap_so_do.py | Đang làm | Bản xem thử đã chạy; còn đánh giá chính thức và bài thủ công để so sánh |

## 5. Bằng chứng đã kiểm tra

### 5.1. Báo cáo tổng hợp ở chế độ xem thử

Lệnh chạy:

```powershell
python tong_hop_danh_gia.py --preview --subset demo
```

Lần thử được chọn có:

- Bộ demo: 30 kiện.
- Đã thử: 3 kiện.
- Đúng lần đầu: 3 kiện.
- Đúng trên số đã thử: 100%.
- Đúng trên toàn bộ 30 kiện: 10%.
- Số mẫu thời gian: 3.
- Trung bình QR tới nhận cửa: 54.933 ms.
- Trung vị: 59.9 ms.
- P95: 61.4 ms.

Đã mở được báo cáo HTML và kiểm tra các giá trị hiển thị.

Báo cáo có số đo năng suất mô phỏng từ nguồn đã chọn,
nhưng chưa đủ điều kiện bộ đầy đủ và phiên đóng để sử dụng
như kết quả đo chính thức.

Báo cáo cũng hiển thị rõ chưa nhập JSON đánh giá QR độc lập.

Kết quả này xác nhận việc tạo và hiển thị báo cáo xem thử.
Không dùng 3/3 để kết luận độ chính xác trên toàn bộ bộ ảnh,
và không dùng báo cáo xem thử để nghiệm thu toàn bộ đồ án.

### 5.2. Lịch sử và số đếm của một phiên 30 lượt

Phiên đã kiểm tra:

- Tên: Kiem tra demo 30 - 01.
- ID ngắn: de8a2511.
- Trạng thái: đã đóng.
- Tổng lượt: 30.
- Thành công: 30.
- Không thành công: 0.
- Cửa 1: 10 kiện.
- Cửa 2: 10 kiện.
- Cửa 3: 10 kiện.

Đã kiểm tra trên giao diện:

- Lần đầu tải 10 lượt lịch sử.
- Bấm Xem thêm để tải tiếp.
- Hiển thị đủ 30 lượt.
- Nút Xem thêm bị vô hiệu hóa khi đã tải hết.
- Tổng số lượt và số kiện mỗi cửa khớp với phiên được chọn.

Kết quả này chỉ xác nhận phiên và thao tác đã thử.
Chưa thay thế kiểm tra lọc, xuất CSV hoặc chuyển phiên
trong các tình huống bất đồng bộ.

### 5.3. Nhãn trong danh sách chọn phiên

Đã kiểm tra giao diện sau khi cập nhật static/app.js.

Mỗi lựa chọn hiển thị:

- Số lượt.
- Trạng thái phiên.
- ID ngắn.
- Tên phiên.

Khi rê chuột, có thể xem tên và ID đầy đủ.

Mục đích: phân biệt các phiên trùng tên và tránh chọn nhầm
phiên rỗng với phiên đã có dữ liệu.

Đã xác nhận nhãn mới hiển thị trên trình duyệt.
Không cần tạo thêm lượt xử lý chỉ để kiểm tra nhãn.

## 6. Kết quả kiểm thử backend ngày 02/11/2026

Lệnh chạy:

```powershell
python -m unittest -v test_completion_flow test_concurrent_requests test_destination_errors
```

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

Bộ thử này chưa bao phủ:

- Xác thực số đo QR.
- Hoàn tác khi ghi dữ liệu thất bại.
- Phân trang nhiều trang.
- Hành vi giao diện trình duyệt.

Phân trang đã được kiểm tra thủ công riêng trong mục 5.2;
đó không phải kết quả của bộ unittest này.

Kết quả 11 bài thử không thay thế nghiệm thu toàn bộ F06–F09.

## 7. Theo dõi phần việc thành viên

| Phần | Nội dung bàn giao | Tình trạng hiện biết | Bước tiếp theo |
|---|---|---|---|
| 1 | Kiểm tra dữ liệu | Đã nhận liên kết nhánh hoặc PR | Rà soát code, dữ liệu thử và kết quả chạy |
| 2 | Khởi tạo hệ thống | Chưa có đủ nguồn bàn giao để xác nhận | Nhận nhánh và hướng dẫn chạy |
| 3 | Bổ sung kiểm thử | Chưa có đủ nguồn bàn giao để xác nhận | Nhận nhánh, rà soát phạm vi bài thử và chạy thử |
| 4 | Lọc lịch sử | Đã nhận liên kết nhánh | Kiểm tra lọc đúng phiên và trên toàn bộ dữ liệu cần lọc |
| 5 | Xuất lịch sử CSV | Đã thấy PR xuất CSV | Rà soát code và thử dữ liệu đầy đủ, tiếng Việt, ký tự đặc biệt và lỗi xuất |

Tình trạng trong bảng phản ánh thông tin đã nhận.
Không suy ra thành viên chưa làm chỉ vì chưa có liên kết bàn giao.

Chỉ ghi đã tích hợp sau khi phần việc có trong bản chung
và đã kiểm tra hoạt động cùng các chức năng hiện có.

## 8. Các kịch bản cần nghiệm thu

| Mã | Kịch bản | Bằng chứng cần lưu |
|---|---|---|
| T01 | Kiện hợp lệ được đưa tới đúng cửa | Kết quả, lịch sử và đối chiếu đáp án |
| T02 | Ảnh không đọc được QR | Thông báo và lịch sử lỗi nghiệp vụ |
| T03 | Mã sai định dạng | Kết quả từ chối hoặc lỗi nghiệp vụ đúng thiết kế |
| T04 | Mã không tồn tại | Thông báo và lịch sử tương ứng |
| T05 | Kiện thiếu điểm đến | Kết quả lỗi đúng lý do |
| T06 | Điểm đến chưa có quy tắc cửa | Kết quả lỗi đúng lý do |
| T07 | Xử lý lại kiện đã thành công trong cùng phiên | Không tăng thêm số thành công |
| T08 | Backend không phản hồi | Thông báo rõ, không tự tạo kết quả hoàn tất |
| T09 | Gửi lại yêu cầu hoàn tất | Không nhân đôi lịch sử và số đo |
| T10 | Đóng phiên khi còn lượt đang chờ | Từ chối đóng và cho phép giải quyết lượt đang chờ |
| T11 | Tạo yêu cầu mới trong phiên đã đóng | Từ chối yêu cầu mới |

Một số kịch bản đã có bằng chứng backend tại mục 6.
Cần ghi riêng kết quả thử giao diện trước khi đánh dấu
hoàn thành toàn bộ kịch bản từ đầu tới cuối.

## 9. Việc làm tiếp theo

- [ ] Rà soát sự thống nhất giữa Define, Design và bảng tiến độ.
- [ ] Nhận đủ phần bàn giao của thành viên.
- [ ] Rà soát và tích hợp từng phần vào bản chung.
- [ ] Kiểm tra khởi tạo trên môi trường mới.
- [ ] Bổ sung kiểm tra xác thực số đo và hoàn tác giao dịch.
- [ ] Kiểm tra các tình huống mất mạng, tải lại và khôi phục.
- [ ] Kiểm tra lọc và xuất CSV trên toàn bộ dữ liệu của phiên.
- [ ] Hoàn thiện bằng chứng cho các kịch bản T01–T11.
- [ ] Chốt phiên bản trước lần đánh giá chính thức.
- [ ] Thực hiện đánh giá QR và định tuyến trên bộ final_test.
- [ ] Đo thời gian và năng suất theo điều kiện đã thống nhất.
- [ ] Thực hiện bài phân loại thủ công để so sánh.
- [ ] Lưu điều kiện thử, thứ tự hoặc seed và các lần lặp.
- [ ] Hoàn thiện báo cáo, slide và hướng dẫn demo.

Chưa kết luận hoàn thành toàn bộ đồ án hoặc đưa ra phần trăm
hoàn thành khi chưa đối chiếu đủ yêu cầu và bằng chứng.