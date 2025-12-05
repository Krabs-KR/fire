import cv2
import numpy as np
from src.map import GridMap
from src.navigator import Navigator

class VirtualEvacuationSystem:
    def __init__(self, map_image_path):
        # 1. 맵 이미지 로드
        self.original_map = cv2.imread(map_image_path)
        if self.original_map is None:
            raise FileNotFoundError(f"이미지를 찾을 수 없습니다: {map_image_path}")
        
        self.h, self.w = self.original_map.shape[:2]
        self.grid_size = 10 # 정밀도를 위해 그리드 사이즈 조절
        
        # 2. 맵 분석 (검은색=길(0), 그 외=벽(1))
        # 이미지를 흑백으로 변환하여 장애물 마스크 생성
        gray = cv2.cvtColor(self.original_map, cv2.COLOR_BGR2GRAY)
        # 검은색(보도) 부분이 0~50 정도라고 가정, 밝은 부분은 벽/상점
        _, self.static_obstacle_mask = cv2.threshold(gray, 60, 255, cv2.THRESH_BINARY)
        
        # 3. 모듈 초기화
        self.grid_map = GridMap(self.w, self.h, self.grid_size)
        self.navigator = Navigator()

        # 4. 좌표 정의 (이미지 픽셀 좌표 근사치)
        # [이미지 분석 기반 좌표 설정]
        self.exits = {
            "Top_Green": (480, 50),     # 상단 중앙 녹색 비상구
            "Bot_Green": (880, 450),    # 우측 하단 녹색 비상구
            "Bot_Blue": (100, 450)      # 좌측 하단 파란 출입구 (상시)
        }
        
        # 5개의 LED 도트판 위치 (흰색 점들 위치 근사)
        self.led_nodes = {
            "LED_1 (좌상)": (180, 150),
            "LED_2 (좌하)": (180, 350),
            "LED_3 (중앙)": (480, 250),
            "LED_4 (우상)": (800, 150),
            "LED_5 (중하)": (480, 420)
        }

    def process(self, fire_locations=[]):
        """
        화재 위치 리스트를 받아 경로를 계산하고 시각화된 이미지를 반환
        fire_locations: [(x, y, radius), ...]
        """
        display_img = self.original_map.copy()
        
        # 1. 그리드 리셋 및 정적 장애물(벽/상점) 등록
        self.grid_map.reset()
        self.grid_map.update_obstacles_from_mask(self.static_obstacle_mask)
        
        # 2. 화재(동적 장애물) 등록 및 그리기
        for (fx, fy) in fire_locations:
            # 화재 반경 설정 (예: 60px)
            fire_radius = 60
            self.grid_map.set_obstacle_rect(fx - fire_radius, fy - fire_radius, 
                                          fire_radius*2, fire_radius*2)
            
            # 시각화: 불 표시
            cv2.circle(display_img, (fx, fy), fire_radius, (0, 0, 255), -1)
            cv2.putText(display_img, "FIRE", (fx-20, fy), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # 3. 비상구 등록 (화재가 근처에 있으면 이용 불가 처리 가능)
        active_exits = []
        for name, (ex, ey) in self.exits.items():
            # 비상구가 화재로 막혔는지 확인하는 로직 추가 가능
            # 여기서는 단순히 모든 비상구를 목적지로 등록
            self.grid_map.add_exit(ex, ey, 20, 20)
            
            # 시각화: 비상구 표시
            color = (255, 0, 0) if "Blue" in name else (0, 255, 0)
            cv2.circle(display_img, (ex, ey), 15, color, -1)
            cv2.putText(display_img, "EXIT", (ex-20, ey-20), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        # 4. 각 LED 노드별 경로 계산
        results = {}
        
        for name, (nx, ny) in self.led_nodes.items():
            path = self.grid_map.get_shortest_path(nx, ny)
            direction = "STOP"
            
            # 시각화: LED 위치 표시
            cv2.circle(display_img, (nx, ny), 10, (0, 255, 255), -1)
            
            if len(path) > 1:
                # 경로 그리기
                cv2.polylines(display_img, [np.array(path)], False, (0, 255, 0), 2)
                
                # 방향 계산 (5칸 앞 또는 경로 끝)
                target_idx = min(5, len(path)-1)
                target_pos = path[target_idx]
                direction = self.navigator.get_direction((nx, ny), target_pos)
                
                # 화살표 그리기 (매우 중요: 아두이노가 표시할 방향)
                self._draw_arrow(display_img, (nx, ny), direction)
            else:
                direction = "BLOCKED"
                cv2.putText(display_img, "X", (nx, ny), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)

            results[name] = direction

        return display_img, results

    def _draw_arrow(self, img, pos, direction):
        x, y = pos
        color = (0, 165, 255) # 오렌지색
        thickness = 3
        d = 30 # 화살표 길이
        
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
