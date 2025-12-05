import streamlit as st
import cv2
import numpy as np
import pandas as pd
import time
import requests  # API 요청을 위한 라이브러리 추가
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
        font-family: 'Pretendard', 'Malgun Gothic', sans-serif; /* 한글 폰트 우선 */
        text-shadow: 0 0 10px rgba(255, 255, 255, 0.2);
    }
    p, div, span, label {
        color: #cccccc; /* 기본 텍스트 밝은 회색 */
        font-family: 'Pretendard', 'Malgun Gothic', sans-serif;
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
        # 배경 파일이 없어도 CCTV 모드는 동작하도록 None 반환 처리
        return None

system = get_system()

# === 4. HUD 그리기 함수 ===
def draw_hud(img, is_emergency, mode="VIRTUAL"):
    """
    이미지를 고해상도로 리사이징하고 관제 시스템 느낌의 오버레이를 그립니다.
    is_emergency: 비상 상황(화재) 여부 boolean
    """
    # 1. 고화질 리사이징
    scale_factor = 2.0
    h, w = img.shape[:2]
    new_w, new_h = int(w * scale_factor), int(h * scale_factor)
    img_hq = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    
    # 2. 오버레이 레이어 생성
    overlay = img_hq.copy()
    
    # 3. HUD 정보 표시
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 상단 정보 바
    cv2.rectangle(overlay, (0, 0), (new_w, 80), (0, 0, 0), -1)
    
    # REC 표시
    rec_text = f"LIVE CAM | {now}" if mode == "LIVE" else f"DIGITAL TWIN | {now}"
    color_status = (0, 0, 255) if is_emergency else (0, 255, 0)
    cv2.circle(overlay, (40, 40), 8, color_status, -1)
    cv2.putText(overlay, rec_text, (60, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2, cv2.LINE_AA)
    
    # 4. 화재 경고
    if is_emergency:
        red_overlay = np.zeros_like(overlay)
        red_overlay[:] = (0, 0, 50) 
        overlay = cv2.addWeighted(overlay, 1.0, red_overlay, 0.2, 0)
        
        cv2.rectangle(overlay, (0, 0), (new_w, new_h), (0, 0, 255), 20)
        
        text_size = cv2.getTextSize("WARNING: FIRE DETECTED", cv2.FONT_HERSHEY_SIMPLEX, 1.5, 4)[0]
        cx, cy = new_w // 2, 150
        cv2.rectangle(overlay, (cx - text_size[0]//2 - 20, cy - 40), (cx + text_size[0]//2 + 20, cy + 20), (0, 0, 0), -1)
        
        cv2.putText(overlay, "WARNING: FIRE DETECTED", (cx - text_size[0]//2, cy), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 4, cv2.LINE_AA)
    else:
        cv2.rectangle(overlay, (0, 0), (new_w, new_h), (0, 255, 0), 4)
        
        text_size = cv2.getTextSize("SYSTEM NORMAL", cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)[0]
        cx = new_w - text_size[0] - 40
        cv2.putText(overlay, "SYSTEM NORMAL", (cx, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2, cv2.LINE_AA)

    final_img = cv2.addWeighted(overlay, 0.85, img_hq, 0.15, 0)
    return final_img

# --- 사이드바: 컨트롤 패널 ---
with st.sidebar:
    st.title("🎛️ 시스템 제어")
    st.caption("중앙 관제 인터페이스 (Central Command)")
    
    st.subheader("📡 모니터링 모드")
    monitoring_mode = st.selectbox(
        "데이터 소스 선택",
        ["가상 시뮬레이션", "실시간 CCTV (VPN)"],
        index=0
    )
    
    st.divider()
    
    st.subheader("🔥 이벤트 시뮬레이션")
    st.markdown("가상/훈련용 화재 이벤트 생성")
    
    # 화재 구역 정의
    fire_zones = {
        "A구역 (좌측 통로)": (250, 320),
        "B구역 (중앙 홀)": (550, 320),
        "C구역 (우측 통로)": (850, 320),
        "D구역 (상단 통로)": (550, 120)
    }
    
    active_fires = []
    
    # 가상 모드일 때만 토글 사용 (실시간 모드에선 API가 우선)
    for i, (name, coords) in enumerate(fire_zones.items()):
        if st.toggle(f"{name} 화재", key=f"fire_{i}"):
            active_fires.append(coords)
    
    st.divider()
    
    # 로그 시스템 (API 상태와 통합 필요)
    if 'logs' not in st.session_state:
        st.session_state.logs = []
    
    st.subheader("📝 이벤트 로그")
    log_df = pd.DataFrame(st.session_state.logs[-10:], columns=["시스템 메시지"]) 
    st.dataframe(log_df, use_container_width=True, hide_index=True)


# --- API 데이터 가져오기 (실시간 모드용) ---
api_status = {
    "fire_detected": False,
    "people_count": 0,
    "directions": {}
}
api_connected = False

if monitoring_mode == "실시간 CCTV (VPN)":
    API_URL = "http://192.168.219.44:5000/status"
    try:
        response = requests.get(API_URL, timeout=0.5)
        if response.status_code == 200:
            data = response.json()
            api_status["fire_detected"] = data.get("fire_detected", False)
            api_status["people_count"] = data.get("people_count", 0)
            
            # 방향 데이터 매핑 (0~4 -> LED 이름)
            raw_dirs = data.get("directions", {})
            mapping = {
                "0": "LED_1 (좌상)",
                "1": "LED_2 (좌하)",
                "2": "LED_3 (중앙)",
                "3": "LED_4 (우상)",
                "4": "LED_5 (중하)"
            }
            mapped_dirs = {}
            for k, v in raw_dirs.items():
                mapped_name = mapping.get(str(k), f"Node {k}")
                mapped_dirs[mapped_name] = v
            api_status["directions"] = mapped_dirs
            
            api_connected = True
    except Exception:
        pass

# --- 상태 결정 로직 ---
# 실시간 모드이면 API 데이터 우선, 아니면 가상 데이터 사용
if monitoring_mode == "실시간 CCTV (VPN)" and api_connected:
    is_emergency = api_status["fire_detected"]
    current_people = api_status["people_count"]
    display_directions = api_status["directions"]
else:
    is_emergency = len(active_fires) > 0
    current_people = 0 # 가상 모드 기본값
    # 방향 데이터는 아래 system.process()에서 계산
    display_directions = {} 


# --- 메인 대시보드 ---
st.title("🚨 스마트 대피 유도 관제 시스템")
st.markdown("### 실시간 지하상가 대피 유도 관제 현황판")

# 상단 지표
m1, m2, m3, m4 = st.columns(4)
m1.metric("시스템 상태", "비상 (CRITICAL)" if is_emergency else "정상 (NORMAL)", delta_color="inverse" if is_emergency else "normal")
m2.metric("활성 화재 구역", "API 감지됨" if (monitoring_mode=="실시간 CCTV (VPN)" and is_emergency) else f"{len(active_fires)} 개소", delta="Alert" if is_emergency else "Normal")
m3.metric("연결된 IoT 노드", "5 대", "Online" if api_connected or monitoring_mode=="가상 시뮬레이션" else "Offline")
m4.metric("재실 인원 (People)", f"{current_people} 명", "Real-time" if api_connected else "Simulated")

st.markdown("---")

if is_emergency:
    st.markdown(f'<div class="alert-box">⚠️ 비상 경보: 화재 감지됨! <br> 우회 경로 프로토콜 가동</div>', unsafe_allow_html=True)

# 레이아웃 컬럼 설정
col_map, col_data = st.columns([2.5, 1])

# === 데이터 선처리 (우측 패널용 - 가상 모드일 때만 계산 필요) ===
if monitoring_mode == "가상 시뮬레이션":
    if system:
        _, display_directions = system.process(active_fires)
    else:
        display_directions = {}

# === 우측 패널 렌더링 (IoT 상태) ===
with col_data:
    st.subheader("📡 IoT 노드 상태")
    st.markdown("실시간 유도등 방향 지시 상태")
    
    if not display_directions:
        st.info("데이터 수신 대기 중..." if monitoring_mode=="실시간 CCTV (VPN)" else "시뮬레이션 준비 중")
    
    # 방향 데이터 정렬 (이름순)
    sorted_items = sorted(display_directions.items())
    
    for node, direction in sorted_items:
        is_blocked = "BLOCKED" in direction
        status_class = "iot-status-blocked" if is_blocked else "iot-status-active"
        
        icon = "🛑"
        desc_kr = "진입 금지"
        desc_en = "BLOCKED"
        
        if "UP" in direction: 
            icon, desc_kr, desc_en = "⬆️ 직진", "상향 이동", "FORWARD"
        elif "DOWN" in direction: 
            icon, desc_kr, desc_en = "⬇️ 후진", "하향 이동", "BACKWARD"
        elif "LEFT" in direction: 
            icon, desc_kr, desc_en = "⬅️ 좌회전", "좌측 이동", "LEFT"
        elif "RIGHT" in direction: 
            icon, desc_kr, desc_en = "➡️ 우회전", "우측 이동", "RIGHT"
        elif "STOP" in direction:
            icon, desc_kr, desc_en = "✅ 도착", "목적지", "ARRIVED"
            
        st.markdown(f"""
        <div class="iot-card">
            <div>
                <div style="font-size: 0.85em; color: #888;">{node.split('(')[0]}</div>
                <div style="font-weight: bold; font-size: 1.1em; color: white;">{node.split('(')[1].replace(')','')}</div>
            </div>
            <div style="text-align: right;">
                <div class="{status_class}" style="font-size: 1.2em;">{icon} {desc_kr}</div>
                <div style="font-size: 0.7em; color: #666;">{desc_en}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    if is_emergency:
        st.markdown("""
        <div style="margin-top: 20px; padding: 10px; background-color: rgba(255, 0, 0, 0.2); border: 1px solid red; border-radius: 5px; color: #ffcccc; font-size: 0.8em; text-align: center;">
            ⚠️ 최적 우회 경로 계산 중... <br> IoT 노드와 동기화 중...
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="margin-top: 20px; padding: 10px; background-color: rgba(0, 255, 0, 0.1); border: 1px solid green; border-radius: 5px; color: #ccffcc; font-size: 0.8em; text-align: center;">
            ✅ 모든 시스템 정상. <br> 이벤트 대기 중.
        </div>
        """, unsafe_allow_html=True)

# === 좌측 패널 렌더링 (맵/CCTV) ===
with col_map:
    map_placeholder = st.empty()
    
    # [CASE 1] 가상 시뮬레이션 모드
    if monitoring_mode == "가상 시뮬레이션":
        if system:
            raw_img, _ = system.process(active_fires)
            hud_img = draw_hud(raw_img, is_emergency, mode="VIRTUAL")
            final_img = cv2.cvtColor(hud_img, cv2.COLOR_BGR2RGB)
            map_placeholder.image(final_img, caption="디지털 트윈 시뮬레이션 (Digital Twin)", use_container_width=True)
        else:
            map_placeholder.error("❌ 배경 맵 파일(background.png)이 없습니다.")

    # [CASE 2] 실시간 CCTV 모드
    elif monitoring_mode == "실시간 CCTV (VPN)":
        CAMERA_URL = "http://10.8.0.6:8080/?action=stream"
        cap = cv2.VideoCapture(CAMERA_URL)
        
        if not cap.isOpened():
            map_placeholder.error(f"❌ 카메라 연결 실패: {CAMERA_URL}")
            st.info("💡 팁: VPN 연결 확인 및 로컬 PC에서 실행 중인지 확인하세요.")
        else:
            while True:
                ret, frame = cap.read()
                if not ret:
                    map_placeholder.warning("신호 없음 (Signal Lost)")
                    break
                
                # API 상태에 따라 HUD 업데이트
                # (루프 안에서도 API 데이터를 갱신하고 싶다면 여기에 requests 로직을 넣어야 하지만, 
                # 성능상 여기서는 처음에 받아온 is_emergency 상태를 유지하거나
                # Streamlit의 rerun 주기에 맡깁니다.)
                hud_img = draw_hud(frame, is_emergency, mode="LIVE")
                final_img = cv2.cvtColor(hud_img, cv2.COLOR_BGR2RGB)
                
                map_placeholder.image(final_img, caption=f"실시간 영상 피드: {CAMERA_URL}", use_container_width=True)
            
            cap.release()
