/*
 * 4 路紅外線探頭 digitalRead 讀值（ESP32）
 * 每 50 ms 印出一行 4 個探頭的 digitalRead 值
 *   1 ＝ 沒擋住
 *   0 ＝ 擋住（本模組擋住時輸出 LOW）
 *
 * 接線：主控板 OUT4(1元)→G27、OUT3(5元)→G26、OUT2(10元)→G25、OUT1(50元)→G33
 * 開發板選「ESP32 Dev Module」，序列埠監控視窗設 115200
 * 也可以開「工具 → 序列繪圖家」看波形（把下面 PLOT_MODE 改成 true）
 */

const byte SENSOR_PIN[4] = {27, 26, 25, 33};   // 1元、5元、10元、50元
const unsigned long INTERVAL_MS = 50;          // 印出間隔
const bool PLOT_MODE = false;                  // true：序列繪圖家格式

unsigned long lastPrint = 0;

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 4; i++) pinMode(SENSOR_PIN[i], INPUT_PULLUP);
  delay(300);
  if (!PLOT_MODE) Serial.println("1元(G27)  5元(G26)  10元(G25)  50元(G33)");
}

void loop() {
  if (millis() - lastPrint < INTERVAL_MS) return;
  lastPrint = millis();

  int v1  = digitalRead(SENSOR_PIN[0]);
  int v5  = digitalRead(SENSOR_PIN[1]);
  int v10 = digitalRead(SENSOR_PIN[2]);
  int v50 = digitalRead(SENSOR_PIN[3]);

  if (PLOT_MODE) {
    // 4 條線上下錯開，才不會疊在一起
    Serial.printf("1yuan:%d,5yuan:%d,10yuan:%d,50yuan:%d\n", v1 + 6, v5 + 4, v10 + 2, v50);
  } else {
    Serial.printf("    %d         %d          %d          %d\n", v1, v5, v10, v50);
  }
}
