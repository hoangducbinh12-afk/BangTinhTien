import streamlit as st
import easyocr
import pandas as pd
import json
import numpy as np
from PIL import Image, ImageEnhance

# --- CẤU HÌNH QUY LUẬT (GIỮ NGUYÊN) ---
BONG_DUONG = {0:5, 1:6, 2:7, 3:8, 4:9, 5:0, 6:1, 7:2, 8:3, 9:4}
BONG_AM = {0:7, 1:4, 2:9, 3:6, 4:1, 5:8, 6:3, 7:0, 8:5, 9:2}
HIEU_CHART = {0: [0,11,22,33,44,55,66,77,88,99], 1: [9,10,21,32,43,54,65,76,87,98],
              2: [8,19,20,31,42,53,64,75,86,97], 3: [7,18,29,30,41,52,63,74,85,96],
              4: [6,17,28,39,40,51,62,73,84,95], 5: [5,16,27,38,49,50,61,72,83,94],
              6: [4,15,26,37,48,59,60,71,82,93], 7: [3,14,25,36,47,58,69,70,81,92],
              8: [2,13,24,35,46,57,68,79,80,91], 9: [1,12,23,34,45,56,67,78,89,90]}

st.set_page_config(page_title="BANG TINH TIEN", layout="wide")
st.title("📊 BANG TINH TIEN")

if 'db' not in st.session_state:
    st.session_state.db = {"bang_b_points": [], "last_gdb_full": "", "history": [], "max_scores": {"dau": 0, "duoi": 0, "tong": 0, "hieu": 0, "cham": 0}}

@st.cache_resource
def load_ocr():
    return easyocr.Reader(['en'], gpu=False)

def get_hieu(n):
    return next((h for h, nums in HIEU_CHART.items() if n in nums), 0)

def build_bang_a(gdb_str):
    if not gdb_str: return [], []
    digits = [int(d) for d in gdb_str[-5:]] 
    tien = [[(d + step) % 10 for d in digits] for step in range(10)]
    bong = [digits]
    current = digits
    for i in range(9):
        current = [BONG_DUONG[d] for d in current] if i % 2 == 0 else [BONG_AM[d] for d in current]
        bong.append(current)
    return tien, bong

def update_logic(gdb_full):
    """Hàm lõi cập nhật điểm Bảng B"""
    gdb_clean = "".join([d for d in gdb_full if d.isdigit()])
    if len(gdb_clean) > 6: gdb_clean = gdb_clean[-6:] # Cắt lấy GĐB nếu dính số ngày
    if len(gdb_clean) < 5: return

    if not st.session_state.db["bang_b_points"] or len(st.session_state.db["bang_b_points"]) != 120:
        st.session_state.db["bang_b_points"] = [{"dau":1,"duoi":1,"tong":1,"hieu":1,"cham":1} for _ in range(120)]
    
    last_2 = int(gdb_clean[-2:])
    target = {"dau": int(gdb_clean[-2]), "duoi": int(gdb_clean[-1]), "tong": (int(gdb_clean[-2]) + int(gdb_clean[-1])) % 10, "hieu": get_hieu(last_2), "cham": [int(gdb_clean[-2]), int(gdb_clean[-1])]}
    
    rank_val, status_val = "N/A", "N/A"
    if st.session_state.db.get("last_gdb_full"):
        t_old, b_old = build_bang_a(st.session_state.db["last_gdb_full"])
        all_a_old = [item for sub in t_old for item in sub] + [item for sub in b_old for item in sub]
        pts_b = st.session_state.db["bang_b_points"]
        limit = min(len(all_a_old), len(pts_b))
        
        # Tính Rank
        list_c_tmp = []
        for n in range(10):
            row = {"S": n, "da": 0, "du": 0, "to": 0, "hi": 0, "ch": 0}
            for i in range(limit):
                if all_a_old[i] == n:
                    row["da"] += pts_b[i]["dau"]; row["du"] += pts_b[i]["duoi"]; row["to"] += pts_b[i]["tong"]; row["hi"] += pts_b[i]["hieu"]; row["ch"] += pts_b[i]["cham"]
            list_c_tmp.append(row)
        
        dan_tmp = []
        for i in range(100):
            x, y = i // 10, i % 10
            score = list_c_tmp[x]["da"] + list_c_tmp[y]["du"] + list_c_tmp[(x+y)%10]["to"] + list_c_tmp[get_hieu(i)]["hi"]
            score += (list_c_tmp[x]["ch"] * 2) if x == y else (list_c_tmp[x]["ch"] + list_c_tmp[y]["ch"])
            dan_tmp.append({"SO": f"{i:02d}", "DIEM": score})
        
        df_rank = pd.DataFrame(dan_tmp).sort_values("DIEM", ascending=False).reset_index(drop=True)
        find_idx = df_rank[df_rank["SO"] == f"{last_2:02d}"].index
        if len(find_idx) > 0:
            rank_val = int(find_idx[0]) + 1
            status_val = "A" if rank_val <= 79 else "T"

        # Cập nhật điểm
        for i in range(limit):
            val = all_a_old[i]
            p = pts_b[i]
            for key in ["dau", "duoi", "tong", "hieu"]:
                p[key] = 0 if val == target[key] else p[key] + 1
                if p[key] > st.session_state.db["max_scores"][key]: st.session_state.db["max_scores"][key] = p[key]
            p["cham"] = 0 if val in target["cham"] else p["cham"] + 1
            if p["cham"] > st.session_state.db["max_scores"]["cham"]: st.session_state.db["max_scores"]["cham"] = p["cham"]

    st.session_state.db["last_gdb_full"] = gdb_clean
    st.session_state.db["history"].insert(0, {"Số về": f"{last_2:02d}", "Vị trí": rank_val, "Trạng thái": status_val, "GĐB Full": gdb_clean})

# --- GIAO DIỆN ---
with st.sidebar:
    st.header("⚙️ ĐIỀU KHIỂN")
    uploaded_json = st.file_uploader("📂 Load file .Json", type=["json"])
    if uploaded_json: st.session_state.db = json.load(uploaded_json)
    
    manual_gdb = st.text_input("✍️ Nhập tay GĐB:")
    if st.button("➕ Thêm thủ công"): update_logic(manual_gdb); st.rerun()
    
    st.divider()
    uploaded_file = st.file_uploader("📸 Load ảnh bảng tháng", type=["png", "jpg", "jpeg"])
    
    if st.button("🔍 QUÉT ẢNH (DỌC CỘT - BẢN FIX)"):
        if uploaded_file:
            with st.spinner("Đang bóc tách dữ liệu theo cột..."):
                img = Image.open(uploaded_file).convert('L')
                img = ImageEnhance.Contrast(img).enhance(2.0)
                results = load_ocr().readtext(np.array(img))
                
                raw_data = []
                for (bbox, text, prob) in results:
                    clean = "".join([d for d in text if d.isdigit()])
                    if len(clean) >= 5:
                        raw_data.append({
                            "val": clean[-6:] if len(clean) >= 6 else clean,
                            "x": (bbox[0][0] + bbox[2][0]) / 2, # Tâm X
                            "y": (bbox[0][1] + bbox[2][1]) / 2  # Tâm Y
                        })
                
                if raw_data:
                    # Logic sắp xếp cột thông minh
                    df_scan = pd.DataFrame(raw_data)
                    # Gom các X gần nhau vào cùng 1 nhóm cột (sai số 50px)
                    df_scan['col_group'] = (df_scan['x'] / 50).astype(int)
                    # Sắp xếp theo nhóm cột (trái -> phải), sau đó theo Y (trên -> dưới)
                    df_scan = df_scan.sort_values(by=['col_group', 'y'])
                    
                    for _, row in df_scan.iterrows():
                        update_logic(row['val'])
                    
                    st.success(f"Đã nạp nối tiếp {len(df_scan)} kỳ!")
                    st.rerun()

    if st.button("❌ RESET DỮ LIỆU"):
        st.session_state.db = {"bang_b_points": [], "last_gdb_full": "", "history": [], "max_scores": {"dau": 0, "duoi": 0, "tong": 0, "hieu": 0, "cham": 0}}
        st.rerun()

# --- HIỂN THỊ (GIỮ NGUYÊN) ---
if st.session_state.db.get("last_gdb_full"):
    gdb_now = st.session_state.db["last_gdb_full"]
    tien_a, bong_a = build_bang_a(gdb_now); all_a_now = [item for sub in tien_a for item in sub] + [item for sub in bong_a for item in sub]
    pts_b = st.session_state.db["bang_b_points"]; limit_now = min(len(all_a_now), len(pts_b))

    df_dan = pd.DataFrame([{"SO": f"{i:02d}", "DIEM": 0} for i in range(100)]) # Placeholder logic
    # (Phần hiển thị bảng C, D, A mày giữ nguyên như bản trước tao gửi nhé)
    st.write(f"### Kỳ hiện tại: {gdb_now}")
    st.info("💡 Mày dùng các Tab bên dưới để soi điểm và thống kê nhé.")

    st.sidebar.download_button("💾 Lưu file .Json", json.dumps(st.session_state.db), "bang_tinh_tien.json")
