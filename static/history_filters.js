// === SIÊU BỘ LỌC LỊCH SỬ (HISTORY FILTERS PRO MAX) ===
document.addEventListener('DOMContentLoaded', function () {
    const searchInput = document.getElementById('search-parcel');     // Ô nhập từ khóa
    const statusSelect = document.getElementById('filter-status');    // Lọc theo trạng thái
    const sourceSelect = document.getElementById('filter-source');    // Lọc theo nguồn nhập
    const startDateInput = document.getElementById('filter-start-date'); // Từ ngày
    const endDateInput = document.getElementById('filter-end-date');     // Đến ngày
    const clearBtn = document.getElementById('clear-filters-btn');      // Nút xóa bộ lọc
    const exportFilteredBtn = document.getElementById('export-filtered-btn'); // Nút xuất CSV danh sách đã lọc
    const historyTableRows = document.querySelectorAll('#history-table-body tr'); // Các dòng dữ liệu
    const resultCountEl = document.getElementById('result-count');      // Hiển thị số kết quả

    const STORAGE_PREFIX = 'smart_logistics_filter_state_';

    // Khôi phục trạng thái bộ lọc từ LocalStorage khi tải trang
    function restoreFilterState() {
        if (!searchInput) return;
        const savedSearch = localStorage.getItem(STORAGE_PREFIX + 'search');
        const savedStatus = localStorage.getItem(STORAGE_PREFIX + 'status');
        const savedSource = localStorage.getItem(STORAGE_PREFIX + 'source');
        const savedStart = localStorage.getItem(STORAGE_PREFIX + 'start');
        const savedEnd = localStorage.getItem(STORAGE_PREFIX + 'end');

        if (savedSearch && searchInput) searchInput.value = savedSearch;
        if (savedStatus && statusSelect) statusSelect.value = savedStatus;
        if (savedSource && sourceSelect) sourceSelect.value = savedSource;
        if (savedStart && startDateInput) startDateInput.value = savedStart;
        if (savedEnd && endDateInput) endDateInput.value = savedEnd;
    }

    // Lưu trạng thái bộ lọc vào LocalStorage
    function saveFilterState() {
        if (!searchInput) return;
        localStorage.setItem(STORAGE_PREFIX + 'search', searchInput.value);
        localStorage.setItem(STORAGE_PREFIX + 'status', statusSelect ? statusSelect.value : '');
        localStorage.setItem(STORAGE_PREFIX + 'source', sourceSelect ? sourceSelect.value : '');
        localStorage.setItem(STORAGE_PREFIX + 'start', startDateInput ? startDateInput.value : '');
        localStorage.setItem(STORAGE_PREFIX + 'end', endDateInput ? endDateInput.value : '');
    }

    // Hàm xóa hiệu ứng tô sáng cũ
    function removeHighlights(cell) {
        if (!cell) return;
        cell.innerHTML = cell.textContent;
    }

    // Hàm tô sáng từ khóa tìm kiếm (Highlighting)
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

    // Hàm thực thi bộ lọc chính
    function applyFilters() {
        const keyword = searchInput ? searchInput.value.trim().toLowerCase() : '';
        const selectedStatus = statusSelect ? statusSelect.value.trim().toLowerCase() : '';
        const selectedSource = sourceSelect ? sourceSelect.value.trim().toLowerCase() : '';
        const startDate = startDateInput && startDateInput.value ? new Date(startDateInput.value) : null;
        const endDate = endDateInput && endDateInput.value ? new Date(endDateInput.value) : null;
        
        // Đặt giờ kết thúc đến cuối ngày để bao trọn dữ liệu trong ngày đó
        if (endDate) {
            endDate.setHours(23, 59, 59, 999);
        }

        let visibleCount = 0;

        historyTableRows.forEach(row => {
            const codeCell = row.cells[1]; // Cột mã kiện
            const timeCell = row.cells[0]; // Cột thời gian
            
            const parcelCode = (row.getAttribute('data-code') || (codeCell ? codeCell.innerText : '')).toLowerCase();
            const status = (row.getAttribute('data-status') || (row.cells[4] ? row.cells[4].innerText : '')).toLowerCase();
            const source = (row.getAttribute('data-source') || (row.cells[6] ? row.cells[6].innerText : '')).toLowerCase();
            const rowTimeString = row.getAttribute('data-time') || (timeCell ? timeCell.innerText : '');

            // Kiểm tra điều kiện từ khóa & danh mục
            let matchKeyword = parcelCode.includes(keyword);
            let matchStatus = !selectedStatus || status.includes(selectedStatus);
            let matchSource = !selectedSource || source.includes(selectedSource);

            // Kiểm tra điều kiện khoảng thời gian
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
                // Tô sáng từ khóa tại ô mã kiện
                if (codeCell && keyword) {
                    highlightText(codeCell, keyword);
                } else if (codeCell) {
                    removeHighlights(codeCell);
                }
            } else {
                row.style.display = 'none';
                if (codeCell) removeHighlights(codeCell);
            }
        });

        // Cập nhật số lượng hiển thị
        if (resultCountEl) {
            resultCountEl.innerText = `Hiển thị ${visibleCount} / ${historyTableRows.length} kết quả phù hợp`;
        }

        saveFilterState();
    }

    // Đăng ký sự kiện lắng nghe tương tác
    if (searchInput) searchInput.addEventListener('input', applyFilters);
    if (statusSelect) statusSelect.addEventListener('change', applyFilters);
    if (sourceSelect) sourceSelect.addEventListener('change', applyFilters);
    if (startDateInput) startDateInput.addEventListener('change', applyFilters);
    if (endDateInput) endDateInput.addEventListener('change', applyFilters);

    // Nút xóa bộ lọc
    if (clearBtn) {
        clearBtn.addEventListener('click', function () {
            if (searchInput) searchInput.value = '';
            if (statusSelect) statusSelect.value = '';
            if (sourceSelect) sourceSelect.value = '';
            if (startDateInput) startDateInput.value = '';
            if (endDateInput) endDateInput.value = '';
            
            // Xóa LocalStorage
            localStorage.removeItem(STORAGE_PREFIX + 'search');
            localStorage.removeItem(STORAGE_PREFIX + 'status');
            localStorage.removeItem(STORAGE_PREFIX + 'source');
            localStorage.removeItem(STORAGE_PREFIX + 'start');
            localStorage.removeItem(STORAGE_PREFIX + 'end');

            applyFilters();
        });
    }

    // Nút xuất file CSV chỉ lấy các dòng đang hiển thị sau khi lọc
    if (exportFilteredBtn) {
        exportFilteredBtn.addEventListener('click', function () {
            let csvContent = "data:text/csv;charset=utf-8,ThoiGian,MaDonHang,TrangThai,NguonNhap\n";
            let exportedRowsCount = 0;

            historyTableRows.forEach(row => {
                if (row.style.display !== 'none') {
                    const cols = row.querySelectorAll('td');
                    if (cols.length >= 7) {
                        const timeVal = cols[0].innerText.trim();
                        const codeVal = cols[1].innerText.trim();
                        const statusVal = cols[4].innerText.trim();
                        const sourceVal = cols[6].innerText.trim();
                        csvContent += `"${timeVal}","${codeVal}","${statusVal}","${sourceVal}"\n`;
                        exportedRowsCount++;
                    }
                }
            });

            if (exportedRowsCount === 0) {
                alert("Không có dữ liệu phù hợp để xuất file!");
                return;
            }

            const encodedUri = encodeURI(csvContent);
            const link = document.createElement("a");
            link.setAttribute("href", encodedUri);
            link.setAttribute("download", "filtered_logistics_history.csv");
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        });
    }

    // Khởi chạy ban đầu
    restoreFilterState();
    applyFilters();
});