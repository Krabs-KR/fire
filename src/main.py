import cv2
import numpy as np
from camera import Camera
from detector import Detector
from map import GridMap

MAP_W, MAP_H = 600, 600
GRID_SIZE = 20

def main():
    # 카메라 초기화
    try:
        cam = Camera(0)
    except ValueError:
        print("카메라를 찾을 수 없습니다. 종료합니다.")
        return

    detector = Detector()
    last_valid_corners = None
    grid_map = None

    # 시뮬레이션된 도트 매트릭스 위치 (상대 좌표 0.0 ~ 1.0)
    dot_matrices_rel = [
        (0.2, 0.2), (0.5, 0.2), (0.8, 0.2),
        (0.2, 0.5),             (0.8, 0.5),
        (0.2, 0.8), (0.5, 0.8), (0.8, 0.8)
    ]

    show_debug_masks = False  # d 키로 토글
    print("q: 종료, r: 맵 리셋, d: 디버그 마스크 토글")

    while True:
        ret, frame = cam.get_frame()
        if not ret:
            print("카메라 프레임을 가져올 수 없습니다.")
            break

        # 크기 통일
        frame = cv2.resize(frame, (640, 480))
        # 원본에 코너/사각형을 그려줄 복사본
        orig_vis = frame.copy()

        # ---- 1. 코너 검출 ----
        corners, corner_mask = detector.detect_corners(frame)

        # 유효한 코너라면 마지막 값 업데이트
        final_corners = None
        if corners is not None:
            area = cv2.contourArea(corners)
            frame_area = frame.shape[0] * frame.shape[1]
            if area > frame_area * 0.05:   # 화면의 5% 이상일 때만 유효
                last_valid_corners = corners

        if last_valid_corners is not None:
            final_corners = last_valid_corners.copy()

        # ---- 2. 투시 변환 or 원본 사용 ----
        warped = None
        if final_corners is not None:
            warped_tmp = detector.warp_perspective(frame, final_corners, MAP_W, MAP_H)
            if warped_tmp is not None and warped_tmp.size > 0:
                # 완전 까만 화면인지 체크 (디버깅용)
                if np.mean(warped_tmp) > 1:   # 평균이 0 근처면 거의 검정
                    warped = warped_tmp

            # 원본에 코너와 사각형 그리기 (어디를 맵으로 쓰는지 보이게)
            pts = final_corners.reshape(-1, 2).astype(int)
            for p in pts:
                cv2.circle(orig_vis, (p[0], p[1]), 6, (255, 0, 0), -1)
            cv2.polylines(orig_vis, [pts], True, (0, 255, 255), 2)

        # 디버깅을 위해: warped가 없으면 원본 그대로 사용
        if warped is None:
            process_frame = frame.copy()
            warp_raw = None
            using_warp = False
        else:
            process_frame = warped
            warp_raw = warped.copy()   # 격자 그리기 전 원본 warp 결과
            using_warp = True

        # ---- 3. 맵 객체 준비 (warp 기준) ----
        if using_warp:
            if grid_map is None:
                grid_map = GridMap(MAP_W, MAP_H, grid_size=GRID_SIZE)
        else:
            grid_map = None  # warp 안 쓰면 맵도 리셋

        # ---- 4. 불 / 탈출구 감지 ----
        fire_boxes, fire_mask = detector.detect_fire(process_frame)
        exit_boxes, exit_mask = detector.detect_exit(process_frame)

        # 탈출구를 그리드에 추가
        if grid_map is not None:
            grid_map.exits.clear()
            for (x, y, w, h) in exit_boxes:
                grid_map.add_exit(x, y, w, h)

        # ---- 5. 시각화 (process_frame 위에 그리기) ----
        vis = process_frame.copy()

        # 불 영역 표시 (빨간 박스)
        for (x, y, w, h) in fire_boxes:
            cv2.rectangle(vis, (x, y), (x + w, y + h), (0, 0, 255), 2)

        # 탈출구 영역 표시 (초록 박스)
        for (x, y, w, h) in exit_boxes:
            cv2.rectangle(vis, (x, y), (x + w, y + h), (0, 255, 0), 2)

        # 격자 + 탈출구 점 표시 (warp 사용 시)
        if grid_map is not None and using_warp:
            grid_map.draw_grid(vis)
            
            # 도트 매트릭스 및 경로 시각화
            for (rel_x, rel_y) in dot_matrices_rel:
                # 상대 좌표를 절대 좌표로 변환
                dm_x = int(rel_x * MAP_W)
                dm_y = int(rel_y * MAP_H)
                
                # 도트 매트릭스 위치 그리기 (노란색 점)
                cv2.circle(vis, (dm_x, dm_y), 8, (0, 255, 255), -1)
                
                # 최단 경로 계산
                path = grid_map.get_shortest_path(dm_x, dm_y)
                
                if len(path) > 1:
                    # 경로 그리기 (파란색 선)
                    for j in range(len(path) - 1):
                        cv2.line(vis, path[j], path[j+1], (255, 0, 0), 2)
                    
                    # 화살표 방향 결정 (다음 단계)
                    next_step = path[1]
                    direction_vector = (next_step[0] - dm_x, next_step[1] - dm_y)
                    
                    # 화살표 그리기
                    mag = np.sqrt(direction_vector[0]**2 + direction_vector[1]**2)
                    if mag > 0:
                        end_point = (int(dm_x + direction_vector[0]/mag * 40), int(dm_y + direction_vector[1]/mag * 40))
                        cv2.arrowedLine(vis, (dm_x, dm_y), end_point, (0, 255, 255), 3)
                else:
                    # 경로를 찾을 수 없음 (빨간 X)
                    cv2.putText(vis, "X", (dm_x, dm_y), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        # ---- 6. 창 여러 개 띄우기 ----
        cv2.imshow('Original', orig_vis)                     # 코너/사각형 표시된 원본
        cv2.imshow('Processed (Warped or Original)', vis)    # warp + 격자/박스
        if warp_raw is not None:
            cv2.imshow('WarpedRaw', warp_raw)                # 격자 그리기 전 순수 warp

        if show_debug_masks:
            corner_m = corner_mask if corner_mask is not None else np.zeros(frame.shape[:2], dtype=np.uint8)
            fire_m = fire_mask if fire_mask is not None else np.zeros(process_frame.shape[:2], dtype=np.uint8)
            exit_m = exit_mask if exit_mask is not None else np.zeros(process_frame.shape[:2], dtype=np.uint8)

            fire_m_resized = cv2.resize(fire_m, (corner_m.shape[1], corner_m.shape[0]))
            exit_m_resized = cv2.resize(exit_m, (corner_m.shape[1], corner_m.shape[0]))

            debug_mask = np.hstack([
                corner_m,
                fire_m_resized,
                exit_m_resized
            ])
            cv2.imshow('Debug Masks (Blue / Red / Black)', debug_mask)
        else:
            try:
                if cv2.getWindowProperty('Debug Masks (Blue / Red / Black)', 0) >= 0:
                    cv2.destroyWindow('Debug Masks (Blue / Red / Black)')
            except:
                pass

        # ---- 7. 키 입력 처리 ----
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:  # q 또는 ESC
            break
        elif key == ord('r'):
            last_valid_corners = None
            grid_map = None
            print("Map reset.")
        elif key == ord('d'):
            show_debug_masks = not show_debug_masks
            print("Debug masks:", "ON" if show_debug_masks else "OFF")

    cam.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
