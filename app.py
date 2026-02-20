import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
import json

# ==========================================
# 1. 설정 및 연결 (배포용 수정판)
# ==========================================
st.set_page_config(layout="wide", page_title="현장 게이지 관리")

@st.cache_resource
def connect_to_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    
    # 1. 스트림릿 클라우드(배포) 환경일 때 (Secrets 사용)
    if "google_secret_json" in st.secrets:
        secret_dict = json.loads(st.secrets["google_secret_json"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(secret_dict, scope)
    # 2. 내 컴퓨터(로컬) 환경일 때 (파일 사용)
    else:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(current_dir, "secrets.json")
        creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, scope)
        
    client = gspread.authorize(creds)
    return client

SHEET_FILE_NAME = "Gauges_System" 

# [추가됨] 데이터 로딩 함수 (이게 없어서 에러가 났던 겁니다!)
@st.cache_data(ttl=5)
def get_gauge_data():
    client = connect_to_sheet()
    sh = client.open(SHEET_FILE_NAME)
    return sh.worksheet("Status").get_all_records()

@st.cache_data(ttl=60)
def get_user_list():
    client = connect_to_sheet()
    sh = client.open(SHEET_FILE_NAME)
    raw_users = sh.worksheet("Users").col_values(1)
    return raw_users[1:] if raw_users and raw_users[0] == "이름" else raw_users

# ==========================================
# 2. 디자인 코드 (CSS)
# ==========================================
st.markdown("""
    <style>
    /* 화면 기본 설정 */
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container { padding: 3rem 2rem; max-width: 100%; background-color: #fcfcfc; }
    
    /* 기본 버튼 디자인 (40px) */
    div.stButton > button {
        width: 100%;             
        height: 125px !important;
        font-size: 40px !important; 
        font-weight: 800 !important; 
        border-radius: 25px !important; 
        border: 2px solid #ddd !important; 
        box-shadow: 0px 6px 12px rgba(0,0,0,0.08) !important; 
    }

    /* 1. 첫 페이지 '대여 시작하기' 버튼 (48px) */
    .start-btn-box div.stButton > button { font-size: 48px !important; }

    /* 2. 빨간색 강조 버튼 */
    div.stButton > button[kind="primary"], div.stFormSubmitButton > button[kind="primary"] {
        background-color: #e63946 !important; 
        color: white !important;              
        border: none !important;              
    }

    /* 3. 관리자 페이지 전용 사각형 2줄 버튼 */
    .square-btn div.stButton > button, .square-btn div.stFormSubmitButton > button {
        height: 120px !important;    
        white-space: pre-wrap !important; 
        line-height: 1.2 !important; 
        font-size: 35px !important;  
    }
    .btn-inspect div.stButton > button, .btn-inspect div.stFormSubmitButton > button { background-color: #ff4b4b !important; color: white !important; border: none !important;}
    .btn-complete div.stButton > button, .btn-complete div.stFormSubmitButton > button { background-color: #28a745 !important; color: white !important; border: none !important;}

    /* 4. [수정] 우측 상단 '관리' 버튼 (완벽한 정사각형, 이전 크기의 절반) */
    /* 특정 ID(admin-btn-target) 뒤에 오는 버튼을 타겟팅하여 모양을 고정시킵니다. */
    div.element-container:has(#admin-btn-target) + div.element-container div.stButton > button {
        width: 60px !important;      
        height: 60px !important;     
        min-width: 60px !important;  
        min-height: 0px !important; 
        font-size: 20px !important;  
        padding: 0 !important;
        border-radius: 15px !important;
        float: right !important;     /* 우측 정렬 */
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1) !important;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        white-space: pre-wrap !important;
        line-height: 1.2 !important;
    }

    /* 대여중인 게이지 목록 (48px) */
    .rent-list-box button {
        text-align: left !important; padding-left: 45px !important; font-size: 48px !important;  
        border-left: 25px solid #ff4b4b !important; background-color: white !important; color: #1a1a1a !important;   
    }
    .date-text { font-size: 40px !important; color: #666; font-weight: 500; }

    /* 검수 중인 게이지 (글씨 작게, 한 줄 고정) */
    .inspecting-card {
        background-color: #e9ecef; opacity: 0.7; border: 2px solid #ccc; border-radius: 15px;       
        padding: 0px 20px; margin-bottom: 15px; font-size: 26px; color: #555; height: 75px;              
        display: flex; align-items: center; pointer-events: none; white-space: nowrap;       
    }

    /* 선택창 및 입력창 (40px) */
    div[data-baseweb="select"] > div, div[data-baseweb="input"] > div {
        min-height: 115px !important; border-radius: 20px !important; display: flex !important;
        justify-content: center !important; align-items: center !important; border: 3px solid #eee !important;  
    }
    div[data-baseweb="select"] span { font-size: 40px !important; font-weight: 700 !important; text-align: center !important; width: 100% !important; color: black !important; }
    input[type="text"] { font-size: 40px !important; font-weight: 700 !important; text-align: center !important; color: black !important; }

    /* 기타 텍스트 */
    h1 { font-size: 60px !important; text-align: center; font-weight: 900; margin-bottom: 40px; }
    h2, h3 { font-size: 45px !important; text-align: center; font-weight: 800; color: #444; width: 100%; }
    .stAlert { font-size: 35px !important; border-radius: 20px; }
    .stDataFrame { font-size: 24px !important; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 3. 세션 상태 및 데이터 로드
# ==========================================
if 'step' not in st.session_state: st.session_state.step = 'HOME'
if 'selected_gauge' not in st.session_state: st.session_state.selected_gauge = None

try:
    df = pd.DataFrame(get_gauge_data())
    user_list = get_user_list()
    client = connect_to_sheet()
    sh = client.open(SHEET_FILE_NAME)
    worksheet_status = sh.worksheet("Status")
    worksheet_logs = sh.worksheet("Logs")
except Exception as e:
    st.error(f"데이터 연결 오류: {e}")
    st.stop()

# ==========================================
# 4. 화면 로직
# ==========================================

# --- [HOME] 대기 화면 ---
if st.session_state.step == 'HOME':
    # [수정] 관리 버튼을 별도의 위쪽 줄 우측 끝으로 이동
    col_space, col_admin = st.columns([9, 1])
    with col_admin:
        # 정사각형 버튼을 만들기 위한 보이지 않는 앵커 태그
        st.markdown('<div id="admin-btn-target"></div>', unsafe_allow_html=True)
        if st.button("⚙️\n관리"): 
            st.session_state.step = 'ADMIN'
            st.rerun()
            
    # [수정] 그 밑줄에 제목 표시
    st.markdown("<h1 style='margin-top:0px;'>📏 게이지 관리 키오스크</h1>", unsafe_allow_html=True)
    
    st.markdown('<div class="start-btn-box">', unsafe_allow_html=True)
    if st.button("🚀 대여 시작하기", type="primary", use_container_width=True):
        st.session_state.step = 'LIST'
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.divider()
    st.markdown("<h3>↩️ 반납할 게이지를 터치하세요</h3>", unsafe_allow_html=True)
    
    if not df.empty:
        borrowed_items = df[df['상태'] == '대여중']
        if not borrowed_items.empty:
            for _, row in borrowed_items.iterrows():
                try:
                    dt_obj = datetime.strptime(str(row['대여일시']), "%m/%d %H:%M")
                    dt_obj = dt_obj.replace(year=datetime.now().year)
                    formatted_date = dt_obj.strftime("%y.%m.%d %H:%M")
                except:
                    formatted_date = row['대여일시']

                btn_label = f"{row['게이지명']} | {row['대여자']}      <span class='date-text'>( 대여일시 {formatted_date} )</span>"
                
                st.markdown('<div class="rent-list-box">', unsafe_allow_html=True)
                if st.button(f"{row['게이지명']} | {row['대여자']}      ( 대여일시 {formatted_date} )", key=f"ret_key_{row['게이지명']}", use_container_width=True):
                    st.session_state.selected_gauge = str(row['게이지명']).strip()
                    st.session_state.step = 'ACTION'
                    st.cache_data.clear()
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("현재 대여중인 게이지가 없습니다.")

# --- [LIST] 게이지 선택 화면 ---
elif st.session_state.step == 'LIST':
    st.markdown("<h3>🔍 대여할 게이지 선택</h3>", unsafe_allow_html=True)
    
    # [수정] 대여가능 및 검수중인 게이지 모두 불러오기
    available_and_inspecting = df[df['상태'].isin(['대여가능', '검수중'])]
    
    if not available_and_inspecting.empty:
        display_options = []
        mapping_dict = {}
        
        for _, row in available_and_inspecting.iterrows():
            g_name = row['게이지명']
            if row['상태'] == '검수중':
                # 검수 중 포맷 (02.20 14:30)
                try:
                    dt_obj = datetime.strptime(str(row['대여일시']), "%m/%d %H:%M")
                    formatted_date = dt_obj.strftime("%m.%d %H:%M")
                except:
                    formatted_date = row['대여일시']
                # 요청하신 양식
                display_text = f"{g_name} [검수 중 (발주 일시 {formatted_date})]"
            else:
                display_text = g_name
                
            display_options.append(display_text)
            mapping_dict[display_text] = g_name # 표시된 글자를 실제 DB 이름과 매칭

        # 게이지 목록 선택창
        choice_display = st.selectbox("게이지 목록", display_options, label_visibility="collapsed")
        choice_actual = mapping_dict[choice_display] # 선택된 실제 게이지명 추출
        
        st.write("") 
        col1, col2 = st.columns(2)
        with col1:
            if st.button("선택 완료", type="primary", use_container_width=True):
                st.session_state.selected_gauge = str(choice_actual).strip()
                st.session_state.step = 'ACTION'
                st.rerun()
        with col2:
            if st.button("취소", use_container_width=True):
                st.session_state.step = 'HOME'
                st.rerun()
    else:
        st.warning("선택 가능한 게이지가 없습니다.")
        if st.button("처음으로 돌아가기", use_container_width=True):
            st.session_state.step = 'HOME'
            st.rerun()

    # 하단 검수 중인 게이지 목록 (회색 한줄 표시 유지)
    inspecting_items = df[df['상태'] == '검수중']
    if not inspecting_items.empty:
        st.divider()
        st.markdown("<h3>🚫 검수 진행 중 (대여 불가)</h3>", unsafe_allow_html=True)
        for _, row in inspecting_items.iterrows():
            try:
                dt_obj = datetime.strptime(str(row['대여일시']), "%m/%d %H:%M")
                formatted_date = dt_obj.strftime("%m.%d %H:%M")
            except:
                formatted_date = row['대여일시']
            
            st.markdown(f"""
            <div class="inspecting-card">
                {row['게이지명']} &nbsp;|&nbsp; 
                <span style='color:#ff4b4b; font-weight:800;'>검수 중</span> &nbsp;|&nbsp;
                <span style='color:#1a1a1a; font-weight:500;'>[검수 발주 일시: {formatted_date}]</span>
            </div>
            """, unsafe_allow_html=True)

# --- [ACTION] 사용자 선택 및 확정 화면 ---
elif st.session_state.step == 'ACTION':
    target_gauge = st.session_state.selected_gauge
    row_data = df[df['게이지명'].astype(str).str.strip() == target_gauge].iloc[0]
    
    st.title(f"🛠️ {target_gauge}")
    
    # [수정] 검수 중인 게이지를 선택하고 들어왔을 때의 예외 처리
    if row_data['상태'] == "검수중":
        st.error("🚫 이 게이지는 현재 검수 진행 중이므로 대여하실 수 없습니다.")
        if st.button("돌아가기", use_container_width=True):
            st.session_state.step = 'HOME'
            st.rerun()
            
    elif row_data['상태'] == "대여가능":
        st.markdown("<h3>👤 사용자 선택</h3>", unsafe_allow_html=True)
        
        options = user_list + ["직접입력"]
        user_name = st.selectbox("사용자 선택", options, label_visibility="collapsed")
        
        custom_user = ""
        if user_name == "직접입력":
            custom_user = st.text_input("대여자 입력", placeholder="이름 또는 업체명을 입력하세요", label_visibility="collapsed")
            st.write("")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("확인", type="primary", use_container_width=True):
                final_user = custom_user.strip() if user_name == "직접입력" else user_name
                
                if user_name == "직접입력" and not final_user:
                    st.error("⚠️ 대여자 이름을 입력해주세요!")
                else:
                    cell = worksheet_status.find(target_gauge)
                    worksheet_status.update_cell(cell.row, 2, "대여중")
                    worksheet_status.update_cell(cell.row, 3, final_user)
                    now_str = datetime.now().strftime("%m/%d %H:%M")
                    worksheet_status.update_cell(cell.row, 4, now_str)
                    worksheet_logs.append_row([now_str, target_gauge, final_user, "대여"])
                    st.cache_data.clear()
                    st.session_state.step = 'HOME'
                    st.rerun()
        with col2:
            if st.button("취소", use_container_width=True):
                st.session_state.step = 'HOME'
                st.rerun()
                
    else: 
        st.error(f"🔴 현재 {row_data['대여자']}님 사용 중")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("확인", type="primary", use_container_width=True):
                cell = worksheet_status.find(target_gauge)
                worksheet_status.update_cell(cell.row, 2, "대여가능")
                worksheet_status.update_cell(cell.row, 3, "")
                worksheet_status.update_cell(cell.row, 4, "")
                now_str = datetime.now().strftime("%m/%d %H:%M")
                worksheet_logs.append_row([now_str, target_gauge, row_data['대여자'], "반납"])
                st.cache_data.clear()
                st.session_state.step = 'HOME'
                st.rerun()
        with col2:
            if st.button("취소", use_container_width=True):
                st.session_state.step = 'HOME'
                st.rerun()

# --- [ADMIN] 관리(검수) 페이지 화면 ---
elif st.session_state.step == 'ADMIN':
    st.markdown("<h1 style='text-align:left; margin-top:0px;'>[ 게이지 관리 ]</h1>", unsafe_allow_html=True)
    
    with st.form("admin_form"):
        admin_data = []
        for _, row in df.iterrows():
            if row['상태'] == '대여중': info = f"{row['대여자']} ({row['대여일시']})"
            elif row['상태'] == '검수중': info = f"검수 진행 중 ({row['대여일시']})"
            else: info = "-"
                
            admin_data.append({
                "선택": False, 
                "게이지 이름": row['게이지명'], 
                "현재 상태 및 대여자(대여일시)": info 
            })
        
        df_admin = pd.DataFrame(admin_data)
        if not df_admin.empty:
            df_admin = df_admin[["게이지 이름", "현재 상태 및 대여자(대여일시)", "선택"]]
        
        edited_df = st.data_editor(
            df_admin,
            column_config={"선택": st.column_config.CheckboxColumn("선택", default=False)},
            disabled=["게이지 이름", "현재 상태 및 대여자(대여일시)"],
            hide_index=True,
            use_container_width=True
        )

        st.write("") 
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div class="square-btn btn-inspect">', unsafe_allow_html=True)
            btn_inspect = st.form_submit_button("검수\n발주", use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with col2:
            st.markdown('<div class="square-btn btn-complete">', unsafe_allow_html=True)
            btn_complete = st.form_submit_button("검수\n완료", use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

    st.divider()
    if st.button("홈으로 돌아가기", use_container_width=True):
        st.session_state.step = 'HOME'
        st.rerun()

    if btn_inspect or btn_complete:
        selected_gauges = edited_df[edited_df['선택'] == True]['게이지 이름'].tolist()
        
        if btn_inspect:
            if not selected_gauges:
                st.error("선택된 게이지가 없습니다.")
            else:
                now_str = datetime.now().strftime("%m/%d %H:%M")
                for g_name in selected_gauges:
                    cell = worksheet_status.find(g_name)
                    worksheet_status.update_cell(cell.row, 2, "검수중")
                    worksheet_status.update_cell(cell.row, 3, "관리자")
                    worksheet_status.update_cell(cell.row, 4, now_str)
                    worksheet_logs.append_row([now_str, g_name, "관리자", "검수발주"])
                st.success(f"{len(selected_gauges)}개 게이지 검수 발주 완료!")
                st.cache_data.clear()
                st.rerun()

        if btn_complete:
            if not selected_gauges:
                st.error("선택된 게이지가 없습니다.")
            else:
                now_str = datetime.now().strftime("%m/%d %H:%M")
                for g_name in selected_gauges:
                    cell = worksheet_status.find(g_name)
                    worksheet_status.update_cell(cell.row, 2, "대여가능")
                    worksheet_status.update_cell(cell.row, 3, "")
                    worksheet_status.update_cell(cell.row, 4, "")
                    worksheet_logs.append_row([now_str, g_name, "관리자", "검수완료"])
                st.success(f"{len(selected_gauges)}개 게이지 검수 완료! (대여 가능)")
                st.cache_data.clear()
                st.rerun()