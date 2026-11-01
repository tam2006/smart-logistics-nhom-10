# DEFINE — Đồ án Smart Logistics nhóm 10

Trạng thái: Bản dự thảo để nhóm rà soát và thống nhất.
Tài liệu xác định yêu cầu và tiêu chí hoàn thành, không thay thế kết quả kiểm thử.

## 1. Tên đề tài

Xây dựng ứng dụng web mô phỏng phân loại kiện hàng theo điểm đến bằng mã QR tại một trạm phân loại gồm ba cửa.

## 2. Hướng chính

Tự động hoá việc đọc mã kiện, tra cứu điểm đến và xác định cửa phân loại.

Hệ thống sử dụng quy tắc ánh xạ điểm đến–cửa.
Không yêu cầu huấn luyện mô hình AI.

## 3. Người sử dụng và vấn đề

### Người sử dụng

Nhân viên vận hành một trạm phân loại kiện hàng trong kho.

### Vấn đề

Quy trình thủ công yêu cầu nhân viên:

1. Đọc mã trên nhãn kiện.
2. Tra bảng thông tin kiện và điểm đến.
3. Xác định cửa phân loại.
4. Ghi nhận kết quả xử lý.

Quá trình này có thể phát sinh chọn sai cửa, bỏ sót, xử lý lại kiện đã hoàn tất hoặc thiếu lịch sử để đối chiếu.

### Mục tiêu giải quyết

Ứng dụng đọc QR để lấy mã kiện, tự tra dữ liệu và xác định cửa.
Giao diện mô phỏng quá trình chuyển kiện và hiển thị kết quả.
Lịch sử và thống kê hỗ trợ kiểm tra kết quả xử lý.

## 4. Đầu vào và đầu ra

| Thành phần | Nội dung |
|---|---|
| Đầu vào QR | Ảnh chứa QR có nội dung là mã kiện, ví dụ KH001 |
| Đầu vào thủ công | Mã kiện được người dùng nhập bằng bàn phím |
| Dữ liệu tra cứu | Danh sách kiện, điểm đến và bảng quy tắc điểm đến–cửa |
| Ngữ cảnh xử lý | Phiên làm việc đang được chọn |
| Đầu ra hợp lệ | Mã kiện, điểm đến, cửa phân loại, mô phỏng và kết quả hoàn tất |
| Đầu ra lỗi | Trạng thái và lý do lỗi; không ghi nhận kiện thành công vào ba cửa |
| Dữ liệu lưu | Lịch sử các lượt hoàn tất và số đo liên quan nếu có |
| Đầu ra đánh giá | Báo cáo đối chiếu đáp án, thời gian và năng suất mô phỏng |

Tên ảnh chỉ phục vụ nhận biết tệp.
Mã kiện phải được lấy từ nội dung QR, không suy ra từ tên ảnh.

Nhập mã bằng tay được ghi đúng nguồn nhập và không tính là đọc QR thành công.

## 5. Dữ liệu và quy tắc phân loại

### Nguồn dữ liệu

Sử dụng dữ liệu tham chiếu Olist/Brazil.
Nhóm đã trao đổi trực tiếp và được giảng viên đồng ý sử dụng nguồn dữ liệu này.

Mã kiện, ảnh QR và quy tắc ánh xạ ba cửa do nhóm thiết lập phục vụ mô phỏng.
Không coi quy tắc của nhóm là quy tắc vận hành thực tế của Olist.

### Quy tắc ba cửa

| Điểm đến | Cửa |
|---|---|
| São Paulo | 1 |
| Rio de Janeiro | 2 |
| Belo Horizonte | 3 |

Dữ liệu kiện và bảng quy tắc phải thống nhất cách biểu diễn điểm đến, bao gồm thông tin bang khi cần để tra cứu.

### Tổ chức bộ dữ liệu của nhóm

- Bộ demo/phát triển: KH001–KH030.
- Bộ kiểm thử cuối cùng: KH031–KH060.
- Mỗi bộ có 30 kiện hợp lệ, chia đều 10 kiện cho mỗi cửa.
- Hai bộ không giao nhau về mã kiện và mã đơn nguồn.
- Bổ sung các tình huống lỗi để kiểm tra riêng.
- Chốt bộ kiểm thử cuối cùng và đáp án trước khi đánh giá.
- Không sửa đáp án theo kết quả mà chương trình trả về.

Việc nhóm tổ chức hai bộ là cách triển khai để tách phát triển và đánh giá.
Yêu cầu nghiệm thu phải có đánh giá trên bộ 30 kiện hợp lệ đã xác định.

## 6. Yêu cầu chức năng bắt buộc

| Mã | Yêu cầu | Điều kiện hoàn thành |
|---|---|---|
| F01 | Mô phỏng một trạm, một băng chuyền và ba cửa | Thể hiện rõ ba cửa và quy tắc điểm đến tương ứng |
| F02 | Đọc QR từ ảnh | Lấy được mã kiện từ nội dung QR và báo khi không đọc được |
| F03 | Nhập mã bằng tay | Kiểm tra và tra cứu được, ghi đúng nguồn nhập |
| F04 | Tra cứu và xác định cửa | Backend kiểm tra dữ liệu kiện và quy tắc trước khi trả kết quả |
| F05 | Mô phỏng tuần tự | Kiện được xử lý lần lượt, kết quả hoàn tất gắn đúng lượt |
| F06 | Quản lý phiên | Tạo, chọn và đóng phiên; lịch sử và thống kê đúng phiên |
| F07 | Chống phân loại trùng | Kiện đã thành công trong cùng phiên không được tính thành công lần nữa |
| F08 | Xử lý lỗi | Thông báo đúng nguyên nhân; kiện lỗi không được tính vào ba cửa |
| F09 | Lưu lịch sử | Mỗi lượt hoàn tất có đúng một bản ghi; gửi lại yêu cầu không tạo bản ghi trùng |
| F10 | Thống kê | Số kiện thành công từng cửa và số lượt lỗi khớp lịch sử của phiên |
| F11 | Đánh giá | Có bộ thử, đáp án, phép đo, kết quả và so sánh với baseline |

## 7. Tình huống kiểm thử bắt buộc

| Mã | Tình huống | Kết quả mong đợi |
|---|---|---|
| T01 | QR hợp lệ của kiện đủ thông tin | Phân đúng cửa và ghi lịch sử sau khi hoàn tất |
| T02 | Ảnh không có QR hoặc QR không đọc được | Báo không đọc được; không tính thành công |
| T03 | Mã sai định dạng | Báo mã không hợp lệ |
| T04 | Mã không tồn tại | Báo không tìm thấy kiện |
| T05 | Kiện thiếu điểm đến | Báo thiếu dữ liệu điểm đến |
| T06 | Điểm đến chưa có quy tắc | Báo chưa cấu hình cửa |
| T07 | Quét lại kiện đã thành công trong cùng phiên | Báo trùng, không tăng số thành công |
| T08 | Backend không phản hồi | Báo lỗi kết nối; không tự kết luận đã hoàn tất |
| T09 | Gửi lại yêu cầu hoàn tất sau khi mất phản hồi | Trả kết quả cũ, không nhân đôi lịch sử |
| T10 | Đóng phiên còn lượt đang xử lý | Từ chối đóng, thông báo rõ lý do |
| T11 | Xử lý vào phiên đã đóng | Từ chối tạo lượt xử lý mới |

T01–T08 bám bộ tình huống trong yêu cầu nhóm 10.
T09–T11 kiểm tra bổ sung tính đúng của cơ chế phiên và hoàn tất.

Ảnh QR không đọc được khác với tệp ảnh hỏng hoặc định dạng không được hỗ trợ.
Lỗi tệp phải được báo riêng, không biến thành kiện thành công.

## 8. Baseline và cách đánh giá

### Baseline thủ công

Người tham gia đọc mã kiện trên nhãn, tra bảng mã kiện–điểm đến–cửa và chọn cửa.

Hai phương pháp dùng cùng bộ kiện và cùng quy tắc.

### Chỉ số và mục tiêu

| Chỉ số | Cách xác định | Mục tiêu hoặc yêu cầu |
|---|---|---|
| Độ chính xác đọc QR | Ảnh đọc đúng mã / tổng ảnh QR hợp lệ được thử | Mục tiêu 30/30 ảnh QR chuẩn |
| Độ đúng phân loại | Kiện hợp lệ hoàn tất đúng cửa / tổng kiện hợp lệ được thử | Mục tiêu 30/30 kiện |
| Xử lý lỗi đúng | Tình huống lỗi được xử lý đúng / tổng tình huống lỗi được thử | Đúng toàn bộ bộ tình huống đã chốt |
| Chống trùng | Đối chiếu số thành công trước và sau khi quét lại | Không tăng số thành công trong cùng phiên |
| Lịch sử | Đối chiếu mã, trạng thái, cửa và số bản ghi | Đúng một lần cho mỗi lượt hoàn tất |
| Thời gian xác định cửa | Đọc, tra cứu và nhận kết quả cửa | Đo và báo cáo điều kiện, số mẫu |
| Năng suất mô phỏng | Số kiện thành công hoàn tất / thời gian chạy tính bằng phút | Đo, báo cáo số kiện và thời lượng |
| So sánh baseline | Thời gian và độ đúng của hai phương pháp | Báo cáo kết quả thực tế, không khẳng định trước mức cải thiện |

### Quy tắc đo

- Tách thời gian hoạt ảnh khỏi phép so sánh thời gian xác định cửa.
- Năng suất mô phỏng có tính hoạt ảnh và khoảng nghỉ giữa các kiện theo điều kiện chạy.
- Không lấy nghịch đảo thời gian xác định cửa để thay cho năng suất toàn lô.
- Không chỉ chọn các lượt đọc QR thành công để tính độ chính xác.
- Bộ thử thiếu ảnh hoặc có lỗi tệp phải được nêu rõ; chưa dùng để kết luận độ chính xác đủ bộ.
- Không dùng lần chạy bị gián đoạn để kết luận năng suất chính thức.
- Thực hiện nhiều lượt thử với thứ tự kiện thay đổi và ghi điều kiện chạy.
- Giữ nguyên cả kết quả không thuận lợi để phân tích.

Các mục tiêu trong tài liệu này chưa phải kết quả đã đạt.

## 9. Công nghệ và ràng buộc

| Thành phần | Công nghệ |
|---|---|
| Giao diện và mô phỏng | HTML, CSS, JavaScript |
| Đọc QR | jsQR |
| Backend/API | Python Flask |
| Lưu trữ | SQLite |
| Kiểm tra và báo cáo | Các công cụ Python trong dự án |
| Quản lý source | Git và GitHub |

Hệ thống phục vụ mô phỏng phần mềm tại một trạm.
Không đánh đồng chuyển động trên giao diện với thiết bị vật lý.

## 10. Phần mở rộng

- Xuất lịch sử phiên thành CSV trên web.
- Bộ lọc lịch sử.
- Xử lý tự động nhiều ảnh theo lô.
- Quét QR bằng camera.

Ưu tiên hoàn thành và đánh giá chức năng bắt buộc.
Các phần mở rộng chỉ được coi là hoàn thành sau khi kiểm tra và tích hợp.

## 11. Ngoài phạm vi

- Điều khiển băng chuyền hoặc thiết bị thật.
- Quản lý nhiều kho.
- Điều phối vận tải và tối ưu tuyến đường.
- Thanh toán.
- Đăng nhập và phân quyền.
- Dự báo hoặc huấn luyện mô hình học máy.

## 12. Sản phẩm bàn giao

1. Ứng dụng web mô phỏng phân loại ba cửa.
2. Backend/API và cấu trúc database.
3. Dữ liệu mẫu, quy tắc, ảnh QR và đáp án kiểm thử.
4. Source code và hướng dẫn khởi tạo, chạy ứng dụng.
5. Kết quả kiểm thử và báo cáo so sánh baseline.
6. Phân tích lỗi và giới hạn.
7. Tài liệu thiết kế, pipeline và kịch bản demo.
8. Video hoặc buổi demo theo yêu cầu học phần.

## 13. Nguyên tắc xác nhận tiến độ

Mỗi yêu cầu được đối chiếu với:

- Module hoặc file thực hiện.
- Người phụ trách.
- Trạng thái: chưa làm, đang làm, chờ kiểm tra, cần sửa hoặc đã nghiệm thu.
- Kịch bản kiểm tra.
- Minh chứng kết quả.

Có code hoặc đã push lên GitHub chưa đồng nghĩa với đã nghiệm thu.
Thay đổi phạm vi phải được cập nhật vào tài liệu trước khi triển khai tiếp.