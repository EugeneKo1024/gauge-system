"""현장 게이지 관리 키오스크 — A형(즉시 저장, 최소 API 호출)."""
from __future__ import annotations

from datetime import datetime
from html import escape
import json
import os
import time
from zoneinfo import ZoneInfo

import gspread
import pandas as pd
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials

from gauge_core import build_transaction, parse_status_table, update_local_records

st.set_page_config(page_title="게이지 관리 | 현장 키오스크", page_icon="📏", layout="wide")

SHEET_FILE_NAME = "Gauges_System"
STATUS_TTL_SECONDS = 60
KST = ZoneInfo("Asia/Seoul")


# Streamlit Secrets에 저장된 기존 google_secret_json 값을 그대로 사용한다.
@st.cache_resource

def get_sheet_resources():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    if "google_secret_json" in st.secrets:
        secret = st.secrets["google_secret_json"]
        secret_dict = json.loads(secret) if isinstance(secret, str) else dict(secret)
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(secret_dict, scope)
    else:
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "secrets.json")
        credentials = ServiceAccountCredentials.from_json_keyfile_name(json_path, scope)
    client = gspread.authorize(credentials)
    spreadsheet = client.open(SHEET_FILE_NAME)
    return spreadsheet, spreadsheet.worksheet("Status"), spreadsheet.worksheet("Logs"), spreadsheet.worksheet("Users")


@st.cache_data(ttl=STATUS_TTL_SECONDS, show_spinner=False)
def fetch_status():
    _, sheet, _, _ = get_sheet_resources()
    return parse_status_table(sheet.get_all_values())


@st.cache_data(ttl=300, show_spinner=False)
def fetch_users():
    _, _, _, sheet = get_sheet_resources()
    raw = sheet.col_values(1)
    if raw and raw[0].strip() == "이름":
        raw = raw[1:]
    return list(dict.fromkeys(name.strip() for name in raw if name.strip()))


def load_status(*, force: bool = False) -> list[dict]:
    if force:
        fetch_status.clear()
    last_loaded = st.session_state.get("status_loaded_at", 0.0)
    if force or "status_rows" not in st.session_state or time.monotonic() - last_loaded >= STATUS_TTL_SECONDS:
        st.session_state.status_rows = fetch_status()
        st.session_state.status_loaded_at = time.monotonic()
    return st.session_state.status_rows


def now_text():
    # 기존 Google Sheets에 저장된 날짜 형식은 유지한다.
    return datetime.now(KST).strftime("%m/%d %H:%M")


def change_for(record: dict, state: str, user: str, action: str, dt: str) -> dict:
    return {
        "sheet_row": record["sheet_row"],
        "게이지명": record["게이지명"],
        "상태": state,
        "대여자": user if state != "대여가능" else "",
        "대여일시": dt if state != "대여가능" else "",
        "로그일시": dt,
        "로그사용자": user,
        "로그작업": action,
    }


def save_changes(changes: list[dict], success_message: str) -> bool:
    """한 번의 원격 쓰기 요청 성공 후에만 화면 캐시를 갱신한다.

    예외 시 자동 재시도하지 않는다: 타임아웃 후 중복 로그 추가를 방지하기 위해
    실제 Sheets 기록을 먼저 확인하도록 안내한다.
    """
    try:
        spreadsheet, status_sheet, logs_sheet, _ = get_sheet_resources()
        payload = build_transaction(changes, status_sheet.id, logs_sheet.id)
        spreadsheet.batch_update(payload)  # Status + Logs를 한 API 쓰기로 전송
    except Exception as exc:
        st.error("저장 완료 여부를 확인할 수 없습니다. Google Sheets의 Status·Logs 기록을 먼저 확인한 후 다시 시도하세요.")
        st.caption(f"오류 정보: {exc}")
        return False
    st.session_state.status_rows = update_local_records(st.session_state.status_rows, changes)
    st.session_state.flash = success_message
    return True


def goto(step: str, name: str | None = None):
    st.session_state.step = step
    if name is not None:
        st.session_state.selected_gauge = name
    st.rerun()


def row_for_name(rows: list[dict], name: str):
    return next((row for row in rows if row["게이지명"] == name), None)


def readable_date(value: str) -> str:
    try:
        return datetime.strptime(str(value), "%m/%d %H:%M").strftime("%m.%d %H:%M")
    except (ValueError, TypeError):
        return str(value).strip() or "기록 없음"


def banner(eyebrow: str, heading: str, description: str):
    st.markdown(
        f'<div class="page-banner"><p class="eyebrow">{escape(eyebrow)}</p>'
        f'<h1>{escape(heading)}</h1><p class="banner-description">{escape(description)}</p></div>',
        unsafe_allow_html=True,
    )


def status_pill(state: str) -> str:
    css = {"대여가능": "available", "대여중": "borrowed", "검수중": "inspection"}.get(state, "neutral")
    return f'<span class="status-pill {css}">{escape(state)}</span>'


# CSS: 갤럭시탭 터치 영역 / 반응형 대시보드 / 밝고 선명한 현장 UI
st.markdown(
    """
<style>
  :root { --navy:#10243B;--ink:#172D45;--muted:#667B8F;--line:#E1E8F1;--blue:#156AE8; }
  .stApp {background: radial-gradient(circle at 95% 3%, #DBEAFE 0, transparent 31%), #F4F7FB; color:var(--ink);}
  [data-testid="stHeader"] {background:transparent;}
  #MainMenu,footer {visibility:hidden;}
  .block-container {max-width:1240px;padding:1.4rem 1.7rem 4rem;}
  .brand-bar {display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:18px;}
  .brand-id {display:flex;align-items:center;gap:11px;font-size:16px;font-weight:850;color:var(--navy);}
  .brand-icon {width:39px;height:39px;border-radius:12px;background:var(--navy);color:#fff;display:grid;place-items:center;font-size:22px;}
  .brand-meta {font-size:13px;color:var(--muted);font-weight:600;}
  .page-banner {background:linear-gradient(112deg,#10243B 0%,#184D83 60%,#287AB9 100%);padding:29px 34px 28px;border-radius:23px;color:#fff;margin-bottom:20px;box-shadow:0 15px 38px rgba(10,43,82,.13);}
  .eyebrow {color:#9EDAF8!important;font-size:13px!important;letter-spacing:2px;font-weight:800;margin:0 0 7px!important;}
  .page-banner h1 {font-size:clamp(28px,4vw,43px)!important;font-weight:860!important;line-height:1.24!important;color:white!important;margin:0!important;}
  .banner-description {font-size:16px!important;color:#E2ECF7!important;margin:10px 0 0!important;}
  .section-title {font-size:21px;font-weight:850;color:var(--navy);margin:24px 0 13px;}
  .kpi-grid {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:4px 0 26px;}
  .kpi {background:#fff;border:1px solid var(--line);border-radius:18px;padding:17px 22px;box-shadow:0 6px 22px rgba(17,44,76,.04);}
  .kpi-label {font-size:15px;color:var(--muted);font-weight:750;margin:0 0 5px;}
  .kpi-number {font-size:40px;font-weight:900;color:var(--navy);line-height:1.1;}
  .kpi-number.green {color:#079669}.kpi-number.orange {color:#C57714}
  .detail-card {background:#fff;border:1px solid var(--line);border-radius:17px;padding:18px 21px;margin:8px 0;}
  .detail-top {display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;}
  .detail-name {font-size:21px;font-weight:850;color:var(--navy);}
  .detail-sub {font-size:14px;color:var(--muted);margin-top:7px;}
  .status-pill {display:inline-block;padding:6px 12px;border-radius:100px;font-size:13px;font-weight:850;white-space:nowrap;}
  .status-pill.available {background:#E2F7EF;color:#07815A;}
  .status-pill.borrowed {background:#FFF0E5;color:#AE6210;}
  .status-pill.inspection {background:#EAEFF5;color:#617184;}
  .status-pill.neutral {background:#EEF3FB;color:#43617C;}
  div.stButton>button, div.stFormSubmitButton>button {width:100%;min-height:70px;border:1px solid #CBD9EA;border-radius:15px!important;font-size:20px!important;font-weight:800!important;box-shadow:0 3px 8px rgba(23,51,83,.04);transition:filter .12s,transform .12s;}
  div.stButton>button:hover,div.stFormSubmitButton>button:hover {transform:translateY(-1px);filter:brightness(.98);}
  div.stButton>button[kind="primary"],div.stFormSubmitButton>button[kind="primary"] {background:var(--blue);border-color:var(--blue);color:white;}
  div.stButton>button[kind="secondary"],div.stFormSubmitButton>button[kind="secondary"] {background:#fff;color:var(--ink);}
  div[data-testid="stSelectbox"] [data-baseweb="select"]>div,div[data-testid="stTextInput"] [data-baseweb="input"]>div {min-height:66px;border-radius:14px;background:#fff;}
  div[data-testid="stSelectbox"] span,div[data-testid="stTextInput"] input {font-size:19px!important;}
  div[data-testid="stDataFrame"] {border:1px solid var(--line);border-radius:15px;overflow:hidden;}
  label,p {color:var(--ink);}
  [data-testid="stAlert"] {border-radius:14px;}
  @media(max-width:760px){.block-container{padding:.9rem .75rem 3rem}.page-banner{padding:22px 19px;border-radius:18px}.kpi-grid{gap:8px}.kpi{padding:12px}.kpi-number{font-size:30px}.kpi-label{font-size:12px}.brand-meta{display:none}div.stButton>button,div.stFormSubmitButton>button{min-height:64px;font-size:17px!important}.detail-name{font-size:18px}}
</style>
""",
    unsafe_allow_html=True,
)

if "step" not in st.session_state:
    st.session_state.step = "HOME"
if "selected_gauge" not in st.session_state:
    st.session_state.selected_gauge = ""

try:
    rows = load_status()
except Exception as exc:
    st.error(f"Google Sheets 연결 또는 데이터 구조 확인이 필요합니다: {exc}")
    st.info("Status 시트 첫 행의 A~D열은 게이지명 / 상태 / 대여자 / 대여일시 순서여야 합니다.")
    st.stop()

st.markdown(
    '<div class="brand-bar"><div class="brand-id"><div class="brand-icon">▥</div>'
    '<div>GAUGE CONTROL <span class="brand-meta">/ 현장 자산관리 키오스크</span></div></div>'
    '<span class="brand-meta">● GOOGLE SHEETS 연결</span></div>',
    unsafe_allow_html=True,
)

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

state = st.session_state.step
count_all = len(rows)
count_available = sum(row["상태"] == "대여가능" for row in rows)
count_borrowed = sum(row["상태"] == "대여중" for row in rows)
count_inspection = sum(row["상태"] == "검수중" for row in rows)

if state == "HOME":
    banner("GAUGE STATUS OVERVIEW", "게이지 관리 대시보드", "게이지 불출과 반납을 간편하고 빠르게 처리하세요.")
    st.markdown(
        '<div class="kpi-grid">'
        f'<div class="kpi"><div class="kpi-label">전체 게이지</div><div class="kpi-number">{count_all}</div></div>'
        f'<div class="kpi"><div class="kpi-label">대여 가능</div><div class="kpi-number green">{count_available}</div></div>'
        f'<div class="kpi"><div class="kpi-label">대여중 · 검수중</div><div class="kpi-number orange">{count_borrowed + count_inspection}</div></div>'
        '</div>',
        unsafe_allow_html=True,
    )
    c_start, c_admin, c_refresh = st.columns([2.3, 1.1, 1.1], gap="small")
    with c_start:
        if st.button("＋ 게이지 대여하기", type="primary", use_container_width=True):
            goto("LIST")
    with c_admin:
        if st.button("⚙ 관리 / 검수", use_container_width=True):
            goto("ADMIN")
    with c_refresh:
        if st.button("↻ 현황 새로고침", use_container_width=True):
            try:
                rows = load_status(force=True)
                st.rerun()
            except Exception as exc:
                st.error(f"새로고침 실패: {exc}")
    st.markdown('<div class="section-title">현재 대여중인 게이지 · 터치하여 반납</div>', unsafe_allow_html=True)
    borrowed = [row for row in rows if row["상태"] == "대여중"]
    if not borrowed:
        st.info("현재 대여중인 게이지가 없습니다.")
    for record in borrowed:
        name = record["게이지명"]
        st.markdown(
            '<div class="detail-card"><div class="detail-top">'
            f'<span class="detail-name">{escape(name)}</span>{status_pill("대여중")}</div>'
            f'<div class="detail-sub">대여자: {escape(record["대여자"])} · 대여일시: {escape(readable_date(record["대여일시"]))}</div></div>',
            unsafe_allow_html=True,
        )
        if st.button(f"↩  {name} 반납하기", key=f"return_{record['sheet_row']}", use_container_width=True):
            goto("ACTION", name)

elif state == "LIST":
    banner("STEP 01 / SELECT GAUGE", "대여할 게이지 선택", "대여 가능한 게이지를 선택하세요. 검수중인 게이지는 대여할 수 없습니다.")
    available = [row for row in rows if row["상태"] == "대여가능"]
    if available:
        options = [row["게이지명"] for row in available]
        selected = st.selectbox("게이지 목록", options, key="gauge_choice")
        c_next, c_back = st.columns(2)
        with c_next:
            if st.button("다음 · 대여자 선택 →", type="primary", use_container_width=True):
                goto("ACTION", selected)
        with c_back:
            if st.button("← 취소", use_container_width=True):
                goto("HOME")
    else:
        st.info("현재 대여 가능한 게이지가 없습니다.")
        if st.button("← 홈으로 돌아가기"):
            goto("HOME")
    inspecting = [row for row in rows if row["상태"] == "검수중"]
    if inspecting:
        st.markdown('<div class="section-title">검수 진행 중 · 대여 불가</div>', unsafe_allow_html=True)
        for record in inspecting:
            st.markdown(
                '<div class="detail-card"><div class="detail-top">'
                f'<span class="detail-name">{escape(record["게이지명"])}</span>{status_pill("검수중")}'
                '</div><div class="detail-sub">'
                f'검수 발주일시: {escape(readable_date(record["대여일시"]))}</div></div>',
                unsafe_allow_html=True,
            )

elif state == "ACTION":
    name = st.session_state.selected_gauge
    record = row_for_name(rows, name)
    if record is None:
        st.warning("선택한 게이지가 목록에서 확인되지 않습니다. 현황을 새로고침하세요.")
        if st.button("← 홈으로"):
            goto("HOME")
        st.stop()
    banner("STEP 02 / CONFIRM ACTION", name, "게이지의 현재 상태를 확인하고 작업을 완료하세요.")
    st.markdown(
        '<div class="detail-card"><div class="detail-top">'
        f'<span class="detail-name">{escape(name)}</span>{status_pill(record["상태"])}</div>'
        f'<div class="detail-sub">현재 사용자: {escape(record["대여자"]) or "—"} '
        f'· 일시: {escape(readable_date(record["대여일시"]))}</div></div>',
        unsafe_allow_html=True,
    )
    if record["상태"] == "검수중":
        st.warning("검수 진행 중인 게이지입니다. 관리 화면에서 검수 완료 후 대여할 수 있습니다.")
        if st.button("← 홈으로"):
            goto("HOME")
    elif record["상태"] == "대여가능":
        try:
            users = fetch_users()
        except Exception as exc:
            st.error(f"Users 시트의 사용자 명단 조회 실패: {exc}")
            st.stop()
        st.markdown('<div class="section-title">대여자 선택</div>', unsafe_allow_html=True)
        # 사용자 선택은 폼 밖에 둔다: "직접입력" 선택 즉시 이름 입력란이 나타난다.
        chosen_user = st.selectbox("사용자", users + ["직접입력"], key="borrow_user")
        with st.form("borrow_form"):
            custom_user = st.text_input("직접입력 이름 / 업체명", key="borrow_custom", placeholder="이름 또는 업체명을 입력하세요") if chosen_user == "직접입력" else ""
            left, right = st.columns(2)
            with left:
                submit = st.form_submit_button("✓ 대여 확정", type="primary", use_container_width=True)
            with right:
                cancel = st.form_submit_button("← 취소", use_container_width=True)
        if cancel:
            goto("HOME")
        if submit:
            borrower = custom_user.strip() if chosen_user == "직접입력" else chosen_user.strip()
            if not borrower:
                st.warning("대여자 이름을 입력하세요.")
            else:
                dt = now_text()
                if save_changes([change_for(record, "대여중", borrower, "대여", dt)], f"{name} · {borrower}님 대여 완료"):
                    goto("HOME")
    elif record["상태"] == "대여중":
        st.markdown('<div class="section-title">게이지 반납 확인</div>', unsafe_allow_html=True)
        st.info(f"현재 대여자: {record['대여자']} · 반납을 확정하면 대여 가능 상태가 됩니다.")
        left, right = st.columns(2)
        with left:
            if st.button("✓ 반납 확정", type="primary", use_container_width=True):
                dt = now_text()
                if save_changes([change_for(record, "대여가능", record["대여자"], "반납", dt)], f"{name} 반납 완료"):
                    goto("HOME")
        with right:
            if st.button("← 취소", use_container_width=True):
                goto("HOME")
    else:
        st.error(f"예상하지 못한 게이지 상태입니다: {record['상태']}")
        if st.button("← 홈으로"):
            goto("HOME")

elif state == "ADMIN":
    banner("MAINTENANCE / MANAGEMENT", "게이지 관리 및 검수", "목록에서 여러 게이지를 선택한 뒤 검수 발주 또는 완료를 처리하세요.")
    st.markdown(
        f'<div class="detail-card"><div class="detail-sub">대여 가능 {count_available}개　·　대여중 {count_borrowed}개　·　검수중 {count_inspection}개</div></div>',
        unsafe_allow_html=True,
    )
    display_rows = []
    for record in rows:
        details = record["대여자"] + " · " + readable_date(record["대여일시"]) if record["대여자"] else readable_date(record["대여일시"]) if record["대여일시"] else "—"
        display_rows.append(
            {"선택": False, "게이지명": record["게이지명"], "상태": record["상태"], "상세": details, "시트행": record["sheet_row"]}
        )
    admin_df = pd.DataFrame(display_rows, columns=["선택", "게이지명", "상태", "상세", "시트행"])
    with st.form("inspection_form"):
        edited_df = st.data_editor(
            admin_df,
            hide_index=True,
            use_container_width=True,
            disabled=["게이지명", "상태", "상세", "시트행"],
            column_order=["선택", "게이지명", "상태", "상세"],
            column_config={"선택": st.column_config.CheckboxColumn("선택", default=False, width="small")},
            key="inspect_editor",
        )
        left, right = st.columns(2)
        with left:
            inspect = st.form_submit_button("↗ 검수 발주", type="primary", use_container_width=True)
        with right:
            complete = st.form_submit_button("✓ 검수 완료", use_container_width=True)
    if inspect or complete:
        chosen_numbers = edited_df.loc[edited_df["선택"], "시트행"].tolist()
        chosen_records = [record for record in rows if record["sheet_row"] in chosen_numbers]
        if not chosen_records:
            st.warning("처리할 게이지를 하나 이상 선택하세요.")
        else:
            dt = now_text()
            changes = []
            for record in chosen_records:
                if inspect:
                    changes.append(change_for(record, "검수중", "관리자", "검수발주", dt))
                else:
                    changes.append(change_for(record, "대여가능", "관리자", "검수완료", dt))
            msg = f"{len(changes)}개 게이지 검수 {'발주' if inspect else '완료'} 처리 완료"
            if save_changes(changes, msg):
                goto("ADMIN")
    if st.button("← 대시보드로 돌아가기", use_container_width=True):
        goto("HOME")

else:
    goto("HOME")

st.caption("GAUGE CONTROL  ·  Google Sheets 즉시 저장  ·  현황 최대 60초 캐시  ·  상태 새로고침은 대시보드에서")
