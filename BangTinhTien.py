import streamlit as st
import easyocr
import pandas as pd
import json
import numpy as np
from PIL import Image, ImageEnhance

# --- CẤU HÌNH QUY LUẬT BÓNG & HIỆU (THEO IMAGE_484E54.PNG) ---
BONG_DUONG = {0:5, 1:6, 2:7, 3:8, 4:9, 5:0, 6:1, 7:2, 8:3, 9:4}
BONG_AM = {0:7, 1:4, 2:9, 3:6, 4:1, 5:8, 6:3, 7:0, 8:5, 9:2}
HIEU_CHART = {0: [0,11,22,33,44,55,66,77,88,99], 1: [9,10,21,32,43,54,65,76,87,98],
              2: [8,19,20,31,42,53,64,75,86,97], 3: [7,18,29,30,41,52,63,74,85,96],
              4: [6,17,28,39,40,51,62,73,84,95], 5: [5,16,27,38,49,50,61,72,83,94],
              6: [4,15,26,37,48,59,60,71,82,93], 7: [3,14,25,36,47,58,69,70,81,92],
              8: [2,13,24,35,46,57,68,79,80,91], 9: [1,12,23,34,45,56,67,78,89,90]}

st.set_page_config(page_title="BANG TINH TIEN", layout="wide")
st.title("📊 BANG TINH TIEN")

# --- KHỞI TẠO BỘ NHỚ ---
if 'db' not in st.session_state:
    st.session_state.db = {
        "bang_b_points": [], 
        "last_gdb_full": "", 
        "history": [],
        "max_scores": {"dau": 0, "duoi": 0, "tong": 0, "hieu": 0, "cham": 0}
    }

@st.cache_resource
def load_ocr():
    return easyocr.Reader(['en'], gpu=False)

def get_hieu(n):
    return next((h for h, nums in HIEU_CHART.items() if n in nums), 0)

def build_bang_a(gdb_str):
    """Xây dựng Bảng A: Tiến và Bóng âm dương (120 vị trí)"""
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
    """Hàm lõi cập nhật điểm Bảng B nối tiếp dữ liệu"""
    gdb_clean = "".join([d for d in gdb_full if d.isdigit()])
    if len(gdb_clean) > 6: gdb_clean = gdb_clean[-6:]
    if len(gdb_clean) < 5: return

    # Khởi tạo hoặc duy trì 120 vị trí điểm
    if not st.session_state.db["bang_b_points"] or len(st.session_state.db["bang_b_points"]) != 120:
        st.session_state.db["bang_b_points"] = [{"dau":1,"duoi":1,"tong":1,"hieu":1,"cham":1} for _ in range(120)]
    
    last_2 = int(gdb_clean[-2:])
    target = {
        "dau": int(gdb_clean[-2]), "duoi": int(gdb_clean[-1]),
        "tong": (int(gdb_clean[-2]) + int(gdb_clean[-1])) % 10,
        "hieu": get_hieu(last_2), "cham": [int(gdb_clean[-2]), int(gdb_clean[-1])]
    }

    rank_val, status_val = "N/A", "N/A"
    if st.session_state.db.get("last_gdb_full"):
        t_old, b_old = build_bang_a(st.session_state.db["last_gdb_full"])
        all_a_old = [item for sub in t_old for item in sub] + [item for sub in b_old for item in sub]
        pts_b = st.session_state.db["bang_b_points"]
        limit = min(len(all_a_old), len(pts_b))
        
        # Tính Rank (Vị trí) trước khi reset
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

        # Cập nhật điểm tịnh tiến
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

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ ĐIỀU KHIỂN")
    uploaded_json = st.file_uploader("📂 Load file .Json", type=["json"])
    if uploaded_json:
        st.session_state.db = json.load(uploaded_json)
        st.success("Đã nạp dữ liệu!")

    manual_gdb = st.text_input("✍️ Nhập tay GĐB:")
    if st.button("➕ Thêm thủ công"):
        update_logic(manual_gdb)
        st.rerun()

    st.divider()
    uploaded_file = st.file_uploader("📸 Load ảnh mới (Bảng tháng)", type=["png", "jpg", "jpeg"])
    
    if st.button("🔍 QUÉT ẢNH (DỌC CỘT - NỐI TIẾP)"):
        if uploaded_file:
            with st.spinner("Đang xử lý ảnh theo cột..."):
                img = Image.open(uploaded_file).convert('L')
                img = ImageEnhance.Contrast(img).enhance(2.0)
                results = load_ocr().readtext(np.array(img))
                
                found = []
                for (bbox, text, prob) in results:
                    clean = "".join([d for d in text if d.isdigit()])
                    if len(clean) >= 5:
                        # Chỉ lấy 6 số cuối để tránh rác
                        gdb_val = clean[-6:] if len(clean) >= 6 else clean
                        found.append({"gdb": gdb_val, "y": bbox[0][1], "x": bbox[0][0]})
                
                # SẮP XẾP CHUẨN: X trước (Cột), Y sau (Dòng từ trên xuống)
                # Dùng threshold 70px để gom cột chính xác
                found.sort(key=lambda k: (k['x'] // 70, k['y']))
                
                for item in found:
                    update_logic(item['gdb'])
                st.success(f"Đã nạp nối tiếp {len(found)} kỳ GĐB!")
                st.rerun()

    if st.button("❌ RESET DỮ LIỆU"):
        st.session_state.db = {"bang_b_points": [], "last_gdb_full": "", "history": [], "max_scores": {"dau": 0, "duoi": 0, "tong": 0, "hieu": 0, "cham": 0}}
        st.rerun()

# --- HIỂN THỊ CHÍNH ---
if st.session_state.db.get("last_gdb_full"):
    gdb_now = st.session_state.db["last_gdb_full"]
    tien_a, bong_a = build_bang_a(gdb_now)
    all_a_now = [item for sub in tien_a for item in sub] + [item for sub in bong_a for item in sub]
    pts_b = st.session_state.db["bang_b_points"]
    limit_now = min(len(all_a_now), len(pts_b))

    list_c = []
    for n in range(10):
        row = {"Số": n, "Đầu": 0, "Đuôi": 0, "Tổng": 0, "Hiệu": 0, "Chạm": 0}
        for i in range(limit_now):
            if all_a_now[i] == n:
                row["Đầu"] += pts_b[i]["dau"]; row["Đuôi"] += pts_b[i]["duoi"]; row["Tổng"] += pts_b[i]["tong"]; row["Hiệu"] += pts_b[i]["hieu"]; row["Chạm"] += pts_b[i]["cham"]
        list_c.append(row)
    df_c = pd.DataFrame(list_c)

    dan_d = []
    for i in range(100):
        x, y = i // 10, i % 10
        score = df_c.iloc[x]["Đầu"] + df_c.iloc[y]["Đuôi"] + df_c.iloc[(x+y)%10]["Tổng"] + df_c.iloc[get_hieu(i)]["Hiệu"]
        score += (df_c.iloc[x]["Chạm"] * 2) if x == y else (df_c.iloc[x]["Chạm"] + df_c.iloc[y]["Chạm"])
        dan_d.append({"SO": f"{i:02d}", "DIEM": int(score)})
    df_dan = pd.DataFrame(dan_d).sort_values("DIEM", ascending=False)

    st.subheader(f"🛡️ GĐB Hiện Tại: {gdb_now}")
    c1, c2 = st.columns(2)
    with c1: st.text_area("Dàn 1 (49 số):", " ".join(df_dan.head(49)["SO"].tolist()), height=100)
    with c2: st.text_area("Dàn 2 (64 số):", " ".join(df_dan.head(64)["SO"].tolist()), height=100)

    tabs = st.tabs(["🕒 Lịch sử", "🎲 Bảng B (Điểm & Thống kê)", "🗂️ Bảng C", "🎲 Bảng D", "📊 Bảng A"])
    
    with tabs[1]:
        # BẢNG THỐNG KÊ TRẠNG THÁI CAO ĐIỂM NHẤT
        st.subheader("📊 Thống kê Trạng thái Cao điểm nhất")
        stats_data = []
        labels = ["Cao diem nhat", "Cao diem nhi", "Cao diem ba", "Cao diem bon"]
        cols = ["dau", "duoi", "tong", "hieu", "cham"]
        
        for idx, label in enumerate(labels):
            row_stat = {"TRANG THAI": label}
            for c in cols:
                sorted_idx = sorted(range(limit_now), key=lambda k: pts_b[k][c], reverse=True)
                top_vtri = sorted_idx[idx]
                score = pts_b[top_vtri][c]
                val_a = all_a_now[top_vtri]
                row_stat[c.upper()] = f"{score} (VT:{top_vtri+1}, Số:{val_a})"
            stats_data.append(row_stat)
        
        max_ls_row = {"TRANG THAI": "Max Diem LS"}
        for c in cols: max_ls_row[c.upper()] = st.session_state.db["max_scores"][c]
        stats_data.append(max_ls_row)
        st.table(pd.DataFrame(stats_data))

        st.divider()
        st.subheader("Chi tiết 120 vị trí")
        display_b = [{"VT": i+1, "Số (A)": all_a_now[i], "Đầu": pts_b[i]["dau"], "Đuôi": pts_b[i]["duoi"], "Tổng": pts_b[i]["tong"], "Hiệu": pts_b[i]["hieu"], "Chạm": pts_b[i]["cham"]} for i in range(limit_now)]
        st.dataframe(pd.DataFrame(display_b), use_container_width=True, hide_index=True)

    with tabs[0]: st.dataframe(pd.DataFrame(st.session_state.db["history"]), use_container_width=True, hide_index=True)
    with tabs[2]: st.table(df_c)
    with tabs[3]: st.dataframe(df_dan.set_index("SO").T, use_container_width=True)
    with tabs[4]:
        ca1, ca2 = st.columns(2); ca1.table(pd.DataFrame(tien_a)); ca2.table(pd.DataFrame(bong_a))

    st.sidebar.download_button("💾 Lưu file .Json", json.dumps(st.session_state.db), "bang_tinh_tien.json")
else: st.info("👋 Hãy load ảnh bảng tháng hoặc nhập GĐB để bắt đầu.")
