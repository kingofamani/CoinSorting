/*
 * 智能分幣機 v2（光耦版）— ESP32 正式程式
 * ESP32（ESP32-WROOM-32，38P 擴展板）＋ 4 個槽型光耦模組（LM393，槽寬 10 mm）＋ 4 位數七段顯示器（TM1637）
 * 開發板選「ESP32 Dev Module」，序列埠監控視窗 115200
 * ※ 擴展板黃色跳帽要設在 3.3V；光耦模組 VCC 接 V 排針（3.3V），不要接 5V 排針
 * 不需安裝任何函式庫
 *
 * 4 個感測器的位置（見 03_v2_光耦版/laser_v2/out/report.md）：
 *   S1  ：在 1 元滑道內，只有 1 元會經過
 *   S5  ：跨在 1|5 間隔條，5、10、50 元都會經過
 *   S10 ：跨在 5|10 間隔條，10、50 元會經過
 *   S50 ：跨在 10|50 間隔條，只有 50 元會經過
 * 計數公式（C＝感測器計數，N＝真實枚數）：
 *   N1 = C1、N5 = C5 − C10、N10 = C10 − C50、N50 = C50
 *   總金額 = C1 + 5×C5 + 5×C10 + 40×C50
 *   防錯：C5 ≥ C10 ≥ C50 必須成立；不成立時顯示器的冒號（或第 2 位小數點）會亮，序列埠印出原因
 *
 * 接線（排線兩端貼標籤，盒端照標籤插）：
 *   S1 → G27、S5 → G26、S10 → G25、S50 → G33（各接該排的 S）；VCC → V、GND → G
 *   顯示器 CLK → G14、DIO → G13
 *
 * 使用：
 *   1. 感測器槽裡清空再開電源：開機顯示「1234」約 1.5 秒，這段時間自動判定「擋住時是 HIGH 還是 LOW」
 *   2. 顯示「0」後再開馬達、倒硬幣；顯示器顯示總金額
 *   3. 歸零：按 ESP32 板上的 BOOT 鍵（不重開機）；或按 RST 鍵（重開機，會重新判定）
 *
 * 序列埠指令（輸入後按 Enter）：
 *   v   即時狀態：開／關（每 0.2 秒印出 4 個感測器的電位與計數；用手指或名片擋槽，看對應那一欄有沒有變）
 *   r   歸零
 *   a   重新自動判定擋住電位（4 個槽裡先清空）
 *   ?   說明與目前設定
 *
 * 防重複計數用「亮區重新上膛」：光束要連續亮 REARM_US 以上，下一次擋住才算新的一枚。
 *   硬幣經過時邊緣的抖動（一枚產生好幾個脈衝）中間的亮縫很短，不會被多算；
 *   兩枚相貼滾過時中間的亮縫通常有幾 ms，仍會分開算。
 *   REARM_US 請用 04_光耦測試原型/opto_test_esp32 丟幣測試報告「方法二」的建議值（報告寫 ms 就乘 1000）；預設 3000。
 * 另外單一段擋住不到 MIN_BLOCK_US（預設 0.3 ms）的雜訊不算（一串很短的雜訊也不算）；一枚硬幣擋住光束至少有好幾 ms。
 * 每一枚在光束「重新變亮」時才確定計入（所以顯示會在硬幣離開感測器時才加）。
 *
 * 用中斷計數：TM1637 更新一次約 20 ms，這段時間硬幣經過也不會漏算。
 * 每 5 ms 核對一次腳位（loop、更新顯示器與印序列埠的過程中都會做）：連續兩次和記錄的狀態不同、
 * 而且中間沒有中斷進來，代表中斷漏掉了邊緣（例如訊號邊緣劇烈抖動時）→ 照實際電位校正。
 *
 * ESP32 Arduino core 2.0.x 與 3.x 都能編譯：只用 attachInterrupt(digitalPinToInterrupt(腳), 函式, CHANGE)、
 * ARDUINO_ISR_ATTR、portMUX 臨界區、pinMode、digitalRead、micros、millis、Serial.printf 這些兩版共通的寫法；
 * uint32_t 在兩版型別不同，印數字時一律先轉成 (unsigned long) 或 (long) 再用 %lu／%ld。
 */

// ===== 1. 腳位 =====
const int NCH = 4;
const uint8_t SENSOR_PIN[NCH] = {27, 26, 25, 33};          // S1、S5、S10、S50
const char *SENSOR_NAME[NCH]  = {"S1", "S5", "S10", "S50"};
const uint8_t CLK_PIN = 14;                                 // 顯示器 CLK
const uint8_t DIO_PIN = 13;                                 // 顯示器 DIO
const uint8_t BOOT_PIN = 0;                                 // 板上的 BOOT 鍵（按下＝LOW），開機後拿來歸零

// ===== 2. 設定 =====
const int LEVEL_AUTO = -1;
const int BLOCKED_LEVEL_SETTING = LEVEL_AUTO;   // 擋住時的電位：LEVEL_AUTO＝開機自動判定；也可直接寫 HIGH 或 LOW
const uint32_t REARM_US = 3000;                 // 亮區重新上膛（微秒，3000＝3 ms）：丟一枚卻 +2 就調大（例如 5000）；兩枚相貼只算 1 就調小
const uint32_t MIN_BLOCK_US = 300;              // 擋住不到這麼久（微秒）當雜訊；馬達開著、沒硬幣「擋住次數」也會自己增加時調大
const unsigned long RESYNC_MS = 5;              // loop 校正的間隔：連續兩次（相隔這麼久）都不一致、中間沒有中斷，才校正
const byte BRIGHTNESS = 4;                      // 顯示器亮度 0~7
const unsigned long CAL_MS = 1500;              // 開機判定電位的時間（顯示 1234 的時間）
const unsigned long LONG_BLOCK_MS = 3000;       // 某個感測器連續擋住超過這麼久就提醒（卡幣或判定反了）
const unsigned long STATUS_MS = 200;            // v 模式的印出間隔

// 數字 0~9 的七段碼（bit0=a … bit6=g；bit7＝冒號或小數點）
const byte SEG_CODE[10] = {0x3F, 0x06, 0x5B, 0x4F, 0x66, 0x6D, 0x7D, 0x07, 0x7F, 0x6F};
const byte SEG_COLON = 0x80;

// ===== 3. 中斷與計數的狀態（中斷和 loop 共用，存取時要進臨界區）=====
portMUX_TYPE countMux = portMUX_INITIALIZER_UNLOCKED;
volatile int  blockedLevel[NCH] = {HIGH, HIGH, HIGH, HIGH};   // 擋住時的電位
volatile bool chBlocked[NCH]    = {false, false, false, false}; // 目前是否擋住
volatile uint32_t lastClearUs[NCH] = {0, 0, 0, 0};            // 光束最近一次變亮的時間
volatile uint32_t blockStartUs[NCH] = {0, 0, 0, 0};           // 這次擋住開始的時間
volatile uint32_t lastEdgeUs[NCH] = {0, 0, 0, 0};             // 最近一次進中斷的時間（loop 校正用）
volatile bool pending[NCH] = {false, false, false, false};    // 有一枚開始了、還沒確定計入
volatile long counts[NCH] = {0, 0, 0, 0};                     // C1、C5、C10、C50
volatile uint32_t pulses[NCH] = {0, 0, 0, 0};                 // 擋住次數（含抖動，給 v 模式看）
volatile uint32_t resyncs[NCH] = {0, 0, 0, 0};                // loop 校正的次數（給 v 模式看）
volatile uint32_t edgeSeq[NCH] = {0, 0, 0, 0};                // 進中斷的次數（loop 校正用：兩次檢查之間有沒有中斷）
bool resyncOn = false;                                        // 中斷接上後才做校正
bool mismatchSeen[NCH] = {false, false, false, false};        // 上一次檢查已經看到不一致
uint32_t mismatchSeq[NCH] = {0, 0, 0, 0};                     // 看到不一致時的 edgeSeq

void resyncStates();   // 先宣告：顯示器與序列埠輸出的過程中也會呼叫

// ===== 4. loop 用的狀態 =====
long shownC[NCH] = {-1, -1, -1, -1};       // 上一次顯示／印出時的計數
bool longWarned[NCH] = {false, false, false, false};
bool statusMode = false;
bool dispOk = false;
unsigned long lastStatusMs = 0;
bool bootWasDown = false;
unsigned long bootDownMs = 0;

// ===== 5. TM1637 驅動（兩條線：CLK、DIO）=====
// 腳位設成「開漏輸出」：寫 LOW＝拉低、寫 HIGH＝放開（由模組上的電阻拉高）
void lineLow(uint8_t p)  { digitalWrite(p, LOW); }
void lineHigh(uint8_t p) { digitalWrite(p, HIGH); }
void bitDelay()          { delayMicroseconds(100); }

void tmStart() {
  lineHigh(DIO_PIN); lineHigh(CLK_PIN); bitDelay();
  lineLow(DIO_PIN); bitDelay();
}

void tmStop() {
  lineLow(CLK_PIN); bitDelay();
  lineLow(DIO_PIN); bitDelay();
  lineHigh(CLK_PIN); bitDelay();
  lineHigh(DIO_PIN); bitDelay();
}

bool tmWrite(byte b) {                  // 回傳 true＝顯示器有回應
  resyncStates();                        // 更新顯示器約 20 ms，中間也要校正
  for (int i = 0; i < 8; i++) {
    lineLow(CLK_PIN); bitDelay();
    if (b & 0x01) lineHigh(DIO_PIN); else lineLow(DIO_PIN);
    bitDelay();
    lineHigh(CLK_PIN); bitDelay();
    b >>= 1;
  }
  lineLow(CLK_PIN); lineHigh(DIO_PIN); bitDelay();   // 讀取回應
  lineHigh(CLK_PIN); bitDelay();
  bool ack = (digitalRead(DIO_PIN) == LOW);
  lineLow(CLK_PIN); bitDelay();
  return ack;
}

bool tmShow(const byte seg[4]) {
  bool ok = true;
  tmStart(); ok &= tmWrite(0x40); tmStop();               // 自動遞增位址寫入
  tmStart(); ok &= tmWrite(0xC0);                          // 從最左邊那位開始
  for (int i = 0; i < 4; i++) ok &= tmWrite(seg[i]);
  tmStop();
  tmStart(); ok &= tmWrite(0x88 | (BRIGHTNESS & 7)); tmStop();   // 開顯示＋亮度
  return ok;
}

// 顯示數字（前面不補 0）；超過 9999 顯示「----」（序列埠有完整金額）；warn＝true 時點亮冒號（或第 2 位小數點）
bool showNumber(long n, bool warn) {
  byte seg[4] = {0, 0, 0, 0};
  if (n < 0) n = 0;
  if (n > 9999) {
    for (int i = 0; i < 4; i++) seg[i] = 0x40;   // 中間橫線 g
  } else {
    for (int i = 3; i >= 0; i--) {
      seg[i] = SEG_CODE[n % 10];
      n /= 10;
      if (n == 0) break;
    }
  }
  if (warn) seg[1] |= SEG_COLON;
  return tmShow(seg);
}

// ===== 6. 中斷：每個感測器一個進入點 =====
// 狀態改變時的計數規則（呼叫前要先進臨界區；中斷和 loop 校正共用）：
//   變成擋住：光束在這之前已經連續亮了 REARM_US 以上 → 新的一枚開始（待定）；
//             REARM_US 內又擋住 → 還是同一枚（抖動）
//   變成亮  ：有待定的一枚，而且「剛結束的這一段擋住」超過 MIN_BLOCK_US → 計入；
//             太短（雜訊或前緣抖動）就繼續待定。看的是單一段的長度，一串很短的雜訊加起來再長也不會算。
ARDUINO_ISR_ATTR void applyEdge(int i, bool b, uint32_t t) {
  chBlocked[i] = b;
  if (b) {
    blockStartUs[i] = t;
    pulses[i] = pulses[i] + 1;
    if ((uint32_t)(t - lastClearUs[i]) >= REARM_US) pending[i] = true;
  } else {
    lastClearUs[i] = t;
    if (pending[i] && (uint32_t)(t - blockStartUs[i]) >= MIN_BLOCK_US) {
      counts[i] = counts[i] + 1;
      pending[i] = false;
    }
  }
}

ARDUINO_ISR_ATTR void handleEdge(int i) {
  uint32_t t = micros();
  int lv = digitalRead(SENSOR_PIN[i]);
  portENTER_CRITICAL_ISR(&countMux);
  lastEdgeUs[i] = t;
  edgeSeq[i] = edgeSeq[i] + 1;
  bool b = (lv == blockedLevel[i]);
  if (b != chBlocked[i]) applyEdge(i, b, t);   // 讀到和目前相同的電位＝極短突波，不理
  portEXIT_CRITICAL_ISR(&countMux);
}

ARDUINO_ISR_ATTR void isrS1()  { handleEdge(0); }
ARDUINO_ISR_ATTR void isrS5()  { handleEdge(1); }
ARDUINO_ISR_ATTR void isrS10() { handleEdge(2); }
ARDUINO_ISR_ATTR void isrS50() { handleEdge(3); }

// 每 RESYNC_MS 檢查一次腳位和記錄的狀態。只看到一次不一致可能只是中斷還沒跑（中斷有延遲），不能動；
// 連續兩次都不一致、而且兩次之間完全沒有中斷進來（edgeSeq 沒變），才是中斷漏掉了邊緣 → 照實際電位校正。
// 邊緣時間用最近一次中斷的時間（漏掉的邊緣就發生在那附近），抖動中被校正時才不會多算。
void resyncStates() {
  static unsigned long lastMs = 0;
  if (!resyncOn || millis() - lastMs < RESYNC_MS) return;
  lastMs = millis();
  for (int i = 0; i < NCH; i++) {
    int lv = digitalRead(SENSOR_PIN[i]);
    portENTER_CRITICAL(&countMux);
    bool b = (lv == blockedLevel[i]);
    if (b == chBlocked[i]) {
      mismatchSeen[i] = false;
    } else if (mismatchSeen[i] && mismatchSeq[i] == edgeSeq[i]) {
      applyEdge(i, b, lastEdgeUs[i]);
      resyncs[i] = resyncs[i] + 1;
      mismatchSeen[i] = false;
    } else {
      mismatchSeen[i] = true;
      mismatchSeq[i] = edgeSeq[i];
    }
    portEXIT_CRITICAL(&countMux);
  }
}

void attachAll() {
  attachInterrupt(digitalPinToInterrupt(SENSOR_PIN[0]), isrS1, CHANGE);
  attachInterrupt(digitalPinToInterrupt(SENSOR_PIN[1]), isrS5, CHANGE);
  attachInterrupt(digitalPinToInterrupt(SENSOR_PIN[2]), isrS10, CHANGE);
  attachInterrupt(digitalPinToInterrupt(SENSOR_PIN[3]), isrS50, CHANGE);
  resyncOn = true;
}

void detachAll() {
  resyncOn = false;
  for (int i = 0; i < NCH; i++) detachInterrupt(digitalPinToInterrupt(SENSOR_PIN[i]));
}

// ===== 7. 開機判定擋住電位（槽裡要清空）=====
// 量 ms 毫秒：閒置時多數是哪個電位，擋住就是另一個。也記下這段時間訊號變了幾次（不穩就警告）。
void detectLevels(unsigned long ms) {
  long highCnt[NCH] = {0, 0, 0, 0};
  long changes[NCH] = {0, 0, 0, 0};
  int prev[NCH];
  long n = 0;
  for (int i = 0; i < NCH; i++) prev[i] = digitalRead(SENSOR_PIN[i]);
  unsigned long t0 = millis();
  while (millis() - t0 < ms) {
    for (int i = 0; i < NCH; i++) {
      int lv = digitalRead(SENSOR_PIN[i]);
      if (lv == HIGH) highCnt[i]++;
      if (lv != prev[i]) { changes[i]++; prev[i] = lv; }
    }
    n++;
    delay(1);
  }

  int lvl[NCH];
  bool blk[NCH];
  for (int i = 0; i < NCH; i++) {
    int idle = (highCnt[i] * 2 >= n) ? HIGH : LOW;
    if (BLOCKED_LEVEL_SETTING == LEVEL_AUTO) lvl[i] = (idle == HIGH) ? LOW : HIGH;
    else lvl[i] = BLOCKED_LEVEL_SETTING;
    blk[i] = (digitalRead(SENSOR_PIN[i]) == lvl[i]);
  }
  uint32_t now = micros();
  portENTER_CRITICAL(&countMux);
  for (int i = 0; i < NCH; i++) {
    blockedLevel[i] = lvl[i];
    chBlocked[i] = blk[i];
    lastClearUs[i] = now;
    blockStartUs[i] = now;
    lastEdgeUs[i] = now;
    pending[i] = false;
    mismatchSeen[i] = false;
  }
  portEXIT_CRITICAL(&countMux);

  Serial.println(BLOCKED_LEVEL_SETTING == LEVEL_AUTO ? "擋住電位（開機自動判定）：" : "擋住電位（程式指定）：");
  bool allSame = true;
  for (int i = 0; i < NCH; i++) {
    Serial.printf("  %-3s G%-2d 閒置 %s → 擋住＝%s", SENSOR_NAME[i], (int)SENSOR_PIN[i],
                  (highCnt[i] * 2 >= n) ? "HIGH" : "LOW", lvl[i] == HIGH ? "HIGH" : "LOW");
    if (changes[i] > 0) Serial.printf("  ⚠ 這段時間訊號變了 %ld 次（接觸不良、槽裡有東西、或模組壞）", changes[i]);
    Serial.println();
    if (lvl[i] != lvl[0]) allSame = false;
  }
  if (!allSame) {
    Serial.println("⚠ 4 個感測器判定不一樣：同款模組應該相同。開機時可能有槽被擋住；清空後輸入 a，或按 RST 重開。");
  }
}

// ===== 8. 計數、計算、輸出 =====
void snapshot(long c[NCH], bool blk[NCH], uint32_t bst[NCH], uint32_t pul[NCH]) {
  portENTER_CRITICAL(&countMux);
  for (int i = 0; i < NCH; i++) {
    c[i] = counts[i];
    blk[i] = chBlocked[i];
    bst[i] = blockStartUs[i];
    pul[i] = pulses[i];
  }
  portEXIT_CRITICAL(&countMux);
}

// 歸零：正在感測器裡、還沒計入的那一枚也一起丟掉。軌道上還有硬幣時歸零會讓 C5≥C10≥C50 不成立，先停馬達再歸零。
void resetCounts() {
  bool busy = false;
  portENTER_CRITICAL(&countMux);
  for (int i = 0; i < NCH; i++) {
    if (chBlocked[i]) busy = true;
    counts[i] = 0; pulses[i] = 0; resyncs[i] = 0; pending[i] = false;
  }
  portEXIT_CRITICAL(&countMux);
  if (busy) Serial.println("⚠ 歸零時有感測器正被擋住：軌道上還有硬幣的話，之後的 C5≥C10≥C50 可能不成立。請停馬達、清空後再歸零。");
  for (int i = 0; i < NCH; i++) shownC[i] = -1;   // 下一次 loop 會重畫顯示器
}

long totalOf(const long c[NCH]) { return c[0] + 5 * c[1] + 5 * c[2] + 40 * c[3]; }
bool consistent(const long c[NCH]) { return c[1] >= c[2] && c[2] >= c[3]; }

void printCounts(const long c[NCH], bool first) {
  if (!first) {
    Serial.print("+");
    for (int i = 0; i < NCH; i++) {
      if (c[i] != shownC[i]) Serial.printf(" %s%+ld", SENSOR_NAME[i], c[i] - shownC[i]);
    }
    Serial.print("  ");
  }
  resyncStates();                        // 序列埠一行可能要印十幾 ms，中間也要校正
  Serial.printf("| C1=%ld C5=%ld C10=%ld C50=%ld | 1元×%ld 5元×%ld 10元×%ld 50元×%ld | 總額 %ld 元\n",
                c[0], c[1], c[2], c[3], c[0], c[1] - c[2], c[2] - c[3], c[3], totalOf(c));
  resyncStates();
  if (!consistent(c)) {
    if (c[1] < c[2]) Serial.printf("  ⚠ C5(%ld) < C10(%ld)：S5 漏算或 S10 多算，金額可能不準\n", c[1], c[2]);
    if (c[2] < c[3]) Serial.printf("  ⚠ C10(%ld) < C50(%ld)：S10 漏算或 S50 多算，金額可能不準\n", c[2], c[3]);
  }
}

// 計數有變就更新顯示器並印出
void updateOutputs() {
  long c[NCH]; bool blk[NCH]; uint32_t bst[NCH]; uint32_t pul[NCH];
  snapshot(c, blk, bst, pul);
  bool changed = false, first = false;
  for (int i = 0; i < NCH; i++) {
    if (c[i] != shownC[i]) changed = true;
    if (shownC[i] < 0) first = true;
  }
  if (!changed) return;
  dispOk = showNumber(totalOf(c), !consistent(c));
  printCounts(c, first);
  for (int i = 0; i < NCH; i++) shownC[i] = c[i];
}

// 某個感測器連續擋住太久：卡幣，或開機時判定反了（每一段擋住只提醒一次）
void checkLongBlock() {
  long c[NCH]; bool blk[NCH]; uint32_t bst[NCH]; uint32_t pul[NCH];
  snapshot(c, blk, bst, pul);
  uint32_t now = micros();
  for (int i = 0; i < NCH; i++) {
    if (!blk[i]) { longWarned[i] = false; continue; }
    if (!longWarned[i] && (uint32_t)(now - bst[i]) > LONG_BLOCK_MS * 1000UL) {
      Serial.printf("⚠ %s 連續擋住超過 %lu 秒：卡幣？或開機時槽裡有東西（判定反了）→ 清空後輸入 a\n",
                    SENSOR_NAME[i], (unsigned long)(LONG_BLOCK_MS / 1000));
      longWarned[i] = true;
    }
  }
}

// 每秒把太舊的時間往前推（最多保留 10 秒），避免 micros() 約 71 分鐘繞回一圈後誤判。
// now 在臨界區裡取，中斷不會在取完 now 之後又改到這些時間。
void refreshClearTimes() {
  static unsigned long lastMs = 0;
  if (millis() - lastMs < 1000) return;
  lastMs = millis();
  portENTER_CRITICAL(&countMux);
  uint32_t now = micros();
  for (int i = 0; i < NCH; i++) {
    if (!chBlocked[i] && (int32_t)(now - lastClearUs[i]) > 10000000L) lastClearUs[i] = now - 10000000UL;
    if ((int32_t)(now - lastEdgeUs[i]) > 10000000L) lastEdgeUs[i] = now - 10000000UL;
  }
  portEXIT_CRITICAL(&countMux);
}

// v 模式：每 0.2 秒一行，■＝擋住、·＝亮
// 「校正」次數一直增加：訊號邊緣抖得很厲害或接觸不良，檢查排線與模組
void printStatus() {
  long c[NCH]; bool blk[NCH]; uint32_t bst[NCH]; uint32_t pul[NCH];
  uint32_t rs[NCH];
  snapshot(c, blk, bst, pul);
  portENTER_CRITICAL(&countMux);
  for (int i = 0; i < NCH; i++) rs[i] = resyncs[i];
  portEXIT_CRITICAL(&countMux);
  for (int i = 0; i < NCH; i++) {
    Serial.printf("%s %s 腳位=%d 計數=%ld 擋住次數=%lu 校正=%lu", SENSOR_NAME[i], blk[i] ? "■" : "·",
                  digitalRead(SENSOR_PIN[i]), c[i], (unsigned long)pul[i], (unsigned long)rs[i]);
    Serial.print(i < NCH - 1 ? " | " : "\n");
    resyncStates();
  }
}

void printHelp() {
  Serial.println("指令：v＝即時狀態開／關、r＝歸零、a＝重新判定擋住電位（槽裡先清空）、?＝說明");
  Serial.println("BOOT 鍵＝歸零（不重開機）；RST 鍵＝重開機（會重新判定）");
  Serial.printf("設定：REARM_US=%lu（%.1f ms）、MIN_BLOCK_US=%lu；擋住電位 S1=%s S5=%s S10=%s S50=%s；顯示器%s\n",
                (unsigned long)REARM_US, REARM_US / 1000.0, (unsigned long)MIN_BLOCK_US,
                blockedLevel[0] == HIGH ? "HIGH" : "LOW", blockedLevel[1] == HIGH ? "HIGH" : "LOW",
                blockedLevel[2] == HIGH ? "HIGH" : "LOW", blockedLevel[3] == HIGH ? "HIGH" : "LOW",
                dispOk ? "有回應" : "沒有回應（檢查 CLK→G14、DIO→G13、VCC、GND）");
}

// 指令都是一個字母，收到就執行（序列埠監控視窗的換行設定選哪一種都可以）
void handleSerial() {
  while (Serial.available() > 0) {
    char ch = (char)Serial.read();
    if (ch == 'v' || ch == 'V') {
      statusMode = !statusMode;
      Serial.println(statusMode ? "即時狀態：開（再輸入 v 關掉）" : "即時狀態：關");
    } else if (ch == 'r' || ch == 'R') {
      resetCounts();
      Serial.println("已歸零");
    } else if (ch == 'a' || ch == 'A') {
      Serial.println("重新判定擋住電位：4 個槽裡要清空，約 1.5 秒……");
      detachAll();
      showNumber(1234, false);
      detectLevels(CAL_MS);
      attachAll();
      resetCounts();
      Serial.println("已重新判定並歸零");
    } else if (ch == '?') {
      printHelp();
    }
  }
}

// BOOT 鍵：按下再放開（按住至少 50 ms）就歸零
void handleBootKey() {
  bool down = (digitalRead(BOOT_PIN) == LOW);
  if (down && !bootWasDown) bootDownMs = millis();
  if (!down && bootWasDown && millis() - bootDownMs >= 50) {
    resetCounts();
    Serial.println("BOOT 鍵：已歸零");
  }
  bootWasDown = down;
}

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < NCH; i++) pinMode(SENSOR_PIN[i], INPUT_PULLUP);
  pinMode(BOOT_PIN, INPUT_PULLUP);
  // 開漏輸出＋可讀回（讀顯示器回應用）＋內建上拉
  pinMode(CLK_PIN, OUTPUT_OPEN_DRAIN | INPUT | PULLUP);
  pinMode(DIO_PIN, OUTPUT_OPEN_DRAIN | INPUT | PULLUP);
  lineHigh(CLK_PIN);
  lineHigh(DIO_PIN);

  // 開機自我測試：顯示 1234，同時判定擋住電位（槽裡要清空）
  dispOk = showNumber(1234, false);
  delay(100);
  Serial.println();
  Serial.println("分幣機 v2（光耦版）開機：判定擋住電位中，槽裡請保持清空……");
  detectLevels(CAL_MS);
  attachAll();
  resetCounts();
  Serial.println(dispOk ? "顯示器有回應" : "⚠ 顯示器沒有回應：檢查 CLK→G14、DIO→G13、VCC、GND");
  printHelp();
  Serial.println("分幣機就緒");
}

void loop() {
  handleSerial();
  handleBootKey();
  resyncStates();
  refreshClearTimes();
  updateOutputs();
  checkLongBlock();
  if (statusMode && millis() - lastStatusMs >= STATUS_MS) {
    lastStatusMs = millis();
    printStatus();
  }
}
