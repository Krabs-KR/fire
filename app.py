import streamlit as st
import cv2
import numpy as np
import pandas as pd
import time
from datetime import datetime
from virtual_core import VirtualEvacuationSystem

# === 1. 페이지 설정 (반드시 맨 처음에 위치) ===
st.set_page_config(
    page_title="스마트 지하상가 관제 시스템",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# === 2. 심미적 디자인 개선 (Cyberpunk/Command Center Style CSS) ===
st.markdown("""
    <style>
    /* 1. 기본 배경 및 폰트 컬러 강제 설정 */
    .stApp {
        background-color: #050505 !important; /* 아주 깊은 검정 */
        color: #e0e0e0 !important;
    }
    
    /* 2. 헤더 텍스트 스타일링 */
    h1, h2, h3, h4, h5, h6 {
        color: #ffffff !important;
        font-family: 'Sans-serif';
        text-shadow: 0 0 10px rgba(255, 255, 255, 0.2);
    }
    p, div, span, label {
        color: #cccccc; /* 기본 텍스트 밝은 회색 */
    }

    /* 3. 메트릭 박스 (네온 글래스 효과) */
    div[data-testid="stMetric"] {
        background-color: rgba(30, 30, 40, 0.7);
        border: 1px solid rgba(100, 100, 100, 0.5);
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        backdrop-filter: blur(10px);
        transition: transform 0.2s;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        border-color: rgba(255, 255, 255, 0.8);
    }
    /* 메트릭 라벨 및 값 색상 강제 */
    div[data-testid="stMetricLabel"] > label {
        color: #a0a0a0 !important;
        font-size: 0.9rem !important;
    }
    div[data-testid="stMetricValue"] > div {
        color: #00ffcc !important; /* 네온 민트색 포인트 */
        font-weight: 700 !important;
        text-shadow: 0 0 8px rgba(0, 255, 204, 0.4);
    }

    /* 4. 경고 박스 스타일 */
    .alert-box {
        padding: 20px;
        background: linear-gradient(45deg, #8B0000, #FF0000);
        color: white !important;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        font-size: 1.5em;
        box-shadow: 0 0 20px rgba(255, 0, 0, 0.6);
        animation: pulse 1.5s infinite;
        margin-bottom: 25px;
        border: 1px solid #ff4444;
    }
    @keyframes pulse {
        0% { transform: scale(1); box-shadow: 0 0 20px rgba(255, 0, 0, 0.6); }
        50% { transform: scale(1.02); box-shadow: 0 0 30px rgba(255, 0, 0, 0.9); }
        100% { transform: scale(1); box-shadow: 0 0 20px rgba(255, 0, 0, 0.6); }
    }
    
    /* 5. 사이드바 스타일링 */
    section[data-testid="stSidebar"] {
        background-color: #111111 !important;
        border-right: 1px solid #333;
    }
    
    /* 6. 데이터프레임 스타일 */
    div[data-testid="stDataFrame"] {
        border: 1px solid #333;
        border-radius: 8px;
    }

    /* 7. IoT 상태 카드 스타일 */
    .iot-card {
        background-color: #1e1e24;
        border: 1px solid #333;
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 10px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        transition: all 0.3s ease;
    }
    .iot-card:hover {
        border-color: #555;
        background-color: #25252b;
    }
    .iot-status-blocked {
        color: #ff4b4b;
        font-weight: bold;
        text-shadow: 0 0 5px rgba(255, 75, 75, 0.5);
    }
    .iot-status-active {
        color: #00ffcc;
        font-weight: bold;
        text-shadow: 0 0 5px rgba(0, 255, 204, 0.5);
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
    
    # 상단 정보 바 (반투명 배경)
    cv2.rectangle(overlay, (0, 0), (new_w, 80), (0, 0, 0), -1)
    
    # REC 표시 (빨간점 + 텍스트)
    cv2.circle(overlay, (40, 40), 8, (0, 0, 255), -1)
    cv2.putText(overlay, f"LIVE REC | {now}", (60, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2, cv2.LINE_AA)
    
    # 4. 화재 발생 시 경고 테두리 및 오버레이
    if active_fires:
        # 화면 전체에 붉은 틴트 효과 (비상 상황 느낌)
        red_overlay = np.zeros_like(overlay)
        red_overlay[:] = (0, 0, 50) # 붉은색
        overlay = cv2.addWeighted(overlay, 1.0, red_overlay, 0.2, 0)
        
        # 경고 박스 및 텍스트
        cv2.rectangle(overlay, (0, 0), (new_w, new_h), (0, 0, 255), 20)
        
        # 중앙 경고 메시지 배경
        text_size = cv2.getTextSize("WARNING: FIRE DETECTED", cv2.FONT_HERSHEY_SIMPLEX, 1.5, 4)[0]
        cx, cy = new_w // 2, 150
        cv2.rectangle(overlay, (cx - text_size[0]//2 - 20, cy - 40), (cx + text_size[0]//2 + 20, cy + 20), (0, 0, 0), -1)
        
        cv2.putText(overlay, "WARNING: FIRE DETECTED", (cx - text_size[0]//2, cy), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 4, cv2.LINE_AA)
    else:
        # 정상 상태 녹색 테두리 (얇게)
        cv2.rectangle(overlay, (0, 0), (new_w, new_h), (0, 255, 0), 4)
        
        text_size = cv2.getTextSize("SYSTEM NORMAL", cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)[0]
        cx = new_w - text_size[0] - 40
        cv2.putText(overlay, "SYSTEM NORMAL", (cx, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2, cv2.LINE_AA)

    # 5. 이미지 합성 (투명도 조절로 고급스럽게)
    final_img = cv2.addWeighted(overlay, 0.85, img_hq, 0.15, 0)
    return final_img

# === 5. 메인 로직 ===
if system is None:
    st.error("❌ 시스템 초기화 실패: 'background.png' 파일이 있는지 확인해주세요.")
    st.stop()

# --- 사이드바: 컨트롤 패널 ---
with st.sidebar:
    st.title("🎛️ SYSTEM CONTROL")
    st.caption("Central Command Interface")
    st.divider()
    
    st.subheader("🔥 Simulation Control")
    st.markdown("구역별 가상 화재 시뮬레이션")
    
    # 화재 구역 정의 (이미지 해상도 1100px 기준 중앙 정렬 좌표)
    fire_zones = {
        "Zone A (좌측 통로)": (250, 320),
        "Zone B (중앙 홀)": (550, 320),
        "Zone C (우측 통로)": (850, 320),
        "Zone D (상단 통로)": (550, 120)
    }
    
    active_fires = []
    
    # 깔끔한 토글 스위치 UI
    for i, (name, coords) in enumerate(fire_zones.items()):
        if st.toggle(name, key=f"fire_{i}"):
            active_fires.append(coords)
    
    st.divider()
    
    # 시스템 로그
    if 'logs' not in st.session_state:
        st.session_state.logs = []
        
    if active_fires and (len(st.session_state.logs) == 0 or "화재 발생" not in st.session_state.logs[-1]):
        st.session_state.logs.append(f"{datetime.now().strftime('%H:%M:%S')} - ⚠️ EVENT: FIRE DETECTED ({len(active_fires)})")
    elif not active_fires and len(st.session_state.logs) > 0 and "화재 발생" in st.session_state.logs[-1]:
         st.session_state.logs.append(f"{datetime.now().strftime('%H:%M:%S')} - ✅ EVENT: SYSTEM CLEARED")

    st.subheader("📝 Event Logs")
    log_df = pd.DataFrame(st.session_state.logs[-10:], columns=["System Message"]) # 최근 10개
    st.dataframe(log_df, use_container_width=True, hide_index=True)


# --- 메인 대시보드 ---
st.title("🚨 SMART EVACUATION OPS")
st.markdown("### 실시간 지하상가 대피 유도 관제 현황판")

# 1. 상단 상태 지표 (Metrics)
m1, m2, m3, m4 = st.columns(4)
m1.metric("System Status", "CRITICAL" if active_fires else "NORMAL", delta_color="inverse" if active_fires else "normal")
m2.metric("Active Fire Zones", f"{len(active_fires)}", delta=f"+{len(active_fires)}" if active_fires else "0")
m3.metric("Connected IoT Nodes", "5 Units", "Stable")
m4.metric("Algorithm Latency", "12ms", "Optimal")

st.markdown("---")

# 2. 비상 경고 배너 (화재 시에만 등장)
if active_fires:
    st.markdown(f'<div class="alert-box">⚠️ EMERGENCY ALERT: {len(active_fires)} ZONES AFFECTED <br> REROUTING PROTOCOLS INITIATED</div>', unsafe_allow_html=True)

# 3. 메인 맵 & 데이터 시각화
col_map, col_data = st.columns([2.5, 1])

with col_map:
    # 코어 로직 실행
    raw_img, directions = system.process(active_fires)
    
    # BGR -> RGB 및 HUD 적용 (고화질 변환)
    hud_img = draw_hud(raw_img, active_fires)
    final_img = cv2.cvtColor(hud_img, cv2.COLOR_BGR2RGB)
    
    # 맵 이미지 표시 (테두리 추가)
    st.image(final_img, caption="Live CCTV Feed - Main Hall", use_container_width=True)

with col_data:
    st.subheader("📡 IoT Node Status")
    st.markdown("실시간 유도등 방향 지시 상태")
    
    for node, direction in directions.items():
        # 상태에 따른 아이콘 및 클래스 지정
        is_blocked = "BLOCKED" in direction
        status_class = "iot-status-blocked" if is_blocked else "iot-status-active"
        
        icon = "🛑"
        desc = "진입 금지"
        
        if "UP" in direction: 
            icon, desc = "⬆️ 직진", "FORWARD"
        elif "DOWN" in direction: 
            icon, desc = "⬇️ 후진", "BACKWARD"
        elif "LEFT" in direction: 
            icon, desc = "⬅️ 좌회전", "LEFT"
        elif "RIGHT" in direction: 
            icon, desc = "➡️ 우회전", "RIGHT"
        elif "STOP" in direction:
            icon, desc = "✅ 도착", "ARRIVED"
            
        # HTML/CSS로 커스텀 카드 렌더링
        st.markdown(f"""
        <div class="iot-card">
            <div>
                <div style="font-size: 0.85em; color: #888;">{node.split('(')[0]}</div>
                <div style="font-weight: bold; font-size: 1.1em; color: white;">{node.split('(')[1].replace(')','')}</div>
            </div>
            <div style="text-align: right;">
                <div class="{status_class}" style="font-size: 1.2em;">{icon} {desc.split()[0]}</div>
                <div style="font-size: 0.7em; color: #666;">{desc.split()[-1]}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    if active_fires:
        st.markdown("""
        <div style="margin-top: 20px; padding: 10px; background-color: rgba(255, 0, 0, 0.2); border: 1px solid red; border-radius: 5px; color: #ffcccc; font-size: 0.8em; text-align: center;">
            ⚠️ Calculating optimal detour paths... <br> Syncing with IoT nodes...
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="margin-top: 20px; padding: 10px; background-color: rgba(0, 255, 0, 0.1); border: 1px solid green; border-radius: 5px; color: #ccffcc; font-size: 0.8em; text-align: center;">
            ✅ All systems nominal. <br> Standby for events.
        </div>
        """, unsafe_allow_html=True)
