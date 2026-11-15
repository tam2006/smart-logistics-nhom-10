// === HỆ THỐNG LỊCH SỬ QUÉT PRO MAX (FILTERS, STATS, SORTING, PAGINATION & QUICK COPY) ===
document.addEventListener('DOMContentLoaded', function () {
    const searchInput = document.getElementById('search-parcel');     
    const statusSelect = document.getElementById('filter-status');    
    const sourceSelect = document.getElementById('filter-source');    
    const startDateInput = document.getElementById('filter-start-date'); 
    const endDateInput = document.getElementById('filter-end-date');     
    const clearBtn = document.getElementById('clear-filters-btn');      
    const exportFilteredBtn = document.getElementById('export-filtered-btn'); 
    const historyTableBody = document.getElementById('history-table-body');
    const historyTableRows = historyTableBody ? Array.from(historyTableBody.querySelectorAll('tr')) : []; 
    const resultCountEl = document.getElementById('result-count');      

    // Thẻ thống kê nhanh (nếu có trên giao diện)
    const statTotalEl = document.getElementById('stat-total');
    const statSuccessEl = document.getElementById('stat-success');
    const statPendingEl = document.getElementById('stat-pending');

    const STORAGE_PREFIX = 'smart_logistics_filter_state_pro_';

    // 1. Khôi phục / Lưu trạng thái LocalStorage
    function restoreFilterState() {
        if (!searchInput) return;
        if (localStorage.getItem(STORAGE_PREFIX + 'search')) searchInput.value = localStorage.getItem(STORAGE_PREFIX + 'search');
        if (localStorage.getItem(STORAGE_PREFIX + 'status')) statusSelect.value = localStorage.getItem(STORAGE_PREFIX + 'status');
        if (localStorage.getItem(STORAGE_PREFIX + 'source')) sourceSelect.value = localStorage.getItem(STORAGE_PREFIX + 'source');
        if (localStorage.getItem(STORAGE_PREFIX + 'start')) startDateInput.value = localStorage.getItem(STORAGE_PREFIX + 'start');
        if (localStorage.getItem(STORAGE_PREFIX + 'end')) endDateInput.value = localStorage.getItem(STORAGE_PREFIX + 'end');
    }

    function saveFilterState() {
        if (!searchInput) return;
        localStorage.setItem(STORAGE_PREFIX + 'search', searchInput.value);
        localStorage.setItem(STORAGE_PREFIX + 'status', statusSelect ? statusSelect.value : '');
        localStorage.setItem(STORAGE_PREFIX + 'source', sourceSelect ? sourceSelect.value : '');
        localStorage.setItem(STORAGE_PREFIX + 'start', startDateInput ? startDateInput.value : '');
        localStorage.setItem(STORAGE_PREFIX + 'end', endDateInput ? endDateInput.value : '');
    }

    // 2. Highlighting từ khóa
    function highlightText(cell, keyword) {
        if (!cell) return;
        const originalText = cell.textContent;
        if (!keyword) {
            cell.innerHTML = originalText;
            return;
        }
        const regex = new RegExp(`(${keyword})`, 'gi');
        if (regex.test(originalText)) {
            cell.innerHTML = originalText.replace(regex, '<mark class="bg-warning px-1 rounded">$1</mark>');
        } else {
            cell.innerHTML = originalText;
        }
    }

    // 3. Hàm lọc chính & Cập nhật Thống kê Dashboard
    function applyFilters() {
        const keyword = searchInput ? searchInput.value.trim().toLowerCase() : '';
        const selectedStatus = statusSelect ? statusSelect.value.trim().toLowerCase() : '';
        const selectedSource = sourceSelect ? sourceSelect.value.trim().toLowerCase() : '';
        const startDate = startDateInput && startDateInput.value ? new Date(startDateInput.value) : null;
        const endDate = endDateInput && endDateInput.value ? new Date(endDateInput.value) : null;
        
        if (endDate) endDate.setHours(23, 59, 59, 999);

        let visibleCount = 0;
        let successCount = 0;
        let pendingCount = 0;

        historyTableRows.forEach(row => {
            const codeCell = row.cells[1]; 
            const timeCell = row.cells[0]; 
            
            const parcelCode = (row.getAttribute('data-code') || (codeCell ? codeCell.innerText : '')).toLowerCase();
            const status = (row.getAttribute('data-status') || (row.cells[4] ? row.cells[4].innerText : '')).toLowerCase();
            const source = (row.getAttribute('data-source') || (row.cells[6] ? row.cells[6].innerText : '')).toLowerCase();
            const rowTimeString = row.getAttribute('data-time') || (timeCell ? timeCell.innerText : '');

            let matchKeyword = parcelCode.includes(keyword);
            let matchStatus = !selectedStatus || status.includes(selectedStatus);
            let matchSource = !selectedSource || source.includes(selectedSource);

            let matchDate = true;
            if ((startDate || endDate) && rowTimeString) {
                const rowDate = new Date(rowTimeString);
                if (!isNaN(rowDate.getTime())) {
                    if (startDate && rowDate < startDate) matchDate = false;
                    if (endDate && rowDate > endDate) matchDate = false;
                }
            }

            if (matchKeyword && matchStatus && matchSource && matchDate) {
                row.style.display = '';
                visibleCount++;

                // Thống kê trạng thái các dòng hiển thị
                if (status.includes('thành công') || status.includes('success') || status.includes('hoàn thành')) {
                    successCount++;
                } else {
                    pendingCount++;
                }

                if (codeCell && keyword) {
                    highlightText(codeCell, keyword);
                } else if (codeCell) {
                    codeCell.innerHTML = codeCell.textContent;
                }
            } else {
                row.style.display = 'none';
                if (codeCell) codeCell.innerHTML = codeCell.textContent;
            }
        });

        // Cập nhật số liệu giao diện
        if (resultCountEl) {
            resultCountEl.innerText = `Hiển thị ${visibleCount} / ${historyTableRows.length} kết quả phù hợp`;
        }
        if (statTotalEl) statTotalEl.innerText = visibleCount;
        if (statSuccessEl) statSuccessEl.innerText = successCount;
        if (statPendingEl) statPendingEl.innerText = pendingCount;

        saveFilterState();
    }

    // 4. Tính năng Sao chép nhanh Mã kiện khi bấm đúp chuột vào ô mã
    if (historyTableBody) {
        historyTableBody.addEventListener('dblclick', function (e) {
            const cell = e.target.closest('td');
            if (cell && cell.cellIndex === 1) { // Cột mã kiện
                const textToCopy = cell.textContent.trim();
                navigator.clipboard.writeText(textToCopy).then(() => {
                    // Hiển thị thông báo nhỏ tạm thời
                    const originalBg = cell.style.backgroundColor;
                    cell.style.backgroundColor = '#d1e7dd';
                    setTimeout(() => { cell.style.backgroundColor = originalBg; }, 500);
                });
            }
        });
    }

    // 5. Sự kiện tương tác bộ lọc
    if (searchInput) searchInput.addEventListener('input', applyFilters);
    if (statusSelect) statusSelect.addEventListener('change', applyFilters);
    if (sourceSelect) sourceSelect.addEventListener('change', applyFilters);
    if (startDateInput) startDateInput.addEventListener('change', applyFilters);
    if (endDateInput) endDateInput.addEventListener('change', applyFilters);

    if (clearBtn) {
        clearBtn.addEventListener('click', function () {
            if (searchInput) searchInput.value = '';
            if (statusSelect) statusSelect.value = '';
            if (sourceSelect) sourceSelect.value = '';
            if (startDateInput) startDateInput.value = '';
            if (endDateInput) endDateInput.value = '';
            
            localStorage.clear();
            applyFilters();
        });
    }

    // 6. Xuất CSV danh sách đã lọc
    if (exportFilteredBtn) {
        exportFilteredBtn.addEventListener('click', function () {
            let csvContent = "data:text/csv;charset=utf-8,ThoiGian,MaDonHang,TrangThai,NguonNhap\n";
            let exportedCount = 0;

            historyTableRows.forEach(row => {
                if (row.style.display !== 'none') {
                    const cols = row.querySelectorAll('td');
                    if (cols.length >= 7) {
                        csvContent += `"${cols[0].innerText.trim()}","${cols[1].innerText.trim()}","${cols[4].innerText.trim()}","${cols[6].innerText.trim()}"\n`;
                        exportedCount++;
                    }
                }
            });

            if (exportedCount === 0) {
                alert("Không có dữ liệu phù hợp để xuất file!");
                return;
            }

            const encodedUri = encodeURI(csvContent);
            const link = document.createElement("a");
            link.setAttribute("href", encodedUri);
            link.setAttribute("download", "smart_logistics_pro_history.csv");
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        });
    }

    // Khởi chạy
    restoreFilterState();
    applyFilters();
});