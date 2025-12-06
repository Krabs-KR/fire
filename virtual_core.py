import cv2
import numpy as np
# 파일들이 같은 경로에 있다고 가정 (src 폴더 구조라면 from src.map import ... 로 수정 필요)
try:
    from map import GridMap
    from navigator import Navigator
except ImportError:
    from src.map import GridMap
    from src.navigator import Navigator

class VirtualEvacuationSystem:
    def __init__(self, map_image_path):
        # 1. 맵 이미지 로드
        self.original_map = cv2.imread(map_image_path)
        if self.original_map is None:
            # 파일이 없을 경우를 대비해 빈 이미지 생성 (오류 방지)
            self.original_map = np.zeros((480, 640, 3), dtype=np.uint8)
        
        self.h, self.w = self.original_map.shape[:2]
        self.grid_size = 10 
        
        # 2. 맵 분석 (장애물 마스크 생성)
        gray = cv2.cvtColor(self.original_map, cv2.COLOR_BGR2GRAY)
        _, self.static_obstacle_mask = cv2.threshold(gray, 60, 255, cv2.THRESH_BINARY)
        
        # 3. 모듈 초기화
        self.grid_map = GridMap(self.w, self.h, self.grid_size)
        self.navigator = Navigator()

        # [좌표 보정 로직 추가]
        # 사용자가 제공한 좌표의 기준 해상도 (get_coords.py 기준)
        REF_W, REF_H = 640, 480
        
        # 현재 로드된 맵 이미지와의 비율 계산
        # 이미지가 더 크거나 작아도 비율에 맞춰 좌표를 이동시킵니다.
        sx = self.w / REF_W
        sy = self.h / REF_H

        # 4. 좌표 정의 (비율 적용)
        # 입력해주신 (640x480) 기준 좌표에 스케일(sx, sy)을 곱해줍니다.
        self.exits = {
            "Exit_1 (Bot_Blue)": (int(28 * sx), int(366 * sy)),    # 좌측 하단
            "Exit_2 (Bot_Green)": (int(560 * sx), int(361 * sy)),  # 우측 하단 (int 변환 수정)
            "Exit_3 (Top_Green)": (int(290 * sx), int(19 * sy))    # 상단 중앙
        }
        
        # 5개의 LED 도트판 위치
        self.led_nodes = {
            "LED_1 (우상)": (int(548 * sx), int(55 * sy)),
            "LED_2 (중하)": (int(288 * sx), int(360 * sy)),
            "LED_3 (중앙)": (int(286 * sx), int(193 * sy)),
            "LED_4 (좌측)": (int(29 * sx), int(195 * sy))
        }

    def process(self, fire_data):
        """
        fire_data: [(x, y), ...] 또는 [(x, y, radius), ...] 혼용 가능
        """
        display_img = self.original_map.copy()
        
        # 1. 그리드 리셋
        self.grid_map.reset()
        self.grid_map.update_obstacles_from_mask(self.static_obstacle_mask)
        
        # 2. 화재 등록 및 시각화
        for item in fire_data:
            # 데이터 형식이 (x, y)인지 (x, y, r)인지 확인
            if len(item) == 3:
                fx, fy, fr = item
            else:
                fx, fy = item
                fr = 60 # 기본 반지름
            
            # 그리드맵에 장애물 등록
            self.grid_map.set_obstacle_rect(int(fx - fr), int(fy - fr), int(fr*2), int(fr*2))
            
            # 시각화 (동심원 효과)
            cv2.circle(display_img, (int(fx), int(fy)), int(fr), (0, 0, 200), -1)       
            cv2.circle(display_img, (int(fx), int(fy)), int(fr*0.7), (0, 100, 255), -1) 
            cv2.circle(display_img, (int(fx), int(fy)), int(fr*0.4), (0, 255, 255), -1) 
            
            cv2.putText(display_img, "FIRE", (int(fx)-20, int(fy)), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # 3. 비상구 등록
        for name, (ex, ey) in self.exits.items():
            self.grid_map.add_exit(ex, ey, 20, 20)
            
            color = (255, 0, 0) if "Blue" in name else (0, 255, 0)
            cv2.circle(display_img, (int(ex), int(ey)), 15, color, -1)
            cv2.putText(display_img, "EXIT", (int(ex)-20, int(ey)-20), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        # 4. 경로 계산
        results = {}
        # 키 정렬을 통해 LED 번호 순서대로 처리 (LED_1 -> LED_2...)
        for name in sorted(self.led_nodes.keys()):
            nx, ny = self.led_nodes[name]
            path = self.grid_map.get_shortest_path(nx, ny)
            direction = "STOP"
            
            # LED 위치 표시 (노란색)
            cv2.circle(display_img, (int(nx), int(ny)), 10, (0, 255, 255), -1)
            
            if len(path) > 1:
                # 경로 그리기
                pts = np.array(path, np.int32)
                cv2.polylines(display_img, [pts], False, (0, 255, 0), 2)
                
                # 방향 계산 (5칸 앞)
                target_idx = min(5, len(path)-1)
                target_pos = path[target_idx]
                direction = self.navigator.get_direction((nx, ny), target_pos)
                
                # 화살표 그리기
                self._draw_arrow(display_img, (nx, ny), direction)
            else:
                direction = "BLOCKED" # 길이 막힘
                cv2.putText(display_img, "X", (int(nx), int(ny)), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)

            results[name] = direction

        return display_img, results

    def _draw_arrow(self, img, pos, direction):
        x, y = int(pos[0]), int(pos[1])
        color = (0, 165, 255) # 오렌지색
        thickness = 3
        d = 30
        
        end_x, end_y = x, y
        if "UP" in direction: end_y -= d
        if "DOWN" in direction: end_y += d
        if "LEFT" in direction: end_x -= d
        if "RIGHT" in direction: end_x += d
        
        if direction != "STOP":
            cv2.arrowedLine(img, (x, y), (end_x, end_y), color, thickness, tipLength=0.5)
            # 텍스트 표시
            cv2.putText(img, direction, (x-20, y+30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)