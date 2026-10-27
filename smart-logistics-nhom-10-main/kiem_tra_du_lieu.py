import sys
from pathlib import Path
import pandas as pd

def run_validation():
    base_dir = Path(__file__).resolve().parent
    has_error = False

    def log_error(msg):
        nonlocal has_error
        has_error = True
        print(f"[LỖI NGHIỆP VỤ] {msg}")

    print("Bắt đầu kiểm tra tính hợp lệ của dữ liệu đầu vào Phần 1...")

    # 1. Kiểm tra file quy tắc phân cửa
    rules_path = base_dir / 'data' / 'processed' / 'routing_rules.csv'
    if not rules_path.exists():
        log_error(f"Không tìm thấy file routing_rules.csv tại {rules_path}")
        sys.exit(1)
    
    rules_df = pd.read_csv(rules_path)

    # 2. Đọc file parcels tổng ở thư mục processed hoặc tìm theo reference
    parcel_path = base_dir / 'data' / 'processed' / 'parcels.csv'
    if not parcel_path.exists():
        parcel_path = base_dir / 'data' / 'reference' / 'demo' / 'parcels.csv' # Fallback

    if not parcel_path.exists():
        log_error(f"Không tìm thấy file parcels.csv tại {parcel_path}")
        sys.exit(1)

    parcels_df = pd.read_csv(parcel_path)
    print(f"Tổng số dòng trong parcels.csv: {len(parcels_df)}")

    # Kiểm tra tổng số 60 kiện
    if len(parcels_df) != 60:
        log_error(f"Tổng số kiện là {len(parcels_df)}, yêu cầu chuẩn đúng 60 kiện.")

    # 3. Kiểm tra từng subset (demo và final_test)
    subsets = ['demo', 'final_test']
    global_codes = set()
    global_orders = set()

    for subset in subsets:
        if 'subset' in parcels_df.columns:
            subset_df = parcels_df[parcels_df['subset'] == subset]
        else:
            # Nếu file phân tách theo thư mục reference
            sub_path = base_dir / 'data' / 'reference' / subset / 'parcels.csv'
            if sub_path.exists():
                subset_df = pd.read_csv(sub_path)
            else:
                subset_df = pd.DataFrame()

        print(f"Kiểm tra tập [{subset}]: {len(subset_df)} kiện.")

        if len(subset_df) != 30:
            log_error(f"Tập {subset} có {len(subset_df)} kiện (Yêu cầu đúng 30 kiện).")

        # Kiểm tra trùng lặp nội bộ và toàn cục
        for _, row in subset_df.iterrows():
            code = row.get('code')
            order_id = row.get('order_id')

            if code in global_codes:
                log_error(f"Mã kiện {code} bị trùng lặp.")
            global_codes.add(code)

            if order_id in global_orders:
                log_error(f"Mã đơn nguồn {order_id} bị trùng lặp.")
            global_orders.add(order_id)

        # Kiểm tra đối chiếu ảnh QR trong thư mục tương ứng
        img_folder = base_dir / 'data' / 'reference' / subset
        if not img_folder.exists():
            img_folder = base_dir / subset

        if img_folder.exists():
            existing_imgs = {p.stem for p in img_folder.glob('*.png')}
            csv_codes = set(subset_df['code'].astype(str))
            missing_imgs = csv_codes - existing_imgs
            if missing_imgs:
                log_error(f"Tập {subset} thiếu file ảnh QR cho các mã: {sorted(missing_imgs)}")
        else:
            log_error(f"Không tìm thấy thư mục ảnh QR cho tập {subset} tại {img_folder}")

    # 4. Kết quả cuối cùng & trả mã thoát
    if has_error:
        print("\n❌ KẾT QUẢ: Kiểm tra dữ liệu THẤT BẠI. (Trả về mã thoát 1)")
        sys.exit(1)
    else:
        print("\n✅ KẾT QUẢ: Tất cả dữ liệu đầu vào đều HỢP LỆ và chính xác tuyệt đối!")
        sys.exit(0)

if __name__ == '__main__':
    run_validation()