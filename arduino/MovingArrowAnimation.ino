#include "LedControl.h"

// ==========================================
// 1. 하드웨어 및 모듈 설정 (이 부분만 수정하세요!)
// ==========================================
const int DIN_PIN = 12;
const int CLK_PIN = 11;
const int CS_PIN  = 10;
const int NUM_DEVICES = 5; // 연결된 모듈 개수

// [핵심] 각 모듈별로 표시할 화살표 방향을 설정합니다.
// 배열의 인덱스는 모듈 번호(0, 1, 2...)와 일치합니다.
// 방향 코드: 0(우), 1(우하), 2(하), 3(좌하), 4(좌), 5(좌상), 6(상), 7(우상)
// 예시: 0번 모듈은 왼쪽(4), 1번 모듈은 아래쪽(2) ...
int moduleDirections[NUM_DEVICES] = {4, 2, 0, 6}; 

// 점멸 속도 설정 (ms)
const int BLINK_INTERVAL = 500; // 0.5초마다 깜빡임

LedControl lc = LedControl(DIN_PIN, CLK_PIN, CS_PIN, NUM_DEVICES);

// ==========================================
// 2. 전역 변수
// ==========================================
unsigned long lastBlinkTime = 0; // 점멸 타이머
bool isLedOn = true;             // 현재 켜짐/꺼짐 상태

// ==========================================
// 3. 패턴 데이터 (화살표 8방향)
// ==========================================
const byte arrows[8][8] = {
  // 0: ➡️ 오른쪽
  { B00011000, B00001100, B00000110, B11111111, B11111111, B00000110, B00001100, B00011000 },
  // 1: ↘️ 오른쪽 아래
  { B00011000, B00001100, B00000110, B00000011, B00000011, B00000110, B00001100, B00011000 },
  // 2: ⬇️ 아래쪽
  { B00011000, B00111100, B01111110, B11111111, B00011000, B00011000, B00011000, B00011000 },
  // 3: ↙️ 왼쪽 아래
  { B00011000, B00110000, B01100000, B11000000, B11000000, B01100000, B00110000, B00011000 },
  // 4: ⬅️ 왼쪽
  { B00011000, B00110000, B01100000, B11111111, B11111111, B01100000, B00110000, B00011000 },
  // 5: ↖️ 왼쪽 위
  { B00011000, B00110000, B01100000, B11000000, B11000000, B01100000, B00110000, B00011000 },
  // 6: ⬆️ 위쪽
  { B00011000, B00111100, B01111110, B11111111, B00011000, B00011000, B00011000, B00011000 },
  // 7: ↗️ 오른쪽 위
  { B00011000, B00001100, B00000110, B00000011, B00000011, B00000110, B00001100, B00011000 }
};

// ==========================================
// 4. 초기화 (Setup)
// ==========================================
void setup() {
  for (int index = 0; index < lc.getDeviceCount(); index++) {
    lc.shutdown(index, false);
    lc.setIntensity(index, 8); // 밝기 조절 (0~15)
    lc.clearDisplay(index);
  }
  lastBlinkTime = millis();
}

// ==========================================
// 5. 메인 루프 (Loop)
// ==========================================
void loop() {
  unsigned long currentTime = millis();

  // [기능 1] 점멸 타이밍 체크
  if (currentTime - lastBlinkTime >= BLINK_INTERVAL) {
    lastBlinkTime = currentTime;
    isLedOn = !isLedOn; // 상태 토글 (켜짐 <-> 꺼짐)

    // 변경된 상태를 모든 모듈에 반영
    updateModules();
  }
}

// ==========================================
// 6. 사용자 정의 함수
// ==========================================

// [핵심] 현재 상태(isLedOn)와 설정값(moduleDirections)에 따라 LED 제어
void updateModules() {
  for (int i = 0; i < NUM_DEVICES; i++) {
    if (isLedOn) {
      // 켜져야 할 때: 각 모듈에 설정된 방향의 화살표 출력
      // 예: moduleDirections[i]가 4라면 4번(왼쪽) 화살표를 i번 모듈에 그림
      int dir = moduleDirections[i];
      displayPattern(i, arrows[dir]);
    } else {
      // 꺼져야 할 때: 화면 지움
      lc.clearDisplay(i);
    }
  }
}

// 특정 모듈(deviceIndex)에 8x8 패턴(patternArray)을 그리는 함수
void displayPattern(int deviceIndex, const byte* patternArray) {
  // 모듈 번호가 유효 범위를 벗어나면 무시 (안전장치)
  if (deviceIndex >= NUM_DEVICES) return;

  for (int row = 0; row < 8; row++) {
    lc.setRow(deviceIndex, row, patternArray[row]);
  }
}
