document.addEventListener('DOMContentLoaded', function () {
    const exportBtn = document.getElementById('exportCsvBtn');
    
    if (exportBtn) {
        exportBtn.addEventListener('click', function () {
            const sessionSelect = document.getElementById('sessionSelect');
            const currentSessionId = sessionSelect ? sessionSelect.value : null;

            if (!currentSessionId) {
                alert("Vui lòng chọn phiên làm việc trước khi xuất CSV.");
                return;
            }

            fetch(`/api/history/export-csv?session_id=${encodeURIComponent(currentSessionId)}`)
                .then(response => {
                    if (!response.ok) {
                        return response.json().then(errData => {
                            throw new Error(errData.error || "Tải dữ liệu thất bại.");
                        });
                    }
                    return response.blob();
                })
                .then(blob => {
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
                    alert("Lỗi: " + error.message);
                });
        });
    }
});
