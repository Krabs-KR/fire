import cv2
import numpy as np

class Detector:
    def __init__(self):
        # 유지보수를 위한 임계값 설정
        self.WALL_THRESH = 200       # 흰색 벽으로 인식할 밝기 기준 (0~255))
        self.MIN_WALL_AREA = 500     # 잡음 제거를 위한 최소 벽 면적
        self.MIN_FIRE_AREA = 10      # 최소 불 영역 크기

    def detect_corners(self, frame):
        """
        [최적화됨] HSV + 침식 연산으로 그림자 제거 및 사각형 검출 강화
        """
        # 1. 노이즈를 줄이기 위해 블러 처리
        img_blur = cv2.GaussianBlur(frame, (5, 5), 0)
        
        # 2. BGR -> HSV 변환
        hsv = cv2.cvtColor(img_blur, cv2.COLOR_BGR2HSV)
        
        # [수정 1] 그림자 제거를 위해 밝기(맨 뒤 숫자)를 60 -> 30으로 대폭 낮춤
        lower_black = np.array([0, 0, 0])
        upper_black = np.array([180, 255, 30]) 
        
        mask = cv2.inRange(hsv, lower_black, upper_black)

        # [수정 2] 침식(Erode) 연산 추가: 흰색 영역을 깎아내서 테두리와 분리시킴 (매우 중요!)
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=2)  # 깎아내기
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel) # 구멍 메우기
        
        # 5. 윤곽선 찾기
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return None, mask

        biggest = None
        max_area = 0
        
        h, w = frame.shape[:2]
        screen_area = w * h

        for cnt in contours:
            area = cv2.contourArea(cnt)
            
            # 노이즈 제거 및 너무 큰(화면 전체가 잡힌 경우) 제외
            if area < 1000 or area > (screen_area * 0.95):
                continue

            # 근사화 (사각형 모양 찾기)
            peri = cv2.arcLength(cnt, True)
            # 0.02는 너무 엄격할 수 있으므로 0.03~0.04로 살짝 완화해도 좋음
            approx = cv2.approxPolyDP(cnt, 0.03 * peri, True) 

            # 점이 4개(사각형)이고 가장 큰 영역을 찾음
            # (점이 4개가 안 나오면 사각형이 아니라고 판단하고 넘어감)
            if len(approx) == 4 and area > max_area:
                biggest = approx
                max_area = area

        if biggest is None:
            return None, mask

        # 좌표 정렬 로직
        pts = biggest.reshape(4, 2).astype(np.float32)
        s = pts.sum(axis=1)
        diff = np.diff(pts, axis=1).reshape(-1)

        tl = pts[np.argmin(s)]
        br = pts[np.argmax(s)]
        tr = pts[np.argmin(diff)]
        bl = pts[np.argmax(diff)]

        corners = np.array([tl, tr, br, bl], dtype=np.float32).reshape(-1, 1, 2)
        return corners, mask



    def warp_perspective(self, frame, corners, width, height):
        if corners is None: return None
        
        dst = np.array([[0, 0], [width-1, 0], [width-1, height-1], [0, height-1]], dtype=np.float32)
        src = corners.reshape(4, 2).astype(np.float32)
        M = cv2.getPerspectiveTransform(src, dst)
        return cv2.warpPerspective(frame, M, (width, height))

    def detect_walls_in_map(self, warped_frame):
        """
        [새 기능] 맵 내부의 흰색 벽을 감지합니다.
        검은색 바닥(어두움) vs 흰색 벽(밝음)
        """
        gray = cv2.cvtColor(warped_frame, cv2.COLOR_BGR2GRAY)
        
        # 밝은 부분(흰색 벽)만 추출
        _, mask = cv2.threshold(gray, self.WALL_THRESH, 255, cv2.THRESH_BINARY)
        
        # 노이즈 제거
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        return mask # GridMap에서 이 마스크를 사용해 장애물 등록

    def detect_fire(self, frame):
        """
        [수정됨] 실제 불꽃(밝음) + 꺼진 양초(빨간색) 모두 감지
        """
        # === 1. 불꽃 감지 (기존 로직: 밝고 붉은 빛) ===
        b, g, r = cv2.split(frame)
        _, mask_bright = cv2.threshold(r, 230, 255, cv2.THRESH_BINARY)
        r_int = r.astype(np.int16)
        b_int = b.astype(np.int16)
        mask_light_color = np.where((r_int - b_int) > 30, 255, 0).astype(np.uint8)
        mask_flame = cv2.bitwise_and(mask_bright, mask_light_color)

        # === 2. 빨간색 양초 본체 감지 (HSV 색상) ===
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # 빨간색 범위 정의 (꺼진 양초 색상)
        # Range 1 (0 ~ 10)
        lower_red1 = np.array([0, 100, 100])
        upper_red1 = np.array([10, 255, 255])
        # Range 2 (170 ~ 180)
        lower_red2 = np.array([170, 100, 100])
        upper_red2 = np.array([180, 255, 255])
        
        mask_red1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask_candle_body = cv2.bitwise_or(mask_red1, mask_red2)

        # === 3. 두 결과 합치기 (불꽃 OR 양초본체) ===
        mask = cv2.bitwise_or(mask_flame, mask_candle_body)
        
        # 잡음 제거 및 영역 확장
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=1) 
        mask = cv2.dilate(mask, kernel, iterations=3) 

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        fire_boxes = []
        for c in contours:
            area = cv2.contourArea(c)
            
            # 너무 작은 점 제외, 너무 큰 영역(창문 등) 제외
            if area < self.MIN_FIRE_AREA or area > 3000: 
                continue
            
            x, y, w, h = cv2.boundingRect(c)
            fire_boxes.append((x, y, w, h))

        return fire_boxes, mask

    def detect_exit(self, frame):
        """
        탈출구 인식. 바닥이 검은색이므로 탈출구는 '녹색'이나 다른 색이어야 인식 가능합니다.
        (기존의 녹색 종이 기준으로 작성)
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        # 녹색 범위 (환경에 따라 튜닝 필요)
        lower_green = np.array([40, 50, 50])
        upper_green = np.array([80, 255, 255])
        
        mask = cv2.inRange(hsv, lower_green, upper_green)
        
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        exit_boxes = []
        for c in contours:
            if cv2.contourArea(c) < 200: continue
            x, y, w, h = cv2.boundingRect(c)
            exit_boxes.append((x, y, w, h))
            
        return exit_boxes, mask