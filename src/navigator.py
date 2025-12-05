import math

class Navigator:
    def __init__(self):
        pass

    def get_direction(self, current_pos, next_pos):
        """
        현재 좌표(cx, cy)와 다음 목표 좌표(nx, ny)를 받아
        8방향(대각선 포함) 중 하나를 반환합니다.
        """
        cx, cy = current_pos
        nx, ny = next_pos
        
        dx = nx - cx
        dy = ny - cy  # 이미지 좌표계에서는 아래로 갈수록 y 증가

        # 거리가 너무 가까우면 정지 (노이즈 방지)
        if abs(dx) < 5 and abs(dy) < 5:
            return "STOP"

        # 각도 계산 (라디안 -> 도)
        # 이미지 좌표계(y가 아래로 증가)를 고려하여 -dy를 사용해 일반 수학 좌표계로 변환
        angle = math.degrees(math.atan2(-dy, dx))
        
        # 음수 각도를 0~360도로 변환
        if angle < 0:
            angle += 360

        # === 8방향 판별 (45도 섹터 나누기) ===
        # 0도(Right), 45도(Up-Right), 90도(Up), 135도(Up-Left)...
        
        if (0 <= angle < 22.5) or (337.5 <= angle <= 360):
            return "RIGHT"
        elif 22.5 <= angle < 67.5:
            return "UP-RIGHT"  # [요청하신 오른쪽 대각선]
        elif 67.5 <= angle < 157.5:
            return "UP"
        # elif 112.5 <= angle < 157.5:
        #     return "UP-LEFT"
        elif 157.5 <= angle < 202.5:
            return "LEFT"
        elif 202.5 <= angle < 247.5:
            return "DOWN-LEFT"
        elif 247.5 <= angle < 292.5:
            return "DOWN"
        elif 292.5 <= angle < 337.5:
            return "DOWN-RIGHT"
            
        return "STOP"