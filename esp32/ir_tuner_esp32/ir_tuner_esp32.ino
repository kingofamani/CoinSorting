/*
 * 分幣機 4 路紅外線調校工具 — ESP32 版（講師用）
 *
 * 用途：
 *   1. 調可變電阻（靈敏度）：即時顯示每一路是否「一直觸發」或「抖動」
 *   2. 找出最適合的 DEBOUNCE_MS（防重複計數時間）：
 *      丟已知數量的硬幣，程式會同時用 17 種時間試算，直接告訴你哪個最好
 *
 * 接線（與正式程式相同）：
 *   主控板 OUT4(1元)→G27、OUT3(5元)→G26、OUT2(10元)→G25、OUT1(50元)→G33
 *   顯示器 CLK→G14、DIO→G13（沒接顯示器也能用）
 *   擴展板黃色跳帽設 3.3V
 *
 * 開發板選「ESP32 Dev Module」，序列埠監控視窗設 115200。
 * 在輸入框打指令後按 Enter：
 *   v      數值模式（開機預設）：每 50 ms 印出 4 個探頭的值
 *   g      圖形模式：每 50 ms 輸出，給「序列繪圖家」（Serial Plotter）畫波形
 *   l      即時模式：每秒一行狀態＋警告，調可變電阻用
 *   c10    丟幣測試：每一路各丟 10 枚（數字可改），丟完輸入 e
 *   c      丟幣測試（不指定枚數，程式自己判斷）
 *   e      結束丟幣測試並產生報告
 *   d50    即時計數使用的 DEBOUNCE 改成 50 ms（數字可改）
 *   p      每個脈衝要不要逐筆顯示（切換）
 *   r      計數與紀錄歸零
 *   ?      說明
 *
 * 用中斷記錄每一次訊號變化（精準到微秒），不會漏掉很短的抖動。
 * 不需安裝任何函式庫。
 */

#include "driver/gpio.h"

// ===== 腳位與設定 =====
byte SENSOR_PIN[4] = {27, 26, 25, 33};          // 1元、5元、10元、50元
const int  COIN_VALUE[4] = {1, 5, 10, 50};
const char *COIN_NAME[4] = {" 1元", " 5元", "10元", "50元"};
const char *PLOT_NAME[4] = {"1yuan", "5yuan", "10yuan", "50yuan"};
const byte CLK_PIN = 14;
const byte DIO_PIN = 13;
const int  BLOCKED_LEVEL = LOW;                 // 擋住時輸出 LOW（本模組）
const uint32_t NOISE_US = 1000;                 // 擋住不到 1 ms 視為雜訊
const unsigned long STATUS_MS = 1000;           // 即時模式狀態列更新間隔
const unsigned long VALUE_MS = 50;              // 數值／圖形模式的輸出間隔

// 丟幣測試時同時試算的 DEBOUNCE 值（ms）
const int CAND[] = {0, 2, 5, 10, 15, 20, 25, 30, 40, 50, 60, 80, 100, 120, 150, 200, 300};
const int NCAND = sizeof(CAND) / sizeof(CAND[0]);

const byte SEG_CODE[10] = {0x3F, 0x06, 0x5B, 0x4F, 0x66, 0x6D, 0x7D, 0x07, 0x7F, 0x6F};
const byte SEG_DASH = 0x40;
const byte SEG_FULL = 0x7F;

// ===== 中斷：記錄每一次訊號變化 =====
struct Edge { uint32_t t; uint8_t ch; uint8_t level; };
const int EBUF = 2048;
Edge ebuf[EBUF];
volatile int eHead = 0;
volatile int eTail = 0;
volatile uint32_t eOverflow = 0;
portMUX_TYPE mux = portMUX_INITIALIZER_UNLOCKED;

// ===== 每一路的狀態與紀錄 =====
const int MAXP = 400;
struct Chan {
  bool blocked;
  uint32_t start;
  // 紀錄（丟幣測試用）
  uint32_t pStart[MAXP];
  uint32_t pWidth[MAXP];
  int n;
  int dropped;
  // 即時計數
  bool hasAccepted;
  uint32_t lastAccepted;
  long liveCount;
  // 即時模式統計（每個狀態列區間）
  uint32_t winEdges;
  uint64_t winBlockedUs;
  uint32_t winNoise;
  uint32_t lastPulseStart;
  bool hasLastPulse;
  bool winSeen;          // 這 50 ms 內是否被擋過
};
Chan chs[4];
uint32_t tmp[MAXP];   // 報告排序用

char mode = 'v';              // v=數值 g=圖形 l=即時 c=丟幣測試
int expectedCoins = 0;        // 丟幣測試預期枚數（0＝不指定）
unsigned long liveDebounceMs = 50;
bool printPulses = true;
uint32_t winStart = 0;
unsigned long lastStatus = 0;
unsigned long lastValue = 0;
unsigned long lastDisp = 0;
bool dispDirty = true;
uint32_t testStart = 0;

// ===== 中斷處理 =====
void IRAM_ATTR onEdge(void *arg) {
  int ch = (int)(intptr_t)arg;
  uint32_t t = micros();
  uint8_t lv = gpio_get_level((gpio_num_t)SENSOR_PIN[ch]);
  portENTER_CRITICAL_ISR(&mux);
  int n = (eHead + 1) % EBUF;
  if (n != eTail) {
    ebuf[eHead].t = t;
    ebuf[eHead].ch = (uint8_t)ch;
    ebuf[eHead].level = lv;
    eHead = n;
  } else {
    eOverflow++;
  }
  portEXIT_CRITICAL_ISR(&mux);
}

bool popEdge(uint32_t &t, uint8_t &ch, uint8_t &level) {
  bool ok = false;
  portENTER_CRITICAL(&mux);
  if (eTail != eHead) {
    t = ebuf[eTail].t;
    ch = ebuf[eTail].ch;
    level = ebuf[eTail].level;
    eTail = (eTail + 1) % EBUF;
    ok = true;
  }
  portEXIT_CRITICAL(&mux);
  return ok;
}

// ===== TM1637（開漏輸出）=====
void lineLow(byte p)  { digitalWrite(p, LOW); }
void lineHigh(byte p) { digitalWrite(p, HIGH); }
void bitDelay()       { delayMicroseconds(100); }

void tmStart() { lineHigh(DIO_PIN); lineHigh(CLK_PIN); bitDelay(); lineLow(DIO_PIN); bitDelay(); }
void tmStop()  { lineLow(CLK_PIN); bitDelay(); lineLow(DIO_PIN); bitDelay(); lineHigh(CLK_PIN); bitDelay(); lineHigh(DIO_PIN); bitDelay(); }

bool tmWrite(byte b) {
  for (int i = 0; i < 8; i++) {
    lineLow(CLK_PIN); bitDelay();
    if (b & 0x01) lineHigh(DIO_PIN); else lineLow(DIO_PIN);
    bitDelay();
    lineHigh(CLK_PIN); bitDelay();
    b >>= 1;
  }
  lineLow(CLK_PIN); lineHigh(DIO_PIN); bitDelay();
  lineHigh(CLK_PIN); bitDelay();
  bool ack = (digitalRead(DIO_PIN) == LOW);
  lineLow(CLK_PIN); bitDelay();
  return ack;
}

void tmShow(const byte seg[4]) {
  tmStart(); tmWrite(0x40); tmStop();
  tmStart(); tmWrite(0xC0);
  for (int i = 0; i < 4; i++) tmWrite(seg[i]);
  tmStop();
  tmStart(); tmWrite(0x8E); tmStop();     // 亮度 6
}

void showNumber(long n) {
  byte seg[4] = {0, 0, 0, 0};
  if (n > 9999) n = 9999;
  for (int i = 3; i >= 0; i--) {
    seg[i] = SEG_CODE[n % 10];
    n /= 10;
    if (n == 0) break;
  }
  tmShow(seg);
}

long liveTotal() {
  long t = 0;
  for (int i = 0; i < 4; i++) t += chs[i].liveCount * COIN_VALUE[i];
  return t;
}

void updateDisplay() {
  if (mode == 'l' || mode == 'v' || mode == 'g') {
    // 即時／數值／圖形模式：4 位數＝4 路，左到右 1、5、10、50 元；「-」沒擋、「8」擋住
    byte seg[4];
    for (int i = 0; i < 4; i++) seg[i] = chs[i].blocked ? SEG_FULL : SEG_DASH;
    tmShow(seg);
  } else {
    showNumber(liveTotal());   // 丟幣測試：顯示目前設定下的總金額
  }
}

// ===== 脈衝處理 =====
void resetAll() {
  portENTER_CRITICAL(&mux);
  eTail = eHead;
  eOverflow = 0;
  portEXIT_CRITICAL(&mux);
  for (int i = 0; i < 4; i++) {
    Chan &c = chs[i];
    c.blocked = (digitalRead(SENSOR_PIN[i]) == BLOCKED_LEVEL);
    c.start = micros();
    c.n = 0;
    c.dropped = 0;
    c.hasAccepted = false;
    c.liveCount = 0;
    c.winEdges = 0;
    c.winBlockedUs = 0;
    c.winNoise = 0;
    c.hasLastPulse = false;
    c.winSeen = false;
  }
  winStart = micros();
  dispDirty = true;
}

void onPulseStart(int ch, uint32_t t) {
  Chan &c = chs[ch];
  if (!c.hasAccepted || (t - c.lastAccepted) > liveDebounceMs * 1000UL) {
    c.liveCount++;
    c.lastAccepted = t;
    c.hasAccepted = true;
  }
  c.winSeen = true;
  dispDirty = true;
}

void onPulseEnd(int ch, uint32_t start, uint32_t width) {
  Chan &c = chs[ch];
  dispDirty = true;
  // 區間內擋住的時間
  uint32_t from = (start > winStart) ? start : winStart;
  if (start + width > from) c.winBlockedUs += (start + width) - from;

  if (c.n < MAXP) {
    c.pStart[c.n] = start;
    c.pWidth[c.n] = width;
    c.n++;
  } else {
    c.dropped++;
  }

  if (width < NOISE_US) {
    c.winNoise++;
  } else if (printPulses && mode != 'v' && mode != 'g') {
    Serial.printf("  [%s] 擋住 %6.1f ms", COIN_NAME[ch], width / 1000.0);
    if (c.hasLastPulse) {
      Serial.printf("　距上一次 %8.1f ms", (start - c.lastPulseStart) / 1000.0);
    }
    Serial.printf("　計數 %ld\n", c.liveCount);
  }
  c.lastPulseStart = start;
  c.hasLastPulse = true;
}

void processEdges() {
  uint32_t et;
  uint8_t ech, elv;
  while (popEdge(et, ech, elv)) {
    Chan &c = chs[ech];
    c.winEdges++;
    bool isBlocked = (elv == BLOCKED_LEVEL);
    if (isBlocked && !c.blocked) {
      c.blocked = true;
      c.start = et;
      onPulseStart(ech, et);
    } else if (!isBlocked && c.blocked) {
      c.blocked = false;
      onPulseEnd(ech, c.start, et - c.start);
    }
  }
}

// ===== 即時模式狀態列 =====
void printStatus() {
  uint32_t now = micros();
  uint32_t span = now - winStart;
  if (span == 0) span = 1;
  Serial.print("狀態 ");
  String warn = "";
  for (int i = 0; i < 4; i++) {
    Chan &c = chs[i];
    uint64_t blk = c.winBlockedUs;
    if (c.blocked) {
      uint32_t from = (c.start > winStart) ? c.start : winStart;
      blk += now - from;
    }
    int pct = (int)(blk * 100 / span);
    if (pct > 100) pct = 100;
    Serial.printf("| %s %s %3d%% ", COIN_NAME[i], c.blocked ? "■" : "·", pct);
    if (pct >= 95 && c.winEdges == 0) {
      warn += String("  ⚠") + COIN_NAME[i] + "一直觸發：可變電阻逆時針調低，或檢查對面牆是否反光";
    } else if (c.winNoise >= 5 || c.winEdges >= 40) {
      warn += String("  ⚠") + COIN_NAME[i] + "抖動（" + String(c.winEdges) + " 次變化）：靈敏度剛好卡在邊界，可變電阻再轉一點";
    }
  }
  Serial.printf("| 計數 %ld/%ld/%ld/%ld＝%ld 元（DEBOUNCE %lu ms）\n",
                chs[0].liveCount, chs[1].liveCount, chs[2].liveCount, chs[3].liveCount,
                liveTotal(), liveDebounceMs);
  if (warn.length()) Serial.println(warn);
  if (eOverflow) {
    Serial.printf("  ⚠ 訊號變化太多，漏記 %lu 筆（多半是嚴重抖動）\n", (unsigned long)eOverflow);
    eOverflow = 0;
  }
  for (int i = 0; i < 4; i++) {
    chs[i].winEdges = 0;
    chs[i].winBlockedUs = 0;
    chs[i].winNoise = 0;
  }
  winStart = now;
}

// ===== 數值模式：每 50 ms 印出 4 個探頭 =====
// 1＝沒擋、0＝擋住（本模組擋住輸出 LOW）
// 後面有 * ＝這 50 ms 內曾經被擋過、但印出時已經離開（硬幣很快通過時會這樣）
void printValues() {
  char line[200];
  int n = snprintf(line, sizeof(line), "%8.2fs  ", millis() / 1000.0);
  for (int i = 0; i < 4; i++) {
    int lv = digitalRead(SENSOR_PIN[i]);
    bool passed = chs[i].winSeen && lv != BLOCKED_LEVEL;
    n += snprintf(line + n, sizeof(line) - n, "%s:%d%s %s  ",
                  COIN_NAME[i], lv, passed ? "*" : " ", lv == BLOCKED_LEVEL ? "■" : "·");
    chs[i].winSeen = false;
  }
  snprintf(line + n, sizeof(line) - n, "| 計數 %ld/%ld/%ld/%ld＝%ld 元",
           chs[0].liveCount, chs[1].liveCount, chs[2].liveCount, chs[3].liveCount, liveTotal());
  Serial.println(line);
}

// 圖形模式：給 Arduino IDE「序列繪圖家」，4 條線上下錯開（擋住＝往上跳 1 格）
void printPlot() {
  for (int i = 0; i < 4; i++) {
    int lv = digitalRead(SENSOR_PIN[i]);
    int blockedNow = (lv == BLOCKED_LEVEL || chs[i].winSeen) ? 1 : 0;
    Serial.printf("%s:%d", PLOT_NAME[i], (3 - i) * 2 + blockedNow);
    Serial.print(i < 3 ? "," : "\n");
    chs[i].winSeen = false;
  }
}

// ===== 丟幣測試報告 =====
int simulateCount(int ch, int debounceMs) {
  const Chan &c = chs[ch];
  int cnt = 0;
  bool has = false;
  uint32_t last = 0;
  for (int k = 0; k < c.n; k++) {
    if (!has || (c.pStart[k] - last) > (uint32_t)debounceMs * 1000UL) {
      cnt++;
      last = c.pStart[k];
      has = true;
    }
  }
  return cnt;
}

int cmpU32(const void *a, const void *b) {
  uint32_t x = *(const uint32_t *)a, y = *(const uint32_t *)b;
  return (x > y) - (x < y);
}

void report() {
  Serial.println();
  Serial.println("================ 丟幣測試報告 ================");
  Serial.printf("測試時間 %.1f 秒；", (micros() - testStart) / 1e6);
  if (expectedCoins > 0) Serial.printf("每一路預期 %d 枚\n", expectedCoins);
  else Serial.println("未指定枚數（以最穩定的結果判斷）");

  int allLo = 0, allHi = NCAND - 1;
  bool anyData = false, conflict = false;

  for (int i = 0; i < 4; i++) {
    const Chan &c = chs[i];
    if (c.n == 0) continue;
    anyData = true;
    Serial.println();
    Serial.printf("── %s（G%d）：收到 %d 個脈衝", COIN_NAME[i], SENSOR_PIN[i], c.n);
    if (c.dropped) Serial.printf("（另有 %d 個超過紀錄上限）", c.dropped);
    Serial.println();

    // 擋住時間
    int noise = 0;
    for (int k = 0; k < c.n; k++) { tmp[k] = c.pWidth[k]; if (c.pWidth[k] < NOISE_US) noise++; }
    qsort(tmp, c.n, sizeof(uint32_t), cmpU32);
    Serial.printf("   擋住時間：最短 %.1f ms、中位數 %.1f ms、最長 %.1f ms",
                  tmp[0] / 1000.0, tmp[c.n / 2] / 1000.0, tmp[c.n - 1] / 1000.0);
    if (noise) Serial.printf("；其中 %d 個短於 1 ms（雜訊／抖動）", noise);
    Serial.println();

    // 間隔
    if (c.n >= 2) {
      int m = 0;
      for (int k = 1; k < c.n; k++) tmp[m++] = c.pStart[k] - c.pStart[k - 1];
      qsort(tmp, m, sizeof(uint32_t), cmpU32);
      Serial.print("   相鄰兩次開始的間隔（由短到長前 6 個）：");
      for (int k = 0; k < m && k < 6; k++) Serial.printf("%.1f ", tmp[k] / 1000.0);
      Serial.println("ms");
    }

    // 各 DEBOUNCE 試算
    int cnt[NCAND];
    Serial.print("   不同 DEBOUNCE_MS 的計數：");
    for (int j = 0; j < NCAND; j++) {
      cnt[j] = simulateCount(i, CAND[j]);
      if (j % 6 == 0) Serial.print("\n     ");
      Serial.printf("%3dms→%-4d", CAND[j], cnt[j]);
    }
    Serial.println();

    // 找最佳範圍
    int bestLo = -1, bestHi = -1;
    int target = expectedCoins;
    if (target <= 0) {
      // 沒指定：找 2ms 以上「計數不變」最長的一段
      int runLo = 1;
      for (int j = 2; j <= NCAND; j++) {
        if (j == NCAND || cnt[j] != cnt[runLo]) {
          if (cnt[runLo] > 0 && (bestLo < 0 || (j - 1 - runLo) > (bestHi - bestLo))) {
            bestLo = runLo; bestHi = j - 1;
          }
          runLo = j;
        }
      }
      if (bestLo >= 0) target = cnt[bestLo];
    } else {
      int runLo = -1;
      for (int j = 0; j <= NCAND; j++) {
        bool ok = (j < NCAND && cnt[j] == target);
        if (ok && runLo < 0) runLo = j;
        if (!ok && runLo >= 0) {
          if (bestLo < 0 || (j - 1 - runLo) > (bestHi - bestLo)) { bestLo = runLo; bestHi = j - 1; }
          runLo = -1;
        }
      }
    }

    if (bestLo < 0) {
      Serial.printf("   ✘ 沒有任何 DEBOUNCE 值能得到 %d 枚。\n", target);
      if (cnt[0] < target) {
        Serial.println("     → 有硬幣沒被偵測到：可變電阻順時針調高、探頭再靠近通道，或硬幣疊在一起掉落。");
      } else {
        Serial.println("     → 抖動太嚴重或硬幣間隔太近：先調可變電阻，並讓硬幣一枚一枚落下。");
      }
      conflict = true;
      continue;
    }
    int rec = CAND[(bestLo + bestHi) / 2];
    Serial.printf("   ✔ %d～%d ms 都能得到 %d 枚，這一路建議 %d ms\n",
                  CAND[bestLo], CAND[bestHi], target, rec);
    if (cnt[0] > target) {
      Serial.printf("     （不防重複時會多算 %d 次，代表有抖動；靈敏度可再微調）\n", cnt[0] - target);
    }
    if (bestHi - bestLo < 2) {
      Serial.println("     ⚠ 可用範圍很窄，實際使用可能不穩：建議再調可變電阻，或讓硬幣間隔大一點。");
    }
    if (bestLo > allLo) allLo = bestLo;
    if (bestHi < allHi) allHi = bestHi;
  }

  Serial.println();
  if (!anyData) {
    Serial.println("沒有收到任何訊號：檢查接線、跳帽 3.3V，或可變電阻太低。");
  } else if (conflict || allLo > allHi) {
    Serial.println("✘ 找不到 4 路都適用的單一值，請先依上面的提示調整後再測一次。");
  } else {
    int rec = CAND[(allLo + allHi) / 2];
    Serial.printf("★ 測試的各路共同可用範圍：%d～%d ms\n", CAND[allLo], CAND[allHi]);
    Serial.println("★ 請把正式程式這一行改成：");
    Serial.printf("   const unsigned long DEBOUNCE_MS = %d;\n", rec);
    Serial.printf("  （本工具的即時計數也已改用 %d ms，可以直接再丟幣驗證）\n", rec);
    liveDebounceMs = rec;
  }
  Serial.println("==============================================");
  Serial.println("輸入 c 或 c10 再測一次，輸入 l 回到即時模式。");
}

// ===== 指令 =====
void printHelp() {
  Serial.println();
  Serial.println("========= 分幣機 4 路紅外線調校工具（ESP32）=========");
  Serial.println(" v     數值模式：每 50 ms 印出 4 個探頭的值（開機預設）");
  Serial.println("       1＝沒擋、0＝擋住；*＝這 50 ms 內擋過但已通過");
  Serial.println(" g     圖形模式：開「工具→序列繪圖家」看 4 條波形");
  Serial.println(" l     即時模式：每秒一行狀態與警告，調可變電阻用");
  Serial.println(" c10   丟幣測試：每一路各丟 10 枚，丟完輸入 e（數字可改）");
  Serial.println(" c     丟幣測試（不指定枚數）");
  Serial.println(" e     結束丟幣測試，產生報告與建議的 DEBOUNCE_MS");
  Serial.println(" d50   即時計數的 DEBOUNCE 改為 50 ms");
  Serial.println(" p     逐筆顯示脈衝：開／關");
  Serial.println(" r     歸零");
  Serial.println(" ?     說明");
  Serial.println("----------------------------------------------------");
  Serial.println("調靈敏度的目標：空通道時 0%、不抖動；手指或硬幣經過時 ■ 出現一次。");
  Serial.println("顯示器：即時模式 4 位數＝1/5/10/50 元，「-」沒擋、「8」擋住；");
  Serial.println("        丟幣測試時顯示總金額。");
  Serial.println("====================================================");
}

void handleSerial() {
  if (!Serial.available()) return;
  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  cmd.toLowerCase();
  if (cmd.length() == 0) return;
  char k = cmd.charAt(0);
  int num = cmd.length() > 1 ? cmd.substring(1).toInt() : -1;

  if (k == 'v' || k == 'g') {
    mode = k;
    resetAll();
    if (k == 'v') Serial.printf("▶ 數值模式：每 %lu ms 一行，計數使用 DEBOUNCE %lu ms\n", VALUE_MS, liveDebounceMs);
    // 圖形模式不印中文，避免繪圖家看不懂
  } else if (k == 'l') {
    mode = 'l';
    resetAll();
    Serial.println("▶ 即時模式：每秒更新一次狀態。先確認 4 路空通道都是 0%。");
  } else if (k == 'c') {
    mode = 'c';
    expectedCoins = (num > 0) ? num : 0;
    resetAll();
    testStart = micros();
    Serial.println();
    Serial.print("▶ 丟幣測試開始");
    if (expectedCoins > 0) Serial.printf("：每一路請各丟 %d 枚（也可以只測其中幾路）", expectedCoins);
    Serial.println("。丟完輸入 e。");
    Serial.println("  建議開馬達讓硬幣照正常速度落下，結果最接近實際使用。");
    for (int i = 0; i < 4; i++) {
      if (chs[i].blocked) Serial.printf("  ⚠ %s 現在就是擋住狀態，請先調可變電阻！\n", COIN_NAME[i]);
    }
  } else if (k == 'e') {
    if (mode != 'c') {
      Serial.println("目前不在丟幣測試中，請先輸入 c 或 c10。");
    } else {
      processEdges();
      report();
      mode = 'e';   // 報告後保持畫面，不再更新狀態
    }
  } else if (k == 'd' && num >= 0) {
    liveDebounceMs = num;
    Serial.printf("即時計數的 DEBOUNCE 改為 %lu ms（輸入 r 歸零後重新計數）\n", liveDebounceMs);
  } else if (k == 'p') {
    printPulses = !printPulses;
    Serial.println(printPulses ? "逐筆顯示：開" : "逐筆顯示：關");
  } else if (k == 'r') {
    resetAll();
    Serial.println("已歸零");
  } else {
    printHelp();
  }
}

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(300);
  delay(300);
  pinMode(CLK_PIN, OUTPUT_OPEN_DRAIN);
  pinMode(DIO_PIN, OUTPUT_OPEN_DRAIN);
  lineHigh(CLK_PIN);
  lineHigh(DIO_PIN);
  for (int i = 0; i < 4; i++) {
    pinMode(SENSOR_PIN[i], INPUT_PULLUP);
    attachInterruptArg(SENSOR_PIN[i], onEdge, (void *)(intptr_t)i, CHANGE);
  }
  resetAll();
  printHelp();
  Serial.printf("▶ 數值模式：每 %lu ms 一行，計數使用 DEBOUNCE %lu ms（輸入 l 切到調校用的即時模式）\n",
                VALUE_MS, liveDebounceMs);
}

void loop() {
  handleSerial();
  processEdges();

  if ((mode == 'v' || mode == 'g') && millis() - lastValue >= VALUE_MS) {
    lastValue = millis();
    processEdges();
    if (mode == 'v') printValues(); else printPlot();
  }
  if (mode == 'l' && millis() - lastStatus >= STATUS_MS) {
    lastStatus = millis();
    printStatus();
  }
  // 顯示器最多每 50 ms 更新一次（中斷照常記錄，不會漏）
  if (dispDirty && millis() - lastDisp >= 50) {
    lastDisp = millis();
    dispDirty = false;
    updateDisplay();
  }
}
