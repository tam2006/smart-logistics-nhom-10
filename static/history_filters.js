// static/history_filters.js
document.addEventListener('DOMContentLoaded', function () {
    const searchInput = document.getElementById('search-parcel'); // Ô nhập mã kiện
    const statusSelect = document.getElementById('filter-status'); // Dropdown trạng thái
    const sourceSelect = document.getElementById('filter-source'); // Dropdown nguồn nhập
    const clearBtn = document.getElementById('clear-filters-btn');   // Nút xóa bộ lọc
    const historyTableRows = document.querySelectorAll('#history-table-body tr'); // Các dòng trong bảng lịch sử
    const resultCountEl = document.getElementById('result-count'); // Hiển thị số kết quả

    function applyFilters() {
        const keyword = searchInput ? searchInput.value.trim().toLowerCase() : '';
        const selectedStatus = statusSelect ? statusSelect.value : '';
        const selectedSource = sourceSelect ? sourceSelect.value : '';

        let visibleCount = 0;

        historyTableRows.forEach(row => {
            const parcelCode = row.getAttribute('data-code') || row.cells[1].innerText.toLowerCase();
            const status = row.getAttribute('data-status') || row.cells[4].innerText.toLowerCase();
            const source = row.getAttribute('data-source') || row.cells[6].innerText.toLowerCase();

            let matchKeyword = parcelCode.includes(keyword);
            let matchStatus = !selectedStatus || status.includes(selectedStatus.toLowerCase());
            let matchSource = !selectedSource || source.includes(selectedSource.toLowerCase());

            if (matchKeyword && matchStatus && matchSource) {
                row.style.display = '';
                visibleCount++;
            } else {
                row.style.display = 'none';
            }
            
        });

        if (resultCountEl) {
            resultCountEl.innerText = `Hiển thị ${visibleCount} kết quả phù hợp`;
        }
    }

    if (searchInput) searchInput.addEventListener('input', applyFilters);
    if (statusSelect) statusSelect.addEventListener('change', applyFilters);
    if (sourceSelect) sourceSelect.addEventListener('change', applyFilters);

    if (clearBtn) {
        clearBtn.addEventListener('click', function () {
            if (searchInput) searchInput.value = '';
            if (statusSelect) statusSelect.value = '';
            if (sourceSelect) sourceSelect.value = '';
            applyFilters();
        });
    }
});