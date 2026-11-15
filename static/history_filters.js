// === HỆ THỐNG LỊCH SỬ QUÉT AI-POWERED ENTERPRISE EDITION ===
document.addEventListener('DOMContentLoaded', function () {
    const searchInput = document.getElementById('search-parcel');     
    const statusSelect = document.getElementById('filter-status');    
    const sourceSelect = document.getElementById('filter-source');    
    const startDateInput = document.getElementById('filter-start-date'); 
    const endDateInput = document.getElementById('filter-end-date');     
    const clearBtn = document.getElementById('clear-filters-btn');      
    const exportFilteredBtn = document.getElementById('export-filtered-btn'); 
    const printReportBtn = document.getElementById('print-report-btn'); 
    
    const historyTableBody = document.getElementById('history-table-body');
    const historyTableRows = historyTableBody ? Array.from(historyTableBody.querySelectorAll('tr')) : []; 
    const resultCountEl = document.getElementById('result-count');      

    // Thống kê nhanh & Tiến độ
    const statTotalEl = document.getElementById('stat-total');
    const statSuccessEl = document.getElementById('stat-success');
    const statPendingEl = document.getElementById('stat-pending');
    const progressBarEl = document.getElementById('success-progress-bar'); 

    // Phân trang
    let currentPage = 1;
    const rowsPerPage = 15; 

    const STORAGE_PREFIX = 'smart_logistics_ai_enterprise_';

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

    // 2. Highlighting từ khóa thông minh
    function highlightText(cell, keyword) {
        if (!cell) return;
        const originalText = cell.textContent;
        if (!keyword) {
            cell.innerHTML = originalText;
            return;
        }
        const regex = new RegExp(`(${keyword})`, 'gi');
        if (regex.test(originalText)) {
            cell.innerHTML = originalText.replace(regex, '<mark class="bg-warning px-1 rounded shadow-sm">$1</mark>');
        } else {
            cell.innerHTML = originalText;
        }
    }

    // 3. Hàm lọc chính với Cú pháp nâng cao & Hiệu ứng mượt mà
    function applyFilters() {
        const rawQuery = searchInput ? searchInput.value.trim().toLowerCase() : '';
        let keyword = rawQuery;
        let queryStatusOverride = '';
        let querySourceOverride = '';

        // Hỗ trợ cú pháp nâng cao dạng "status:thành công" hoặc "source:qr"
        if (rawQuery.includes('status:')) {
            const parts = rawQuery.split('status:');
            keyword = parts[0].trim();
            queryStatusOverride = parts[1].split(' ')[0].trim();
        }
        if (rawQuery.includes('source:')) {
            const parts = rawQuery.split('source:');
            keyword = parts[0].trim();
            querySourceOverride = parts[1].split(' ')[0].trim();
        }

        const selectedStatus = queryStatusOverride || (statusSelect ? statusSelect.value.trim().toLowerCase() : '');
        const selectedSource = querySourceOverride || (sourceSelect ? sourceSelect.value.trim().toLowerCase() : '');
        const startDate = startDateInput && startDateInput.value ? new Date(startDateInput.value) : null;
        const endDate = endDateInput && endDateInput.value ? new Date(endDateInput.value) : null;
        
        if (endDate) endDate.setHours(23, 59, 59, 999);

        let filteredRows = [];
        let successCount = 0;
        let pendingCount = 0;

        historyTableRows.forEach(row => {
            const codeCell = row.cells[1]; 
            const timeCell = row.cells[0]; 
            
            const parcelCode = (row.getAttribute('data-code') || (codeCell ? codeCell.innerText : '')).toLowerCase();
            const status = (row.getAttribute('data-status') || (row.cells[4] ? row.cells[4].innerText : '')).toLowerCase();
            const source = (row.getAttribute('data-source') || (row.cells[6] ? row.cells[6].innerText : '')).toLowerCase();
            const rowTimeString = row.getAttribute('data-time') || (timeCell ? timeCell.innerText : '');

            let matchKeyword = !keyword || parcelCode.includes(keyword);
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
                filteredRows.push(row);
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

        // Phân trang
        const totalFiltered = filteredRows.length;
        const totalPages = Math.ceil(totalFiltered / rowsPerPage) || 1;
        if (currentPage > totalPages) currentPage = totalPages;

        const startIndex = (currentPage - 1) * rowsPerPage;
        const endIndex = startIndex + rowsPerPage;

        historyTableRows.forEach(row => { row.style.display = 'none'; });

        for (let i = startIndex; i < endIndex && i < totalFiltered; i++) {
            const row = filteredRows[i];
            row.style.display = '';
            // Hiệu ứng Fade-in mượt mà khi hiển thị
            row.style.opacity = '0';
            setTimeout(() => { row.style.opacity = '1'; row.style.transition = 'opacity 0.3s ease-in-out'; }, 50);
        }

        // Cập nhật giao diện thống kê
        if (resultCountEl) {
            resultCountEl.innerText = `Hiển thị ${totalFiltered} / ${historyTableRows.length} kết quả phù hợp (Trang ${currentPage}/${totalPages})`;
        }
        if (statTotalEl) statTotalEl.innerText = totalFiltered;
        if (statSuccessEl) statSuccessEl.innerText = successCount;
        if (statPendingEl) statPendingEl.innerText = pendingCount;

        if (progressBarEl && totalFiltered > 0) {
            const successPercent = (successCount / totalFiltered) * 100;
            progressBarEl.style.width = successPercent + '%';
            progressBarEl.setAttribute('aria-valuenow', successPercent);
        }

        saveFilterState();
    }

    // 4. Phím tắt thông minh (Keyboard Shortcuts: Ctrl+K để tìm kiếm, Esc để reset)
    document.addEventListener('keydown', function (e) {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
            e.preventDefault();
            if (searchInput) {
                searchInput.focus();
                searchInput.select();
            }
        } else if (e.key === 'Escape') {
            if (clearBtn) clearBtn.click();
        }
    });

    // 5. Sắp xếp cột bảng (Sorting)
    const tableHeaders = document.querySelectorAll('#history-table th');
    tableHeaders.forEach((th, index) => {
        th.style.cursor = 'pointer';
        th.title = 'Bấm để sắp xếp';
        let isAsc = true;
        th.addEventListener('click', function () {
            isAsc = !isAsc;
            historyTableRows.sort((rowA, rowB) => {
                const valA = rowA.cells[index] ? rowA.cells[index].innerText.trim() : '';
                const valB = rowB.cells[index] ? rowB.cells[index].innerText.trim() : '';
                return isAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
            });
            historyTableRows.forEach(row => historyTableBody.appendChild(row));
            applyFilters();
        });
    });

    // 6. Sao chép nhanh khi bấm đúp chuột
    if (historyTableBody) {
        historyTableBody.addEventListener('dblclick', function (e) {
            const cell = e.target.closest('td');
            if (cell && cell.cellIndex === 1) {
                const textToCopy = cell.textContent.trim();
                navigator.clipboard.writeText(textToCopy).then(() => {
                    const originalBg = cell.style.backgroundColor;
                    cell.style.backgroundColor = '#d1e7dd';
                    setTimeout(() => { cell.style.backgroundColor = originalBg; }, 500);
                });
            }
        });
    }

    // 7. Lắng nghe sự kiện
    if (searchInput) searchInput.addEventListener('input', () => { currentPage = 1; applyFilters(); });
    if (statusSelect) statusSelect.addEventListener('change', () => { currentPage = 1; applyFilters(); });
    if (sourceSelect) sourceSelect.addEventListener('change', () => { currentPage = 1; applyFilters(); });
    if (startDateInput) startDateInput.addEventListener('change', () => { currentPage = 1; applyFilters(); });
    if (endDateInput) endDateInput.addEventListener('change', () => { currentPage = 1; applyFilters(); });

    if (clearBtn) {
        clearBtn.addEventListener('click', function () {
            if (searchInput) searchInput.value = '';
            if (statusSelect) statusSelect.value = '';
            if (sourceSelect) sourceSelect.value = '';
            if (startDateInput) startDateInput.value = '';
            if (endDateInput) endDateInput.value = '';
            localStorage.clear();
            currentPage = 1;
            applyFilters();
        });
    }

    // 8. Xuất CSV thông minh
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
            link.setAttribute("download", "smart_logistics_ai_enterprise_history.csv");
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        });
    }

    // 9. In báo cáo / Lưu PDF chuyên nghiệp
    if (printReportBtn) {
        printReportBtn.addEventListener('click', function () {
            window.print();
        });
    }

    // Khởi chạy hệ thống
    restoreFilterState();
    applyFilters();
});