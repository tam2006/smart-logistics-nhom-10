document.addEventListener('DOMContentLoaded', function () {
    const exportBtn = document.getElementById('exportCsvBtn'); // Nút xuất CSV trên giao diện
    
    if (exportBtn) {
        exportBtn.addEventListener('click', function () {
            const sessionSelect = document.getElementById('sessionSelect');
            const currentSessionId = sessionSelect ? sessionSelect.value : null;

            // Kiểm tra trường hợp chưa chọn phiên làm việc
            if (!currentSessionId) {
                alert("Lỗi: Vui lòng chọn phiên làm việc trước khi xuất CSV.");
                return;
            }

            // Gọi API lấy file CSV với xử lý lỗi mạng và dữ liệu rỗng
            fetch(`/api/history/export-csv?session_id=${encodeURIComponent(currentSessionId)}`)
                .then(response => {
                    if (!response.ok) {
                        return response.json().then(errData => {
                            throw new Error(errData.error || "Tải dữ liệu thất bại hoặc phiên rỗng.");
                        }).catch(() => {
                            throw new Error("Lỗi mạng hoặc không thể tải dữ liệu từ server.");
                        });
                    }
                    return response.blob();
                })
                .then(blob => {
                    // Tạo đường dẫn tạm để tải file về máy
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `lich_su_phien_${currentSessionId}.csv`;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    window.URL.revokeObjectURL(url);
                })
                .catch(error => {
                    alert("Không thể xuất CSV: " + error.message);
                });
        });
    }
});
