import streamlit as st
import cv2
import numpy as np
import pandas as pd
import time
from datetime import datetime
from virtual_core import VirtualEvacuationSystem

# === 1. 페이지 설정 (반드시 맨 처음에 위치) ===
st.set_page_config(
    page_title="스마트 지하상가 관제 대시보드",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# === 2. 고급 스타일링 (CSS) ===
st.markdown("""
    <style>
    /* 전체 배경 및 폰트 설정 */
    .stApp {
        background-color: #0e1117;
    }
    
    /* 메트릭 박스 스타일 */
    div[data-testid="stMetric"] {
        background-color: #262730;
        border: 1px solid #464b5c;
        padding: 15px;
        border-radius: 10px;
        color: white;
    }
    
    /* 경고 문구 스타일 */
    .alert-box {
        padding: 20px;
        background-color: #ff4b4b;
        color: white;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        font-size: 1.5em;
        animation: blinker 1s linear infinite;
        margin-bottom: 20px;
    }
    
    @keyframes blinker {
        50% { opacity: 0; }
    }
    
    /* 데이터 테이블 스타일 */
    .dataframe {
        font-size: 0.8rem !important;
    }
    </style>
""", unsafe_allow_html=True)

# === 3. 시스템 초기화 (캐싱 & 해상도 보정) ===
@st.cache_resource
def get_system():
    try:
        # 배경 이미지 로드
        sys = VirtualEvacuationSystem("background.png")
        
        # [핵심 수정] 해상도 불일치 해결을 위한 리사이징 패치
        # 코드상 좌표(최대 약 900px)에 맞춰 배경 이미지를 적절한 크기(Width 1100px)로 조정합니다.
        # 이렇게 하면 고해상도 이미지를 넣어도 점들이 제자리에 찍힙니다.
        TARGET_WIDTH = 1100
        h, w = sys.original_map.shape[:2]
        
        if w > TARGET_WIDTH or w < 800: # 크기가 너무 크거나 작으면 조정
            scale = TARGET_WIDTH / w
            new_h = int(h * scale)
            
            # 1. 원본 맵 리사이징
            sys.original_map = cv2.resize(sys.original_map, (TARGET_WIDTH, new_h))
            sys.w, sys.h = TARGET_WIDTH, new_h
            
            # 2. 장애물 마스크도 동일하게 리사이징
            if hasattr(sys, 'static_obstacle_mask'):
                 sys.static_obstacle_mask = cv2.resize(sys.static_obstacle_mask, (TARGET_WIDTH, new_h))
            
            # 3. 그리드맵(경로 계산용)도 변경된 크기로 재설정
            # sys.grid_map 객체의 클래스(GridMap)를 가져와서 새로 생성
            GridMapClass = type(sys.grid_map)
            sys.grid_map = GridMapClass(TARGET_WIDTH, new_h, sys.grid_size)
            
        return sys
        
    except Exception as e:
        st.error(f"시스템 초기화 중 오류 발생: {e}")
        return None

system = get_system()

# === 4. HUD 그리기 함수 (시각적 개선 핵심) ===
def draw_hud(img, active_fires):
    """
    이미지를 고해상도로 리사이징하고 관제 시스템 느낌의 오버레이를 그립니다.
    """
    # 1. 고화질 리사이징 (2배 확대 + 큐빅 보간법으로 부드럽게)
    scale_factor = 2.0
    h, w = img.shape[:2]
    new_w, new_h = int(w * scale_factor), int(h * scale_factor)
    img_hq = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    
    # 2. 오버레이 레이어 생성
    overlay = img_hq.copy()
    
    # 3. HUD 정보 표시 (시간, 상태)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # REC 표시 (빨간점 + 텍스트)
    cv2.circle(overlay, (40, 40), 10, (0, 0, 255), -1)
    cv2.putText(overlay, f"REC | {now}", (60, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
    
    # 4. 화재 발생 시 경고 테두리 및 오버레이
    if active_fires:
        # 화면 전체에 붉은 틴트 효과 (비상 상황 느낌)
        red_overlay = np.zeros_like(overlay)
        red_overlay[:] = (0, 0, 50) # 붉은색
        overlay = cv2.addWeighted(overlay, 1.0, red_overlay, 0.3, 0)
        
        cv2.rectangle(overlay, (0, 0), (new_w-1, new_h-1), (0, 0, 255), 30)
        cv2.putText(overlay, "WARNING: FIRE DETECTED", (new_w//2 - 250, 100), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 4, cv2.LINE_AA)
    else:
        # 정상 상태 녹색 테두리
        cv2.rectangle(overlay, (0, 0), (new_w-1, new_h-1), (0, 255, 0), 15)
        cv2.putText(overlay, "SYSTEM NORMAL", (new_w//2 - 180, 100), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3, cv2.LINE_AA)

    # 5. 이미지 합성 (투명도 조절로 고급스럽게)
    final_img = cv2.addWeighted(overlay, 0.9, img_hq, 0.1, 0)
    return final_img

# === 5. 메인 로직 ===
if system is None:
    st.error("❌ 시스템 초기화 실패: 'background.png' 파일이 있는지 확인해주세요.")
    st.stop()

# --- 사이드바: 컨트롤 패널 ---
with st.sidebar:
    st.title("🎛️ 제어 패널")
    st.divider()
    
    st.subheader("🔥 화재 구역 시뮬레이션")
    
    # 화재 구역 정의
    fire_zones = {
        "A구역 (좌측 통로)": (180, 250),
        "B구역 (중앙 홀)": (480, 250),
        "C구역 (우측 통로)": (800, 300),
        "D구역 (상단 통로)": (480, 100)
    }
    
    active_fires = []
    
    # 깔끔한 토글 스위치 UI
    col_t1, col_t2 = st.columns(2)
    for i, (name, coords) in enumerate(fire_zones.items()):
        # 2열로 배치
        with (col_t1 if i % 2 == 0 else col_t2):
            if st.toggle(name, key=f"fire_{i}"):
                active_fires.append(coords)
    
    st.divider()
    
    # 시스템 로그 (세션 상태 사용)
    if 'logs' not in st.session_state:
        st.session_state.logs = []
        
    if active_fires and (len(st.session_state.logs) == 0 or "화재 발생" not in st.session_state.logs[-1]):
        st.session_state.logs.append(f"{datetime.now().strftime('%H:%M:%S')} - ⚠️ 화재 감지됨 ({len(active_fires)}구역)")
    elif not active_fires and len(st.session_state.logs) > 0 and "화재 발생" in st.session_state.logs[-1]:
         st.session_state.logs.append(f"{datetime.now().strftime('%H:%M:%S')} - ✅ 상황 종료 (정상화)")

    st.subheader("📝 시스템 로그")
    log_df = pd.DataFrame(st.session_state.logs[-5:], columns=["Event Log"]) # 최근 5개만
    st.dataframe(log_df, use_container_width=True, hide_index=True)


# --- 메인 대시보드 ---
st.title("🚨 스마트 지하상가 대피 유도 관제 시스템")

# 1. 상단 상태 지표 (Metrics)
m1, m2, m3, m4 = st.columns(4)
m1.metric("시스템 상태", "비상" if active_fires else "정상", delta_color="inverse" if active_fires else "normal")
m2.metric("활성 화재 구역", f"{len(active_fires)} 개소", delta=f"+{len(active_fires)}" if active_fires else "0")
m3.metric("연결된 IoT 장치", "5 대", "Online")
m4.metric("최적 경로 계산", "실시간", "Active")

st.divider()

# 2. 비상 경고 배너
if active_fires:
    st.markdown(f'<div class="alert-box">⚠️ 비상 상황: {len(active_fires)}개 구역 화재 감지! 대피 경로가 재설정됩니다.</div>', unsafe_allow_html=True)

# 3. 메인 맵 & 데이터 시각화
col_map, col_data = st.columns([2.5, 1])

with col_map:
    # 코어 로직 실행
    raw_img, directions = system.process(active_fires)
    
    # BGR -> RGB 및 HUD 적용 (고화질 변환)
    hud_img = draw_hud(raw_img, active_fires)
    final_img = cv2.cvtColor(hud_img, cv2.COLOR_BGR2RGB)
    
    st.image(final_img, caption="실시간 관제 모니터링 (Live Feed)", use_container_width=True)

with col_data:
    st.subheader("📡 IoT 장치 현황")
    st.caption("각 구역 LED 유도등 상태")
    
    for node, direction in directions.items():
        # 상태에 따른 색상 및 아이콘 지정
        bg_color = "#ff4b4b" if "BLOCKED" in direction else "#262730"
        border_color = "#ff4b4b" if "BLOCKED" in direction else "#464b5c"
        
        icon = "🛑"
        desc = "진입 금지"
        
        if "UP" in direction: 
            icon, desc = "⬆️", "직진/상향"
        elif "DOWN" in direction: 
            icon, desc = "⬇️", "후진/하향"
        elif "LEFT" in direction: 
            icon, desc = "⬅️", "좌회전"
        elif "RIGHT" in direction: 
            icon, desc = "➡️", "우회전"
        elif "STOP" in direction:
            icon, desc = "✅", "목적지 도착"
            
        st.markdown(f"""
        <div style="background-color: {bg_color}; border: 1px solid {border_color}; padding: 10px; border-radius: 5px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
            <span style="font-weight: bold; color: white;">{node.split('(')[0]}</span>
            <span style="background-color: rgba(255,255,255,0.1); padding: 2px 8px; border-radius: 4px; color: white;">{icon} {direction}</span>
        </div>
        """, unsafe_allow_html=True)
    
    if active_fires:
        st.error("경로 알고리즘이 우회로를 탐색 중입니다.")
    else:
        st.success("모든 경로가 최적화되었습니다.")
