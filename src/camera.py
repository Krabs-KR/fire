import cv2

class Camera:
    def __init__(self, source=0):
        """
        카메라를 초기화합니다.
        :param source: 카메라 소스 (기본값 0).
        """
        # 1) Windows에서 MSMF 대신 DSHOW 백엔드 먼저 시도
        self.cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)

        # 2) 만약 이게 안 되면 기본 백엔드로 한 번 더 시도
        if not self.cap.isOpened():
            print("[WARN] CAP_DSHOW로 열기 실패, 기본 백엔드로 재시도합니다.")
            self.cap = cv2.VideoCapture(source)

        if not self.cap.isOpened():
            raise ValueError("Could not open video source (index: {})".format(source))

    def get_frame(self):
        ret, frame = self.cap.read()
        return ret, frame

    def release(self):
        if self.cap is not None:
            self.cap.release()
