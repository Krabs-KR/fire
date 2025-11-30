import cv2
import numpy as np

class Detector:
    def __init__(self):
        pass

    # -------------------------
    # 1) 맵 코너(파란색) 검출
    # -------------------------
    def detect_corners(self, frame):
        """
        맵의 4개 모서리(파란색)를 감지합니다.
        :param frame: 입력 이미지 프레임.
        :return: (corners, mask)
                 corners: 4x1x2 float32 (TL, TR, BR, BL) 또는 None
                 mask: 파란색 마스크 (디버깅용)
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # 파란색 범위 (조금 좁게)
        lower_blue = np.array([90, 50, 50])
        upper_blue = np.array([140, 255, 255])
        mask = cv2.inRange(hsv, lower_blue, upper_blue)

        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if len(contours) < 4:
            return None, mask

        # 면적 기준 상위 4개만 사용 (너무 작은 점 제거)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:4]

        pts = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < 100:  # 너무 작은 건 무시
                continue
            M = cv2.moments(c)
            if M['m00'] == 0:
                continue
            cx = M['m10'] / M['m00']
            cy = M['m01'] / M['m00']
            pts.append([cx, cy])

        if len(pts) != 4:
            return None, mask

        pts = np.array(pts, dtype=np.float32)

        # (x + y)가 가장 작은 점 -> TL
        # (x - y)가 가장 큰 점 -> TR
        # (x + y)가 가장 큰 점 -> BR
        # (x - y)가 가장 작은 점 -> BL
        s = pts.sum(axis=1)
        diff = np.diff(pts, axis=1).reshape(-1)

        tl = pts[np.argmin(s)]
        br = pts[np.argmax(s)]
        tr = pts[np.argmax(diff)]
        bl = pts[np.argmin(diff)]

        corners = np.array([tl, tr, br, bl], dtype=np.float32).reshape(-1, 1, 2)
        return corners, mask

    # -------------------------
    # 2) 투시 변환
    # -------------------------
    def warp_perspective(self, frame, corners, width, height):
        """
        감지된 코너를 이용해 프레임을 투시 변환합니다.
        :param frame: 원본 프레임.
        :param corners: 4x1x2 float32 (TL, TR, BR, BL).
        :param width: 결과 맵 너비.
        :param height: 결과 맵 높이.
        :return: warped 이미지 또는 None
        """
        if corners is None or len(corners) != 4:
            return None

        # 목적지 좌표 (직사각형)
        dst = np.array([
            [0, 0],
            [width - 1, 0],
            [width - 1, height - 1],
            [0, height - 1]
        ], dtype=np.float32)

        src = corners.reshape(4, 2).astype(np.float32)
        M = cv2.getPerspectiveTransform(src, dst)
        warped = cv2.warpPerspective(frame, M, (width, height))

        return warped

    # -------------------------
    # 3) 불(빨간색) 감지
    # -------------------------
    def detect_fire(self, frame):
        """
        빨간색으로 표시된 '불' 위치를 감지합니다.
        :param frame: 입력 이미지 (warp 후 맵 기준).
        :return: (bounding_boxes, mask)
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # 빨간색은 두 구간으로 나눠 잡기
        lower_red1 = np.array([0, 100, 100])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([160, 100, 100])
        upper_red2 = np.array([179, 255, 255])

        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask = cv2.bitwise_or(mask1, mask2)

        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        fire_boxes = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < 200:
                continue
            x, y, w, h = cv2.boundingRect(c)
            fire_boxes.append((x, y, w, h))

        return fire_boxes, mask

    # -------------------------
    # 4) 탈출구(검은색) 감지
    # -------------------------
    def detect_exit(self, frame):
        """
        검은색으로 표시된 탈출구를 감지합니다.
        :param frame: 입력 이미지 (warp 후 맵 기준).
        :return: (bounding_boxes, mask)
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # 검은색은 밝기(V)가 낮은 영역
        lower_black = np.array([0, 0, 0])
        upper_black = np.array([180, 255, 60])  # V <= 60 정도
        mask = cv2.inRange(hsv, lower_black, upper_black)

        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        exit_boxes = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < 200:
                continue
            x, y, w, h = cv2.boundingRect(c)
            exit_boxes.append((x, y, w, h))

        return exit_boxes, mask
