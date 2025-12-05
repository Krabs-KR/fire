import streamlit as st
import cv2
import numpy as np
from virtual_core import VirtualEvacuationSystem

# 페이지 설정
st.set_page_config(page_title="스마트 지하상가 대피 유도 시스템", layout="wide")

# CSS 커스텀
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        height: 50px;
        font-weight: bold;
    }
    .status-box {
        padding: 15px;
        border-radius: 10px;
        background-color: #f0f2f6;
        margin-bottom: 10px;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_system():
    # 이미지 파일 경로 확인 필수 (background.png)
    return VirtualEvacuationSystem("background.png")

try:
    system = get_system()
except Exception as e:
    st.error(f"시스템 초기화 오류: {e}")
    st.stop()

# === UI 레이아웃 ===
st.title("🚨 지하상가 스마트 대피 유도 관제 시스템")

col_main, col_control = st.columns([3, 1])

# === 사이드바/컨트롤 패널 (화재 시뮬레이션) ===
with col_control:
    st.header("🔥 화재 발생 시뮬레이션")
    st.write("아래 버튼을 클릭하여 가상 화재를 발생시키세요.")
    
    # 세션 스테이트로 화재 위치 관리
    if 'fires' not in st.session_state:
        st.session_state.fires = []

    # 화재 구역 정의 (예시 좌표)
    fire_zones = {
        "Zone A (좌측 통로)": (180, 250),
        "Zone B (중앙 홀)": (480, 250),
        "Zone C (우측 통로)": (800, 300),
        "Zone D (상단 통로)": (480, 100)
    }

    # 화재 토글 버튼 생성
    active_fires = []
    for name, coords in fire_zones.items():
        is_active = st.toggle(f"🔥 {name} 화재", value=False)
        if is_active:
            active_fires.append(coords)

    st.divider()
    st.subheader("📡 아두이노 전송 데이터")
    st.caption("각 도트 매트릭스에 전송될 방향 명령입니다.")
    
    # 결과 데이터를 담을 공간 확보
    data_placeholder = st.empty()

# === 메인 화면 (맵 시각화) ===
with col_main:
    # 로직 실행
    result_img, directions = system.process(active_fires)
    
    # OpenCV BGR -> RGB 변환
    result_img = cv2.cvtColor(result_img, cv2.COLOR_BGR2RGB)
    
    st.image(result_img, caption="실시간 대피 경로 모니터링", use_container_width=True)

# === 데이터 패널 업데이트 ===
with data_placeholder.container():
    for node, direction in directions.items():
        icon = "🛑"
        if "UP" in direction: icon = "⬆️"
        elif "DOWN" in direction: icon = "⬇️"
        elif "LEFT" in direction: icon = "⬅️"
        elif "RIGHT" in direction: icon = "➡️"
        
        st.markdown(f"""
        <div class="status-box">
            <b>{node}</b><br>
            <span style="font-size: 1.5em;">{icon} {direction}</span>
        </div>
        """, unsafe_allow_html=True)

# === Arduino 연동 참고용 ===
# 실제 구현 시에는 시리얼 통신이나 WiFi(MQTT/HTTP)로 directions 값을 전송하면 됩니다.
# Example: 
# import serial
# ser.write(f"{node_id}:{direction}\n".encode())
