import numpy as np
import heapq
import cv2

class GridMap:
    def __init__(self, width, height, grid_size=20):
        """
        그리드 맵을 초기화합니다.
        :param width: 영역의 너비 (픽셀).
        :param height: 영역의 높이 (픽셀).
        :param grid_size: 각 그리드 셀의 크기 (픽셀).
        """
        self.width = width
        self.height = height
        self.grid_size = grid_size
        self.cols = width // grid_size
        self.rows = height // grid_size

        # 0 = 빈 칸, 1 = 장애물
        self.grid = np.zeros((self.rows, self.cols), dtype=np.uint8)

        # 탈출구 셀 목록 (gx, gy)
        self.exits = []

    def _to_grid(self, x, y):
        gx = int(x // self.grid_size)
        gy = int(y // self.grid_size)
        gx = max(0, min(self.cols - 1, gx))
        gy = max(0, min(self.rows - 1, gy))
        return gx, gy

    def _to_pixel(self, gx, gy):
        cx = gx * self.grid_size + self.grid_size // 2
        cy = gy * self.grid_size + self.grid_size // 2
        return cx, cy

    def set_obstacle_rect(self, x, y, w, h):
        """
        픽셀 기준 사각형 영역을 장애물로 표시.
        """
        x2 = x + w
        y2 = y + h
        for px in range(x, x2, self.grid_size):
            for py in range(y, y2, self.grid_size):
                gx, gy = self._to_grid(px, py)
                self.grid[gy, gx] = 1

    def add_exit(self, x, y, w, h):
        """
        검은색으로 표시된 탈출구의 bounding box를 받아
        중심을 그리드 좌표로 변환해 저장.
        """
        cx = x + w / 2
        cy = y + h / 2
        gx, gy = self._to_grid(cx, cy)
        if (gx, gy) not in self.exits:
            self.exits.append((gx, gy))

    def draw_grid(self, img, color=(60, 60, 60)):
        """
        디버깅용: 맵 위에 격자를 그려줌.
        """
        h, w = img.shape[:2]
        # 세로선
        for c in range(self.cols + 1):
            x = c * self.grid_size
            cv2.line(img, (x, 0), (x, h), color, 1)
        # 가로선
        for r in range(self.rows + 1):
            y = r * self.grid_size
            cv2.line(img, (0, y), (w, y), color, 1)

        # 탈출구 표시
        for gx, gy in self.exits:
            cx, cy = self._to_pixel(gx, gy)
            cv2.circle(img, (cx, cy), 5, (0, 255, 0), -1)  # 초록색 점

    # 나중에 필요하면 여기서 BFS / A* 추가해서 경로 계산 가능
    def get_shortest_path(self, start_x, start_y):
        """
        A*를 사용하여 시작점에서 탈출구까지의 최단 경로를 찾습니다.
        :param start_x: 시작 x 좌표 (픽셀).
        :param start_y: 시작 y 좌표 (픽셀).
        :return: 경로를 나타내는 픽셀 좌표의 (x, y) 튜플 리스트.
        """
        if not self.exits:
            return []

        start_node = self._to_grid(start_x, start_y)
        
        # 가장 가까운 탈출구 찾기 (직선 거리 기준)
        shortest_path = []
        min_length = float('inf')

        for exit_pos in self.exits:
            path = self._astar(start_node, exit_pos)
            if path and len(path) < min_length:
                min_length = len(path)
                shortest_path = path
        
        return shortest_path

    def _astar(self, start_node, end_node):
        if self.grid[start_node[1], start_node[0]] == 1:
            return [] # 시작점이 불 속에 있음

        # A* 알고리즘
        open_set = []
        heapq.heappush(open_set, (0, start_node))
        came_from = {}
        g_score = {start_node: 0}
        f_score = {start_node: self._heuristic(start_node, end_node)}

        while open_set:
            current = heapq.heappop(open_set)[1]

            if current == end_node:
                return self._reconstruct_path(came_from, current)

            for neighbor in self._get_neighbors(current):
                tentative_g_score = g_score[current] + 1

                if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g_score
                    f_score[neighbor] = tentative_g_score + self._heuristic(neighbor, end_node)
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))

        return [] # 경로를 찾을 수 없음

    def _heuristic(self, a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1]) # 맨해튼 거리

    def _get_neighbors(self, node):
        x, y = node
        neighbors = []
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]: # 4방향 연결
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.cols and 0 <= ny < self.rows:
                if self.grid[ny, nx] == 0:
                    neighbors.append((nx, ny))
        return neighbors

    def _reconstruct_path(self, came_from, current):
        total_path = [current]
        while current in came_from:
            current = came_from[current]
            total_path.append(current)
        total_path.reverse()
        return [self._to_pixel(x, y) for x, y in total_path]
