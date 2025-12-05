import cv2
import numpy as np

# 분리된 모듈들 import
from camera import Camera
from detector import Detector
from map import GridMap
from navigator import Navigator
from server import EvacuationServer

# === 설정 ===
MAP_WIDTH = 640
MAP_HEIGHT = 480
GRID_SIZE = 20

# 1개의 도트만 테스트한다고 가정 (혹은 여러 개)
FIXED_DOT_POSITIONS = [
   (69, 397),
   (321, 270),
   (314, 81),
   (589, 204),
   (599, 398)
]
FIXED_EXIT_POSITIONS = [
    (70, 80),
    (347, 400),
    (608, 50)
]

def main():
    # 1. 모듈 초기화
    try:
        # STREAM_URL = "http://10.8.0.2:8080/?action=stream"
        STREAM_URL = 1  # 테스트용 로컬 카메라
        print(f"Connecting to {STREAM_URL}...")
        cam = Camera(STREAM_URL)
    except Exception as e:
        print(f"Camera Error: {e}")
        return

    detector = Detector()
    grid_map = GridMap(MAP_WIDTH, MAP_HEIGHT, GRID_SIZE)
    navigator = Navigator()      # 방향 계산기
    server = EvacuationServer()  # 웹 서버
    
    # 2. 서버 시작 (백그라운드)
    server.start()

    # [핵심 변수] 벽 고정용
    wall_locked = False
    locked_wall_mask = None

    print("=== System Started ===")
    print("1. 'c' 키: 벽 고정/해제 (Lock)")
    print("2. 'q' 키: 종료")
    
    while True:
        ret, frame = cam.get_frame()
        if not ret: break
        
        # 화면 준비
        frame = cv2.resize(frame, (MAP_WIDTH, MAP_HEIGHT))
        analysis_map = frame.copy()

        # [A] 맵 & 벽 업데이트 (시각화 복구됨)
        grid_map.reset()
        current_wall_mask = None
        
        if wall_locked and locked_wall_mask is not None:
            # [고정 모드] 저장해둔 벽 마스크 사용
            current_wall_mask = locked_wall_mask
            
            # [복구됨] 고정된 벽을 빨간색으로 표시
            analysis_map[locked_wall_mask > 0] = [0, 0, 255]
            
            cv2.putText(analysis_map, "[WALL LOCKED]", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        else:
            # [탐색 모드] 실시간 벽 감지
            current_wall_mask = detector.detect_walls_in_map(analysis_map)
            
            # [복구됨] 감지된 벽을 초록색으로 표시
            if current_wall_mask is not None:
                analysis_map[current_wall_mask > 0] = [0, 255, 0]

            cv2.putText(analysis_map, "Searching Walls... Press 'c'", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
        # 그리드맵에 장애물 업데이트
        if current_wall_mask is not None:
            grid_map.update_obstacles_from_mask(current_wall_mask)

        # [B] 불 감지
        fire_boxes, _ = detector.detect_fire(analysis_map)
        is_fire = (len(fire_boxes) > 0)
        
        for (fx, fy, fw, fh) in fire_boxes:
            grid_map.set_obstacle_rect(fx-20, fy-20, fw+40, fh+40)
            cv2.rectangle(analysis_map, (fx, fy), (fx+fw, fy+fh), (0, 0, 255), 2)
            cv2.putText(analysis_map, "FIRE", (fx, fy-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 2)

        # [C] 탈출구 등록
        for ex, ey in FIXED_EXIT_POSITIONS:
            grid_map.add_exit(ex, ey, 20, 20)
            cv2.circle(analysis_map, (ex, ey), 8, (255, 255, 255), -1)
            cv2.putText(analysis_map, "EXIT", (ex-15, ey-15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,0), 1)

        # [D] 도트 경로 및 방향 계산 (Navigator 위임)
        current_directions = {}
        
        for i, (dx, dy) in enumerate(FIXED_DOT_POSITIONS):
            if not (0 <= dx < MAP_WIDTH and 0 <= dy < MAP_HEIGHT): continue

            # 1. 도트 좌표 표시 (요청사항 반영)
            cv2.putText(analysis_map, f"({dx},{dy})", (dx+10, dy), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

            path = grid_map.get_shortest_path(dx, dy)
            direction = "STOP"

            if len(path) > 1:
                # [수정 1] 화살표와 텍스트의 기준점을 통일
                # path[1]은 너무 가까워서 방향이 불안정할 수 있으므로
                # 5칸 앞(idx) 혹은 경로의 끝을 기준으로 방향을 계산합니다.
                idx = min(5, len(path)-1)
                target_pos = path[idx] # 화살표가 가리키는 지점
                
                # Navigator에게 '현재위치'와 '목표지점(5칸앞)'을 줘서 큰 흐름의 방향을 얻음
                direction = navigator.get_direction((dx, dy), target_pos)
                
                # 경로 그리기
                cv2.polylines(analysis_map, [np.array(path)], False, (255, 0, 0), 2)
                
                # 화살표 그리기 (목표 지점 target_pos 사용)
                cv2.arrowedLine(analysis_map, (dx, dy), target_pos, (0, 255, 255), 2)
                
                # 방향 텍스트 (위치 약간 조정)
                cv2.putText(analysis_map, direction, (dx, dy-20), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2) # 폰트 크기 살짝 키움
            else:
                 cv2.putText(analysis_map, "X", (dx, dy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 1)

            current_directions[i] = direction
            cv2.circle(analysis_map, (dx, dy), 5, (0, 255, 255), -1)

        # [E] 서버에 데이터 업데이트
        server.update_data(is_fire, current_directions)

        # 화면 출력
        cv2.imshow("Smart Evacuation System", analysis_map)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('c'):
            # 벽 고정/해제 토글 로직
            if not wall_locked:
                wall_locked = True
                locked_wall_mask = current_wall_mask.copy() if current_wall_mask is not None else None
                print(">>> 벽 고정 완료! (LOCKED)")
            else:
                wall_locked = False
                locked_wall_mask = None
                print(">>> 벽 고정 해제. (UNLOCKED)")

    cam.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()