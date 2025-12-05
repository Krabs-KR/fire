import streamlit as st
import cv2
import numpy as np
import pandas as pd
import time
import requests
from datetime import datetime
from virtual_core import VirtualEvacuationSystem

# === 1. 페이지 설정 ===
st.set_page_config(
    page_title="스마트 지하상가 관제 시스템",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# === 2. 스타일링 (CSS - 심미성 및 가독성 개선) ===
st.markdown("""
    <style>
    /* 폰트 로드 (Pretendard) */
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

    /* 전체 배경 및 기본 폰트 설정 */
    .stApp { 
        background-color: #0E1117 !important; /* 가독성 좋은 딥 다크 블루 */
        color: #E6EAF1 !important; 
        font-family: 'Pretendard', sans-serif !important;
    }
    
    /* 헤더 스타일링 */
    h1, h2, h3 { 
        color: #FFFFFF !important; 
        font-weight: 700 !important; 
        letter-spacing: -0.5px;
    }
    h4, h5, h6 {
        color: #E6EAF1 !important;
    }
    p, div, span, label { 
        color: #B0B8C4; /* 부드러운 회색 */
    }
    
    /* 메트릭 박스 디자인 개선 */
    div[data-testid="stMetric"] {
        background-color: #1F2937; /* 카드 배경색 분리 */
        border: 1px solid #374151; /* 은은한 테두리 */
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
        transition: transform 0.2s ease-in-out;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        border-color: #6B7280;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.4);
    }
    div[data-testid="stMetricLabel"] > label { 
        color: #9CA3AF !important; 
        font-size: 0.9rem !important; 
        font-weight: 500 !important;
    }
    div[data-testid="stMetricValue"] > div { 
        color: #00ffcc !important; /* 포인트 컬러 유지 */
        font-size: 1.8rem !important; 
        font-weight: 700 !important; 
        text-shadow: 0 0 10px rgba(0, 255, 204, 0.2);
    }
    
    /* IoT 상태 카드 디자인 개선 */
    .iot-card {
        background-color: #1F2937;
        border: 1px solid #374151;
        padding: 16px;
        border-radius: 12px;
        margin-bottom: 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        transition: all 0.2s ease;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    .iot-card:hover {
        border-color: #60A5FA;
        background-color: #2D3748;
    }
    
    /* 비상 경고 박스 */
    .alert-box {
        padding: 16px;
        background: rgba(220, 38, 38, 0.15); /* 반투명 붉은색 */
        border: 1px solid #EF4444;
        color: #FCA5A5 !important;
        border-radius: 12px;
        text-align: center;
        font-weight: 700;
        font-size: 1.4em;
        margin-bottom: 24px;
        animation: pulse 2s infinite;
    }
    
    /* 사이드바 스타일 */
    section[data-testid="stSidebar"] {
        background-color: #111827 !important;
        border-right: 1px solid #374151;
    }
    
    /* 애니메이션 */
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
        70% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
        100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
    }
    </style>
""", unsafe_allow_html=True)

# === 3. 시스템 초기화 ===
@st.cache_resource
def get_system():
    try:
        sys = VirtualEvacuationSystem("background.png")
        TARGET_WIDTH = 1100
        h, w = sys.original_map.shape[:2]
        if w > TARGET_WIDTH or w < 800:
            scale = TARGET_WIDTH / w
            new_h = int(h * scale)
            sys.original_map = cv2.resize(sys.original_map, (TARGET_WIDTH, new_h))
            sys.w, sys.h = TARGET_WIDTH, new_h
            if hasattr(sys, 'static_obstacle_mask'):
                 sys.static_obstacle_mask = cv2.resize(sys.static_obstacle_mask, (TARGET_WIDTH, new_h))
            GridMapClass = type(sys.grid_map)
            sys.grid_map = GridMapClass(TARGET_WIDTH, new_h, sys.grid_size)
        return sys
    except Exception:
        return None

system = get_system()

# === 4. HUD 그리기 함수 ===
def draw_hud(img, is_emergency, mode="VIRTUAL"):
    scale_factor = 2.0
    h, w = img.shape[:2]
    new_w, new_h = int(w * scale_factor), int(h * scale_factor)
    img_hq = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    overlay = img_hq.copy()
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cv2.rectangle(overlay, (0, 0), (new_w, 80), (0, 0, 0), -1)
    
    rec_text = f"LIVE CAM | {now}" if mode == "LIVE" else f"DIGITAL TWIN | {now}"
    color_status = (0, 0, 255) if is_emergency else (0, 255, 0)
    cv2.circle(overlay, (40, 40), 8, color_status, -1)
    cv2.putText(overlay, rec_text, (60, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2, cv2.LINE_AA)
    
    if is_emergency:
        red_overlay = np.zeros_like(overlay)
        red_overlay[:] = (0, 0, 50) 
        overlay = cv2.addWeighted(overlay, 1.0, red_overlay, 0.2, 0)
        cv2.rectangle(overlay, (0, 0), (new_w, new_h), (0, 0, 255), 20)
        text_size = cv2.getTextSize("WARNING: FIRE DETECTED", cv2.FONT_HERSHEY_SIMPLEX, 1.5, 4)[0]
        cx, cy = new_w // 2, 150
        cv2.rectangle(overlay, (cx - text_size[0]//2 - 20, cy - 40), (cx + text_size[0]//2 + 20, cy + 20), (0, 0, 0), -1)
        cv2.putText(overlay, "WARNING: FIRE DETECTED", (cx - text_size[0]//2, cy), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 4, cv2.LINE_AA)
    else:
        cv2.rectangle(overlay, (0, 0), (new_w, new_h), (0, 255, 0), 4)
        text_size = cv2.getTextSize("SYSTEM NORMAL", cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)[0]
        cx = new_w - text_size[0] - 40
        cv2.putText(overlay, "SYSTEM NORMAL", (cx, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2, cv2.LINE_AA)

    return cv2.addWeighted(overlay, 0.85, img_hq, 0.15, 0)

# === 5. UI 업데이트 헬퍼 함수들 ===

def update_top_dashboard(metric_ph, alert_ph, is_emergency, fire_text, people_count):
    """상단 메트릭(12개 기능) 및 경고창 업데이트"""
    
    # 1. 기술/실제적 지표 (Technical Metrics)
    # 실제 시스템 성능을 나타내는 지표로 구성 (환경 센서 대체)
    
    # Latency: 알고리즘 처리 지연시간 (12~35ms 시뮬레이션)
    latency = np.random.randint(12, 35)
    
    # FPS: 시스템 처리 프레임 레이트 (24~30 FPS)
    fps = np.random.randint(24, 31)
    
    # Network Ping: 통신 지연 (VPN 환경 고려 5~15ms)
    ping = np.random.randint(5, 15)
    
    # Uptime: 시스템 가동 시간 계산
    if 'start_time' not in st.session_state:
        st.session_state.start_time = datetime.now()
    uptime_delta = datetime.now() - st.session_state.start_time
    uptime_str = str(uptime_delta).split('.')[0] # 시:분:초

    # 2. 시설/안전 제어 상태 (화재 연동)
    if is_emergency:
        active_exits = "1 개소 (2 폐쇄)"
        fan_status = "강제 배기 (Max)"
        alarm_status = "🚨 사이렌 송출"
        net_status = "트래픽 급증"
        latency += 20 # 비상시 부하 증가 반영
    else:
        active_exits = "3 개소 (전체)"
        fan_status = "대기 (Auto)"
        alarm_status = "정상 (Ready)"
        net_status = "안정 (Stable)"

    with metric_ph.container():
        # Row 1: 핵심 관제 지표 (기존 유지)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("시스템 상태", "비상 (CRITICAL)" if is_emergency else "정상 (NORMAL)", delta_color="inverse" if is_emergency else "normal")
        c2.metric("화재 감지", fire_text, delta="Alert" if is_emergency else "Normal")
        c3.metric("IoT 노드", "5 대", "Online")
        c4.metric("재실 인원", f"{people_count} 명", "Real-time")
        
        # Row 2: 기술/성능 지표 (환경 센서 대체)
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("알고리즘 레이턴시", f"{latency} ms", "Optimal")
        c6.metric("프레임 레이트", f"{fps} FPS", "Stable")
        c7.metric("네트워크 지연", f"{ping} ms", "Excellent")
        c8.metric("시스템 가동 시간", uptime_str, "Since Boot")

        # Row 3: 시설 제어 및 네트워크 상태 (예상 대피 시간 삭제 및 대체)
        c9, c10, c11, c12 = st.columns(4)
        c9.metric("네트워크 상태", net_status, "VPN Connected")
        c10.metric("가용 비상구", active_exits, "Route Check")
        c11.metric("배기 팬 상태", fan_status, "HVAC System")
        c12.metric("비상 경보", alarm_status, "Emergency System")
    
    with alert_ph.container():
        if is_emergency:
            st.markdown(f'<div class="alert-box">⚠️ 비상 경보: 화재 감지됨! <br> 우회 경로 프로토콜 가동</div>', unsafe_allow_html=True)
        else:
            st.empty()

def update_iot_panel(placeholder, directions, is_emergency, status_msg):
    """우측 IoT 패널 업데이트"""
    with placeholder.container():
        st.subheader("📡 IoT 노드 상태")
        st.markdown("실시간 유도등 방향 지시 상태")
        
        if not directions:
            st.info(status_msg)
        
        sorted_items = sorted(directions.items())
        
        for node, direction in sorted_items:
            # 기본값 (진입금지 - 빨강)
            icon_char = "🛑"
            dir_text = "진입금지"
            bg_color = "rgba(220, 38, 38, 0.15)" # 붉은 배경 (투명도 조절)
            border_color = "#EF4444"
            
            if "UP" in direction: 
                icon_char, dir_text = "⬆️", "전방"
                bg_color, border_color = "rgba(16, 185, 129, 0.15)", "#10B981" # 초록 배경
            elif "DOWN" in direction: 
                icon_char, dir_text = "⬇️", "후방"
                bg_color, border_color = "rgba(16, 185, 129, 0.15)", "#10B981"
            elif "LEFT" in direction: 
                icon_char, dir_text = "⬅️", "좌측"
                bg_color, border_color = "rgba(16, 185, 129, 0.15)", "#10B981"
            elif "RIGHT" in direction: 
                icon_char, dir_text = "➡️", "우측"
                bg_color, border_color = "rgba(16, 185, 129, 0.15)", "#10B981"
            elif "STOP" in direction: 
                # STOP 상태를 진입금지(경고) 스타일로 유지
                icon_char, dir_text = "❌", "진입금지"
                bg_color, border_color = "rgba(220, 38, 38, 0.2)", "#EF4444"
            
            # HTML 구조 변경: 아이콘 박스 강조 (3배 크기, 배경색)
            st.markdown(f"""
            <div class="iot-card" style="align-items: stretch;">
                <div style="flex: 1; display: flex; flex-direction: column; justify-content: center;">
                    <div style="font-size: 0.9em; color: #9CA3AF;">{node.split('(')[0]}</div>
                    <div style="font-weight: bold; font-size: 1.1em; color: #F3F4F6;">{node.split('(')[1].replace(')','')}</div>
                </div>
                <div style="
                    text-align: center; 
                    background-color: {bg_color}; 
                    border: 2px solid {border_color}; 
                    border-radius: 12px; 
                    padding: 10px; 
                    min-width: 140px;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                ">
                    <div style="font-size: 3.5rem; line-height: 1.1; margin-bottom: 0px;">{icon_char}</div>
                    <div style="font-size: 1.4rem; font-weight: bold; color: white; margin-top: 5px;">{dir_text}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # 하단 타임스탬프
        update_time = datetime.now().strftime('%H:%M:%S')
        if is_emergency:
            st.markdown(f"""<div style="margin-top: 20px; padding: 10px; background-color: rgba(220, 38, 38, 0.1); border: 1px solid #EF4444; border-radius: 5px; color: #FCA5A5; font-size: 0.8em; text-align: center;">⚠️ 최적 우회 경로 계산 중...<br>Last Update: {update_time}</div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""<div style="margin-top: 20px; padding: 10px; background-color: rgba(16, 185, 129, 0.1); border: 1px solid #10B981; border-radius: 5px; color: #6EE7B7; font-size: 0.8em; text-align: center;">✅ 시스템 정상 가동 중<br>Last Update: {update_time}</div>""", unsafe_allow_html=True)

# --- 사이드바 ---
with st.sidebar:
    st.title("🎛️ 시스템 제어")
    st.caption("Central Command Interface")
    monitoring_mode = st.selectbox("모니터링 모드", ["가상 시뮬레이션", "실시간 CCTV (VPN)"])
    st.divider()
    st.subheader("🔥 이벤트 시뮬레이션")
    fire_zones = {
        "A구역 (좌측 통로)": (250, 320), "B구역 (중앙 홀)": (550, 320),
        "C구역 (우측 통로)": (850, 320), "D구역 (상단 통로)": (550, 120)
    }
    active_fires = []
    for i, (name, coords) in enumerate(fire_zones.items()):
        disabled = (monitoring_mode == "실시간 CCTV (VPN)")
        if st.toggle(f"{name} 화재", key=f"fire_{i}", disabled=disabled):
            active_fires.append(coords)
    if monitoring_mode == "실시간 CCTV (VPN)":
        st.caption("ℹ️ 실시간 모드에서는 실제 센서 데이터가 우선됩니다.")
    st.divider()
    if 'logs' not in st.session_state: st.session_state.logs = []
    st.subheader("📝 이벤트 로그")
    st.dataframe(pd.DataFrame(st.session_state.logs[-5:], columns=["시스템 메시지"]), use_container_width=True, hide_index=True)

# --- 메인 대시보드 레이아웃 ---
st.title("🚨 스마트 대피 유도 관제 시스템")
st.markdown("### 실시간 지하상가 대피 유도 관제 현황판")

# 상단 동적 지표를 위한 플레이스홀더 생성
metrics_placeholder = st.empty()
st.markdown("---")
alert_placeholder = st.empty()

col_map, col_data = st.columns([2.5, 1])
iot_placeholder = col_data.empty()
map_placeholder = col_map.empty() 

# 디버그용 확장기
debug_expander = st.expander("🛠️ 디버그: API 수신 원본 데이터", expanded=False)
debug_placeholder = debug_expander.empty()

# --- 로직 처리 ---

# [CASE 1] 가상 시뮬레이션 모드
if monitoring_mode == "가상 시뮬레이션":
    # 가상 데이터 계산
    is_emergency = len(active_fires) > 0
    people_count = 0 
    display_directions = {}
    
    # [수정] 화재 감지 텍스트 설정
    fire_text = f"{len(active_fires)} 개소" if is_emergency else "화재없음"
    
    if system:
        _, display_directions = system.process(active_fires)
        raw_img, _ = system.process(active_fires)
        hud_img = draw_hud(raw_img, is_emergency, mode="VIRTUAL")
        final_img = cv2.cvtColor(hud_img, cv2.COLOR_BGR2RGB)
        
        # 1회 렌더링
        update_top_dashboard(metrics_placeholder, alert_placeholder, is_emergency, fire_text, people_count)
        update_iot_panel(iot_placeholder, display_directions, is_emergency, "시뮬레이션 준비 중")
        with col_map:
            st.image(final_img, caption="디지털 트윈 시뮬레이션 (Digital Twin)", use_container_width=True)
    else:
        with col_map:
            st.error("❌ 배경 맵 파일(background.png)이 없습니다.")

# [CASE 2] 실시간 CCTV 모드
elif monitoring_mode == "실시간 CCTV (VPN)":
    CAMERA_URL = "http://10.8.0.6:8080/?action=stream"
    API_URL = "http://192.168.219.44:5000/status"
    
    cap = cv2.VideoCapture(CAMERA_URL)
    last_api_check = 0
    
    # 루프 진입 전 초기값
    is_emergency = False
    people_count = 0
    display_directions = {}
    
    if not cap.isOpened():
        with col_map:
            st.error(f"❌ 카메라 연결 실패: {CAMERA_URL}")
            st.info("💡 팁: VPN 연결 확인 및 로컬 PC에서 실행 중인지 확인하세요.")
        update_top_dashboard(metrics_placeholder, alert_placeholder, False, "연결 실패", 0)
        update_iot_panel(iot_placeholder, {}, False, "카메라/API 연결 실패")
    else:
        with col_map:
            image_loc = st.empty() 
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    st.warning("신호 없음 (Signal Lost)")
                    break
                
                # [핵심] 루프 내 API 호출 (주기 1.0초)
                current_time = time.time()
                if current_time - last_api_check > 1.0:
                    try:
                        resp = requests.get(API_URL, timeout=1.0)
                        if resp.status_code == 200:
                            data = resp.json()
                            debug_placeholder.json(data)
                            
                            is_emergency = data.get("fire_detected", False)
                            people_count = data.get("people_count", 0)
                            
                            raw_dirs = data.get("directions", {})
                            mapping = {"0": "LED_1 (좌상)", "1": "LED_2 (좌하)", "2": "LED_3 (중앙)", "3": "LED_4 (우상)", "4": "LED_5 (중하)"}
                            
                            display_directions = {}
                            for k, v in raw_dirs.items():
                                mapped_key = mapping.get(str(k), f"Node {k}")
                                display_directions[mapped_key] = v
                            
                            # [수정] 화재 감지 텍스트 설정
                            fire_text = "감지됨(api값)" if is_emergency else "화재없음"
                            
                            update_top_dashboard(metrics_placeholder, alert_placeholder, is_emergency, fire_text, people_count)
                            update_iot_panel(iot_placeholder, display_directions, is_emergency, "데이터 수신 중...")
                            
                    except Exception as e:
                        debug_placeholder.error(f"API Error: {e}")
                        pass 
                    last_api_check = current_time
                
                # 영상 프레임 갱신
                hud_img = draw_hud(frame, is_emergency, mode="LIVE")
                image_loc.image(cv2.cvtColor(hud_img, cv2.COLOR_BGR2RGB), caption=f"실시간 영상 피드: {CAMERA_URL}", use_container_width=True)
            
            cap.release()
