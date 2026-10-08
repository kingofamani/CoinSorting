/*
 * 光耦簡易測試原型 — 1 路槽型光耦測試程式（ESP32）
 *
 * 用途：驗證「槽型光耦模組跨裝在滑坡上」能不能可靠地數硬幣。
 *   1. 開機約 1 秒自動判定：擋住時輸出 HIGH 還是 LOW（開機時槽裡不要放東西）
 *   2. 每一枚硬幣印出：第幾枚、遮光時間、和前一枚的間隔；設定幣別後估算滾動速度
 *      （不在丟幣測試時，擋住的當下先印「▼ 擋住（#N 開始）」，光束重新亮了才印「#N 遮光…」那一行）
 *   3. 丟幣測試：丟已知枚數後，同時用多種 DEBOUNCE 試算，告訴你哪個值最可靠
 *
 * 接線（只接一路光耦，3 條母母杜邦線）：
 *   光耦模組 OUT（有的寫 DO）→ 擴展板 G27 那一排的 S
 *   光耦模組 VCC             → 同一排的 V（擴展板黃色跳帽一定要設 3.3V，不可接 5V）
 *   光耦模組 GND             → 同一排的 G
 *   （可不接）TM1637 顯示器 CLK→G14、DIO→G13、VCC→V、GND→G：顯示目前枚數
 *
 * 開發板選「ESP32 Dev Module」，序列埠監控視窗設 115200。
 * 在輸入框打指令後按 Enter（換行設定選哪一種都可以）：
 *   c20   丟幣測試：接下來要丟 20 枚（數字可改；只打 c＝不指定枚數），丟完輸入 e
 *   e     結束丟幣測試，印出報告與建議值
 *   k5    設定目前測的幣別：k1、k5、k10、k50（k0 取消），用來估算速度
 *   b2.5  光束離軌道的高度（mm，預設 2.5），用來估算速度
 *   v     每 50 ms 印出目前電位：開／關（看閒置穩不穩、擋住會不會變）
 *   p     逐筆印出每一個原始脈衝：開／關（看抖動用）
 *   h     強制設定：擋住時輸出 HIGH
 *   l     強制設定：擋住時輸出 LOW
 *   a     重新自動判定擋住電位（槽裡先清空）
 *   g3    即時計數：光束連續亮 3 ms 以上，下一次擋住才算新的一枚（預設 3）
 *   d0    即時計數：從擋住開始算，幾 ms 內再擋住都算同一枚（前緣 DEBOUNCE，預設 0）
 *   r     歸零
 *   ?     說明與目前設定
 *
 * 用中斷記錄每一次訊號變化（精準到微秒）放進環形緩衝區，loop 再處理，很短的脈衝也不會漏。
 * 不需安裝任何函式庫。
 *
 * ESP32 Arduino core 2.0.x 與 3.x 都能編譯：
 *   - 只用兩版共通的寫法：attachInterrupt(digitalPinToInterrupt(腳), 函式, CHANGE)、
 *     portMUX／portENTER_CRITICAL、pinMode、digitalRead、micros、Serial.printf。
 *   - 已知差異 1：uint32_t 在 2.0.x 是 unsigned int、在 3.x 是 unsigned long，
 *     所以印數字時一律先轉成 (unsigned long) 再用 %lu，兩版都不會有型別警告。
 *   - 已知差異 2：3.x 的 pinMode／digitalRead 內部改用「腳位管理」，
 *     本程式改腳位模式前會先 detachInterrupt，改完再 attachInterrupt，兩版行為相同。
 *   - 已知差異 3：3.x 改了 LEDC、計時器（timerBegin）等 API；本程式都沒有用到。
 *   - 「檔案→偏好設定→編譯器警告」設成「更多」或「全部」時，ESP32 會把警告當成錯誤；
 *     本程式已避開常見的警告（有號／無號比較、printf 型別不符、未使用的變數）。
 */

// ===== 腳位與設定 =====
const uint8_t SENSOR_PIN = 27;            // 光耦 OUT → G27 的 S
const uint8_t CLK_PIN = 14;               // 顯示器 CLK（可不接）
const uint8_t DIO_PIN = 13;               // 顯示器 DIO（可不接）
const byte BRIGHTNESS = 4;                // 顯示器亮度 0~7
const unsigned long CAL_MS = 1000;        // 開機量閒置電位的時間
const unsigned long VALUE_MS = 50;        // v 模式的印出間隔
const uint32_t NOISE_US = 1000;           // 擋住不到 1 ms 視為雜訊／抖動
const uint32_t LONG_BLOCK_US = 3000000UL; // 光束連續擋住超過 3 秒就提醒（卡幣，或判定反了）
const uint32_t NONE_US = 0xFFFFFFFFUL;    // 「沒有這個值」
// 設計規格 R6：正式機兩枚相貼滾過時，光束高的亮區最壞約 5 ms（報告建議值的上限，沒設定幣別時用）
const double SPEC_TOUCH_BRIGHT_US = 5000.0;

// 硬幣：面額、直徑（mm）
const int   COIN_VAL[4] = {1, 5, 10, 50};
const float COIN_DIA[4] = {20.0f, 22.0f, 26.0f, 28.0f};

// 丟幣測試時同時試算的值（單位 µs）
// 方法一「前緣 DEBOUNCE」：從一枚開始擋住算起，這段時間內再擋住都算同一枚（舊程式的做法）
const uint32_t CAND_D_US[] = {0, 2000, 5000, 10000, 15000, 20000, 25000, 30000, 40000,
                              50000, 60000, 80000, 100000, 120000, 150000, 200000, 300000};
const int NCAND_D = sizeof(CAND_D_US) / sizeof(CAND_D_US[0]);
// 方法二「亮區重新上膛」：光束要連續亮超過這段時間，下一次擋住才算新的一枚
const uint32_t CAND_G_US[] = {0, 100, 200, 500, 1000, 2000, 3000, 5000, 8000,
                              10000, 15000, 20000, 30000, 50000};
const int NCAND_G = sizeof(CAND_G_US) / sizeof(CAND_G_US[0]);

// 數字 0~9 的七段碼（bit0=a … bit6=g）
const byte SEG_CODE[10] = {0x3F, 0x06, 0x5B, 0x4F, 0x66, 0x6D, 0x7D, 0x07, 0x7F, 0x6F};

// ===== 中斷：記錄每一次訊號變化（環形緩衝區）=====
struct EdgeRec { uint32_t t; uint8_t level; };
const int EBUF = 1024;
EdgeRec ebuf[EBUF];
volatile int eHead = 0;                   // 只有中斷會改
volatile int eTail = 0;                   // 只有 loop 會改
volatile uint32_t eOverflow = 0;          // 緩衝區滿了、漏記的筆數
portMUX_TYPE edgeMux = portMUX_INITIALIZER_UNLOCKED;

// ===== 丟幣測試的原始紀錄（每一個脈衝的開始時間與擋住長度）=====
const int MAXP = 1500;
uint32_t pStart[MAXP];
uint32_t pWidth[MAXP];
uint32_t tmp[MAXP];                       // 報告排序用
int pN = 0;
int pDropped = 0;

// 報告用：把脈衝分成一枚一枚之後的統計
struct SegStats {
  int coins;
  int multi;              // 產生多個脈衝的枚數
  int maxPulses;          // 一枚最多幾個脈衝
  int extra;              // 多出來的脈衝總數
  uint32_t maxInGap;      // 同一枚之內最長的亮縫（µs）
  uint32_t maxInSpan;     // 同一枚之內：第一個到最後一個脈衝「開始」的最長距離（µs）
  uint32_t minS2S;        // 兩枚「開始到開始」最短（µs）
  uint32_t minBright;     // 兩枚之間的亮區最短（µs）
};

// ===== 設定（可用指令改）=====
int blockedLevel = HIGH;                  // 擋住時的電位（開機自動判定）
uint32_t rearmUs = 3000;                  // 即時計數：亮區重新上膛（µs）
uint32_t debounceUs = 0;                  // 即時計數：前緣 DEBOUNCE（µs）
int coinIdx = -1;                         // 目前測的幣別（-1＝未設定）
double beamH = 2.5;                       // 光束離軌道（mm）
bool valueMode = false;
bool printPulses = false;
bool dispOk = false;

// ===== 狀態 =====
bool testing = false;
int expectN = 0;
unsigned long testStartMs = 0;

bool blocked = false;                     // 光束目前是否被擋住
bool skipPulse = false;                   // 歸零時光束已經被擋住：這一段不算
uint32_t pulseStartUs = 0;
bool longBlockWarned = false;             // 這一段擋住已經提醒過「擋太久」
bool haveLastEnd = false;
uint32_t lastEndUs = 0;

bool coinOpen = false;                    // 目前這一枚還沒結束
long coinNo = 0;
uint32_t coinStartUs = 0;
uint32_t coinEndUs = 0;
int coinPulses = 0;
unsigned long coinStartMs = 0;

bool havePrevCoin = false;
uint32_t prevStartUs = 0;
uint32_t prevEndUs = 0;
unsigned long prevStartMs = 0;

long liveCount = 0;

bool winSeen = false;                     // v 模式：這 50 ms 內擋過
uint32_t winEdges = 0;                    // v 模式：這 50 ms 內的訊號變化次數
uint32_t dupTotal = 0;                    // 極短突波（中斷讀到和目前一樣的電位）
uint32_t ovfTotal = 0;
uint32_t ovfPending = 0;
unsigned long lastOvfMsgMs = 0;
unsigned long lastValueMs = 0;
unsigned long lastDispMs = 0;
bool dispDirty = true;

char cmdBuf[24];
int cmdLen = 0;
unsigned long cmdLastMs = 0;

// ===== 中斷處理 =====
void IRAM_ATTR onEdge() {
  uint32_t t = micros();
  uint8_t lv = (uint8_t)digitalRead(SENSOR_PIN);
  portENTER_CRITICAL_ISR(&edgeMux);
  int n = (eHead + 1) % EBUF;
  if (n != eTail) {
    ebuf[eHead].t = t;
    ebuf[eHead].level = lv;
    eHead = n;
  } else {
    eOverflow = eOverflow + 1;
  }
  portEXIT_CRITICAL_ISR(&edgeMux);
}

bool popEdge(uint32_t &t, uint8_t &lv) {
  bool ok = false;
  portENTER_CRITICAL(&edgeMux);
  if (eTail != eHead) {
    t = ebuf[eTail].t;
    lv = ebuf[eTail].level;
    eTail = (eTail + 1) % EBUF;
    ok = true;
  }
  portEXIT_CRITICAL(&edgeMux);
  return ok;
}

// 清空緩衝區，回傳清掉幾筆（含漏記）
uint32_t takeEdgeCount() {
  uint32_t n;
  portENTER_CRITICAL(&edgeMux);
  int h = eHead;
  int tl = eTail;
  n = (uint32_t)((h - tl + EBUF) % EBUF) + eOverflow;
  eTail = h;
  eOverflow = 0;
  portEXIT_CRITICAL(&edgeMux);
  return n;
}

uint32_t takeOverflow() {
  uint32_t n;
  portENTER_CRITICAL(&edgeMux);
  n = eOverflow;
  eOverflow = 0;
  portEXIT_CRITICAL(&edgeMux);
  return n;
}

// ===== TM1637（開漏輸出；沒接顯示器也沒關係）=====
// 腳位設成「開漏輸出＋內建上拉」：寫 LOW＝拉低、寫 HIGH＝放開；
// 內建上拉是為了沒接顯示器時讀得到「沒回應」，有接時不影響。
void lineLow(byte p)  { digitalWrite(p, LOW); }
void lineHigh(byte p) { digitalWrite(p, HIGH); }
void bitDelay()       { delayMicroseconds(100); }

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

bool tmWrite(byte b) {                 // 回傳 true＝顯示器有回應
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
  tmStart(); ok &= tmWrite(0x40); tmStop();              // 自動遞增位址寫入
  tmStart(); ok &= tmWrite(0xC0);                         // 從最左邊那位開始
  for (int i = 0; i < 4; i++) ok &= tmWrite(seg[i]);
  tmStop();
  tmStart(); ok &= tmWrite(0x88 | (BRIGHTNESS & 7)); tmStop();   // 開顯示＋亮度
  return ok;
}

// 顯示數字（前面不補 0，最多 9999）
bool showNumber(long n) {
  byte seg[4] = {0, 0, 0, 0};
  if (n < 0) n = 0;
  if (n > 9999) n = 9999;
  for (int i = 3; i >= 0; i--) {
    seg[i] = SEG_CODE[n % 10];
    n /= 10;
    if (n == 0) break;
  }
  return tmShow(seg);
}

// ===== 小工具 =====
const char *levelName(int lv) { return (lv == HIGH) ? "HIGH" : "LOW"; }

// 硬幣立著滾、光束離軌道 h：光束切過硬幣的長度（弦長）＝ 2√(2rh − h²)
double chordMm(int idx, double h) {
  if (idx < 0 || idx > 3) return 0;
  double r = COIN_DIA[idx] / 2.0;
  double q = 2.0 * r * h - h * h;
  if (h <= 0 || q <= 0) return 0;
  return 2.0 * sqrt(q);
}

double chordNow() { return chordMm(coinIdx, beamH); }

void printSettings() {
  Serial.printf("目前設定：擋住＝%s｜即時計數：亮區 %.1f ms、前緣 %lu ms｜",
                levelName(blockedLevel), rearmUs / 1000.0, (unsigned long)(debounceUs / 1000UL));
  if (coinIdx >= 0) Serial.printf("幣別 %d 元｜", COIN_VAL[coinIdx]);
  else Serial.print("幣別 未設定｜");
  Serial.printf("光束離軌道 %.1f mm", beamH);
  double c = chordNow();
  if (c > 0) Serial.printf("（弦長 %.2f mm）", c);
  Serial.printf("｜顯示器 %s\n", dispOk ? "有回應" : "沒偵測到");
}

// ===== 歸零 =====
void resetState() {
  takeEdgeCount();                        // 先清空緩衝區
  int lv = digitalRead(SENSOR_PIN);
  blocked = (lv == blockedLevel);
  skipPulse = blocked;
  pulseStartUs = micros();
  longBlockWarned = false;
  haveLastEnd = false;
  coinOpen = false;
  coinNo = 0;
  coinPulses = 0;
  havePrevCoin = false;
  liveCount = 0;
  winSeen = false;
  winEdges = 0;
  dupTotal = 0;
  ovfTotal = 0;
  ovfPending = 0;
  pN = 0;
  pDropped = 0;
  testStartMs = millis();
  dispDirty = true;
  if (blocked) {
    Serial.println("  ⚠ 現在光束是擋住的（這一段不算）：槽裡有東西嗎？或擋住電位設反了（輸入 h 或 l）");
  }
}

// ===== 開機自動判定擋住電位 =====
void autoDetectLevel() {
  Serial.println();
  Serial.println("▶ 自動判定擋住電位（約 1 秒）：槽裡請不要放任何東西……");

  // 1) 空接檢查：開內建下拉、再開內建上拉，讀到的值如果跟著變，表示 G27 沒接到東西
  detachInterrupt(digitalPinToInterrupt(SENSOR_PIN));
  pinMode(SENSOR_PIN, INPUT_PULLDOWN);
  delay(5);
  int withDown = digitalRead(SENSOR_PIN);
  pinMode(SENSOR_PIN, INPUT_PULLUP);
  delay(5);
  int withUp = digitalRead(SENSOR_PIN);
  attachInterrupt(digitalPinToInterrupt(SENSOR_PIN), onEdge, CHANGE);
  takeEdgeCount();

  // 2) 取樣 1 秒：每 1 ms 讀一次，另外用中斷數變化次數
  unsigned long t0 = millis();
  long nHigh = 0;
  long nAll = 0;
  unsigned long changes = 0;
  while (millis() - t0 < CAL_MS) {
    if (digitalRead(SENSOR_PIN) == HIGH) nHigh++;
    nAll++;
    changes += takeEdgeCount();
    delay(1);
  }
  changes += takeEdgeCount();
  if (nAll < 1) nAll = 1;

  int idle = (nHigh * 2 >= nAll) ? HIGH : LOW;
  blockedLevel = (idle == HIGH) ? LOW : HIGH;
  int pctHigh = (int)(nHigh * 100 / nAll);
  Serial.printf("  閒置（沒擋）電位：%s（1 秒內 HIGH 佔 %d%%、訊號變化 %lu 次）\n",
                levelName(idle), pctHigh, changes);
  Serial.printf("  → 判定：擋住時輸出 %s\n", levelName(blockedLevel));

  if (withDown == LOW && withUp == HIGH) {
    Serial.println("  ⚠ G27 好像沒接到東西：開內建下拉讀到 0、開內建上拉讀到 1（腳位跟著內建電阻走）。");
    Serial.println("    檢查 OUT→G27 的 S、VCC→V、GND→G 有沒有插好，接好後輸入 a 重新判定。");
    Serial.println("    （若模組本身沒有上拉電阻，也會這樣；程式有開內建上拉，仍然可以用）");
  }
  if (changes > 0 || (nHigh != 0 && nHigh != nAll)) {
    Serial.printf("  ⚠ 閒置時訊號不穩：1 秒內變化 %lu 次。可能是：槽裡有東西或手在晃、\n", changes);
    Serial.println("    杜邦線接觸不良、VCC 沒接或黃色跳帽不在 3.3V、模組壞了、強光直射。");
    Serial.println("    排除後輸入 a 重新判定；也可以用 h／l 直接指定。");
  }
  Serial.println("  如果剛才這 1 秒槽裡不是空的，判定一定是反的 → 清空後輸入 a。");
  Serial.println("  確認方法：用紙片擋住光束約 1 秒再拿開。");
  Serial.println("    正確：擋住的當下印「▼ 擋住（#1 開始）」，拿開後才印「#1 遮光 約 1000 ms」（遮光≈你擋住的時間）。");
  Serial.println("    判定反了：拿開時才印「▼ 擋住」，或擋住的當下就印出「#1 遮光…」→ 輸入 h 或 l 改過來。");
  Serial.println("  也可以輸入 v：槽空著要顯示「· 沒擋」，擋住要顯示「■ 擋住」。");
}

// ===== 每一枚硬幣 =====
// 即時規則：前一個脈衝結束後「亮了 ≥ 亮區門檻」而且「離這一枚開始 > 前緣 DEBOUNCE」，
// 下一次擋住才算新的一枚；否則算同一枚的抖動。報告的 splitCoins() 用完全相同的規則。
void finalizeCoin() {
  if (!coinOpen) return;
  coinOpen = false;
  uint32_t span = coinEndUs - coinStartUs;
  Serial.printf("  #%ld", coinNo);
  if (testing && expectN > 0) Serial.printf("/%d", expectN);
  Serial.printf("  遮光 %6.1f ms", span / 1000.0);
  if (havePrevCoin) {
    unsigned long dMs = coinStartMs - prevStartMs;
    if (dMs > 60000UL) {
      Serial.printf("  間隔 %.1f 秒", dMs / 1000.0);   // 超過 1 分鐘改用 millis（micros 約 71 分鐘歸零）
    } else {
      Serial.printf("  間隔 %7.1f ms（亮 %7.1f ms）",
                    (coinStartUs - prevStartUs) / 1000.0, (coinStartUs - prevEndUs) / 1000.0);
    }
  } else {
    Serial.print("  （第一枚）");
  }
  double c = chordNow();
  if (c > 0 && span > 0) Serial.printf("  速度≈%.2f m/s", c / (span / 1000.0));
  if (coinPulses > 1) Serial.printf("  ⚠抖動：%d 個脈衝", coinPulses);
  if (span < NOISE_US) Serial.print("  ⚠不到 1 ms，可能是雜訊");
  Serial.println();
  if (testing && expectN > 0) {
    if (coinNo == expectN) Serial.printf("  ✔ 已經 %d 枚：丟完請輸入 e\n", expectN);
    if (coinNo == expectN + 1) Serial.println("  ⚠ 已經超過預期枚數（抖動被多算，或多丟了）");
  }
  havePrevCoin = true;
  prevStartUs = coinStartUs;
  prevEndUs = coinEndUs;
  prevStartMs = coinStartMs;
}

void onPulseStart(uint32_t t) {
  if (coinOpen) {
    bool isNew = ((t - coinEndUs) >= rearmUs) && ((t - coinStartUs) > debounceUs);
    if (!isNew) {
      coinPulses++;
      return;
    }
    finalizeCoin();
  }
  coinOpen = true;
  coinStartUs = t;
  coinEndUs = t;
  coinPulses = 1;
  coinStartMs = millis();
  liveCount++;
  coinNo = liveCount;
  dispDirty = true;
  // 不在丟幣測試時，擋住的當下先回應一行（邊緣時間在中斷裡記好了，多印這一行不影響量測）；
  // 丟幣測試中不印，避免洗版。「#N 遮光…」要等光束重新亮了（亮區門檻之後）才印。
  if (!testing) Serial.printf("  ▼ 擋住（#%ld 開始）\n", coinNo);
}

void onPulseEnd(uint32_t s, uint32_t e) {
  uint32_t w = e - s;
  if (printPulses) {
    Serial.printf("    · 脈衝：擋 %.3f ms", w / 1000.0);
    if (haveLastEnd) Serial.printf("，前面亮 %.3f ms", (s - lastEndUs) / 1000.0);
    Serial.println();
  }
  if (testing) {
    if (pN < MAXP) {
      pStart[pN] = s;
      pWidth[pN] = w;
      pN++;
    } else {
      pDropped++;
    }
  }
  haveLastEnd = true;
  lastEndUs = e;
  if (coinOpen) coinEndUs = e;
}

void handleEdge(uint32_t t, uint8_t lv) {
  winEdges++;
  bool isBlk = ((int)lv == blockedLevel);
  if (isBlk == blocked) {        // 和目前狀態一樣：中間有一段短到讀不到的突波
    dupTotal++;
    return;
  }
  blocked = isBlk;
  if (isBlk) {
    pulseStartUs = t;
    winSeen = true;
    if (!skipPulse) onPulseStart(t);
  } else if (skipPulse) {
    skipPulse = false;
    haveLastEnd = true;
    lastEndUs = t;
  } else {
    onPulseEnd(pulseStartUs, t);
  }
}

// 處理緩衝區；回傳 true＝已經清空（一次最多處理 EBUF 筆，避免嚴重抖動時卡在這裡）
bool processEdges() {
  uint32_t t = 0;
  uint8_t lv = 0;
  for (int i = 0; i < EBUF; i++) {
    if (!popEdge(t, lv)) return true;
    handleEdge(t, lv);
  }
  return false;
}

// ===== v 模式：每 50 ms 一行 =====
void printValue() {
  int lv = digitalRead(SENSOR_PIN);
  bool isBlk = (lv == blockedLevel);
  Serial.printf("%9.2f s  G27=%d  %s%s  計數 %ld", millis() / 1000.0, lv,
                isBlk ? "■ 擋住" : "· 沒擋", (!isBlk && winSeen) ? " *" : "  ", liveCount);
  if (winEdges > 0) Serial.printf("  變化 %lu 次", (unsigned long)winEdges);
  Serial.println();
  winSeen = false;
  winEdges = 0;
}

// ===== 丟幣測試報告 =====
int cmpU32(const void *a, const void *b) {
  uint32_t x = *(const uint32_t *)a;
  uint32_t y = *(const uint32_t *)b;
  return (x > y) - (x < y);
}

// 用「亮區 rearm、前緣 deb」的規則把紀錄的脈衝分成一枚一枚（和即時計數同一個規則）。
// st 不是 NULL 時填統計；spans 不是 NULL 時填每一枚的遮光時間（第一個脈衝開始到最後一個結束）。
int splitCoins(uint32_t rearm, uint32_t deb, SegStats *st, uint32_t *spans) {
  if (st != NULL) {
    st->coins = 0;
    st->multi = 0;
    st->maxPulses = 0;
    st->extra = 0;
    st->maxInGap = 0;
    st->maxInSpan = 0;
    st->minS2S = NONE_US;
    st->minBright = NONE_US;
  }
  if (pN <= 0) return 0;
  int coins = 1;
  int pulses = 1;
  uint32_t cStart = pStart[0];
  uint32_t lastStart = pStart[0];
  uint32_t lastEnd = pStart[0] + pWidth[0];
  uint32_t inGap = 0;
  for (int k = 1; k <= pN; k++) {
    bool more = (k < pN);
    uint32_t gap = 0;
    bool isNew = true;                    // k == pN：收尾最後一枚
    if (more) {
      gap = pStart[k] - lastEnd;
      isNew = (gap >= rearm) && ((pStart[k] - cStart) > deb);
    }
    if (!isNew) {
      pulses++;
      if (gap > inGap) inGap = gap;
    } else {
      if (spans != NULL) spans[coins - 1] = lastEnd - cStart;
      if (st != NULL) {
        if (pulses > 1) {
          st->multi++;
          st->extra += pulses - 1;
        }
        if (pulses > st->maxPulses) st->maxPulses = pulses;
        if (inGap > st->maxInGap) st->maxInGap = inGap;
        if (lastStart - cStart > st->maxInSpan) st->maxInSpan = lastStart - cStart;
        if (more) {
          if (pStart[k] - cStart < st->minS2S) st->minS2S = pStart[k] - cStart;
          if (gap < st->minBright) st->minBright = gap;
        }
      }
      if (more) {
        coins++;
        pulses = 1;
        inGap = 0;
        cStart = pStart[k];
      }
    }
    if (more) {
      lastStart = pStart[k];
      lastEnd = pStart[k] + pWidth[k];
    }
  }
  if (st != NULL) st->coins = coins;
  return coins;
}

// 找「計數＝target」最長的一段；找到回傳 true
bool bestRun(const int *cnt, int n, int target, int *lo, int *hi) {
  int bLo = -1, bHi = -1, runLo = -1;
  for (int j = 0; j <= n; j++) {
    bool ok = (j < n) && (cnt[j] == target);
    if (ok && runLo < 0) runLo = j;
    if (!ok && runLo >= 0) {
      if (bLo < 0 || (j - 1 - runLo) > (bHi - bLo)) {
        bLo = runLo;
        bHi = j - 1;
      }
      runLo = -1;
    }
  }
  *lo = bLo;
  *hi = bHi;
  return bLo >= 0;
}

// 沒指定枚數時：從 from 開始，計數不變的最長一段，回傳那個計數
int stableCount(const int *cnt, int n, int from) {
  int best = 0, bestLen = 0, runLo = from;
  for (int j = from + 1; j <= n; j++) {
    if (j == n || cnt[j] != cnt[runLo]) {
      int len = j - runLo;
      if (cnt[runLo] > 0 && len > bestLen) {
        bestLen = len;
        best = cnt[runLo];
      }
      runLo = j;
    }
  }
  return best;
}

// 在 cand[lo..hi]（都已經算對）裡挑建議值：小於 hiUs、倍數上最接近 loUs 與 hiUs 中間的值。
// hiUs <= 0 表示沒有上限資訊 → 取這一段的中間；都不合格回傳 -1。
int pickRec(const uint32_t *cand, int lo, int hi, double loUs, double hiUs) {
  if (hiUs <= 0) {
    int j = (lo + hi) / 2;
    if (cand[j] == 0 && j < hi) j++;      // 不建議 0
    return j;
  }
  double mid = sqrt(loUs * hiUs);
  int best = -1;
  double bestErr = 0;
  for (int j = lo; j <= hi; j++) {
    double c = (double)cand[j];
    if (c <= 0 || c >= hiUs) continue;
    double err = fabs(log(c / mid));
    if (best < 0 || err < bestErr) {
      best = j;
      bestErr = err;
    }
  }
  return best;
}

void printReport() {
  unsigned long durMs = millis() - testStartMs;
  Serial.println();
  Serial.println("================ 丟幣測試報告 ================");
  Serial.printf("測試 %.1f 秒；", durMs / 1000.0);
  if (expectN > 0) Serial.printf("預期 %d 枚", expectN);
  else Serial.print("未指定枚數");
  if (coinIdx >= 0) Serial.printf("；%d 元（直徑 %.0f mm）", COIN_VAL[coinIdx], (double)COIN_DIA[coinIdx]);
  Serial.printf("；光束離軌道 %.1f mm；擋住＝%s\n", beamH, levelName(blockedLevel));

  int shortN = 0;
  for (int k = 0; k < pN; k++) {
    if (pWidth[k] < NOISE_US) shortN++;
  }
  Serial.printf("收到 %d 個脈衝（短於 1 ms 的 %d 個）；極短突波 %lu 次；漏記 %lu 筆\n",
                pN, shortN, (unsigned long)dupTotal, (unsigned long)ovfTotal);
  if (pDropped > 0) Serial.printf("⚠ 另有 %d 個脈衝超過紀錄上限 %d 個，沒有算進報告\n", pDropped, MAXP);
  if (durMs > 4200000UL) Serial.println("⚠ 測試超過 70 分鐘：micros() 約 71.6 分鐘歸零一次，間隔可能算錯，請分次測");
  if (blocked) Serial.println("⚠ 結束時光束還被擋住，最後這一段沒有算進報告");
  if (pN == 0) {
    Serial.println("沒有收到任何脈衝：檢查 OUT→G27、VCC→V、GND→G、黃色跳帽 3.3V；");
    Serial.println("再輸入 v，用紙片擋光束，看 G27 的 0/1 會不會變。");
    Serial.println("==============================================");
    return;
  }

  // ---- 兩種方法、各種值的試算 ----
  int cntD[NCAND_D];
  int cntG[NCAND_G];
  for (int j = 0; j < NCAND_D; j++) cntD[j] = splitCoins(0, CAND_D_US[j], NULL, NULL);
  for (int j = 0; j < NCAND_G; j++) cntG[j] = splitCoins(CAND_G_US[j], 0, NULL, NULL);
  int liveN = splitCoins(rearmUs, debounceUs, NULL, NULL);

  int target = expectN;
  if (target <= 0) {
    target = stableCount(cntG, NCAND_G, 1);
    Serial.printf("（未指定枚數：以最穩定的結果 %d 枚當作正確答案）\n", target);
  }

  // ---- 精確臨界值：把最長的 target−1 段亮區當作「兩枚之間」，其餘是同一枚的抖動 ----
  bool cut = false;
  bool hasJit = false;
  uint32_t gapX = 0;          // 同一枚之內最長的亮縫
  uint32_t gapY = NONE_US;    // 兩枚之間最短的亮區
  if (target >= 1 && pN >= target) {
    int m = pN - 1;
    for (int k = 1; k < pN; k++) tmp[k - 1] = pStart[k] - (pStart[k - 1] + pWidth[k - 1]);
    if (m > 0) qsort(tmp, m, sizeof(uint32_t), cmpU32);
    if (target >= 2) gapY = tmp[m - (target - 1)];
    if (m - target >= 0) {
      gapX = tmp[m - target];
      hasJit = true;
    }
    cut = (!hasJit) || (gapX < gapY);
  }

  // ---- 每一枚的統計 ----
  SegStats st;
  int nC;
  if (cut) nC = splitCoins((target >= 2) ? gapY : NONE_US, 0, &st, tmp);
  else nC = splitCoins(rearmUs, debounceUs, &st, tmp);
  qsort(tmp, nC, sizeof(uint32_t), cmpU32);

  Serial.println();
  Serial.printf("── 每一枚（%s，共 %d 枚）\n", cut ? "依預期枚數分枚" : "依目前的即時規則分枚", nC);
  Serial.printf("   遮光時間：最短 %.1f ms、中位數 %.1f ms、最長 %.1f ms\n",
                tmp[0] / 1000.0, tmp[nC / 2] / 1000.0, tmp[nC - 1] / 1000.0);
  double chord = chordNow();
  double vFast = 0;
  if (chord > 0 && tmp[0] > 0) {
    vFast = chord / (tmp[0] / 1000.0);
    double vMid = chord / (tmp[nC / 2] / 1000.0);
    double vSlow = chord / (tmp[nC - 1] / 1000.0);
    Serial.printf("   估計速度（弦長 %.2f mm ÷ 遮光時間）：最慢 %.2f、中位數 %.2f、最快 %.2f m/s\n",
                  chord, vSlow, vMid, vFast);
  } else if (chord <= 0) {
    Serial.println("   （輸入 k1／k5／k10／k50 設定幣別，就能估算滾動速度）");
  }
  if (nC >= 2) {
    Serial.printf("   兩枚之間：開始到開始最短 %.1f ms；亮區最短 %.1f ms\n",
                  st.minS2S / 1000.0, st.minBright / 1000.0);
  }

  Serial.println("── 抖動（一枚產生多個脈衝）");
  if (st.multi == 0) {
    Serial.println("   沒有：每一枚都只有一個乾淨的脈衝 ✔");
  } else {
    Serial.printf("   %d 枚裡有 %d 枚產生多個脈衝（一枚最多 %d 個，總共多出 %d 個）\n",
                  nC, st.multi, st.maxPulses, st.extra);
    Serial.printf("   同一枚之內：最長的亮縫 %.3f ms；第一個到最後一個脈衝開始最多差 %.1f ms\n",
                  st.maxInGap / 1000.0, st.maxInSpan / 1000.0);
  }
  if (dupTotal > 0 || ovfTotal > 0) {
    Serial.printf("   另有極短突波 %lu 次、漏記 %lu 筆 → 訊號邊緣在抖，檢查接線與 3.3V\n",
                  (unsigned long)dupTotal, (unsigned long)ovfTotal);
  }

  // ---- 正式機兩枚相貼的估計（有設定幣別才算）----
  double touchBrightUs = 0, touchS2SUs = 0;
  if (vFast > 0) {
    double dia = COIN_DIA[coinIdx];
    touchBrightUs = (dia - chord) / vFast * 1000.0;
    touchS2SUs = dia / vFast * 1000.0;
    Serial.printf("── 估計：兩枚 %d 元相貼、以本次最快 %.2f m/s 滾過\n", COIN_VAL[coinIdx], vFast);
    Serial.printf("   亮區約 %.1f ms、開始到開始約 %.1f ms（未扣光窗寬，實際亮區會再短一點）\n",
                  touchBrightUs / 1000.0, touchS2SUs / 1000.0);
  }

  // ---- 方法一：前緣 DEBOUNCE ----
  Serial.println();
  Serial.println("── 方法一：前緣 DEBOUNCE（從擋住開始算，這段時間內再擋住都算同一枚）");
  Serial.printf("   各值算出的枚數（ms→枚，✔＝等於 %d 枚）：", target);
  for (int j = 0; j < NCAND_D; j++) {
    if (j % 6 == 0) Serial.print("\n    ");
    Serial.printf("%4lu→%-3d%s", (unsigned long)(CAND_D_US[j] / 1000UL), cntD[j], (cntD[j] == target) ? "✔ " : "  ");
  }
  Serial.println();
  double dLoLim = 1000.0, dHiLim = 0;      // µs；dHiLim 0＝沒有上限資訊
  if (cut) {
    if (st.maxInSpan > dLoLim) dLoLim = st.maxInSpan;
    if (target >= 2) dHiLim = st.minS2S;
    Serial.printf("   精確範圍：至少 %.1f ms（同一枚最後一個脈衝）", st.maxInSpan / 1000.0);
    if (target >= 2) Serial.printf("、小於 %.1f ms（兩枚開始到開始最短）", st.minS2S / 1000.0);
    Serial.println();
  }
  if (touchS2SUs > 0 && (dHiLim <= 0 || touchS2SUs < dHiLim)) dHiLim = touchS2SUs;
  int dLo = -1, dHi = -1, dRec = -1;
  bool dOk = bestRun(cntD, NCAND_D, target, &dLo, &dHi);
  if (dOk) {
    dRec = pickRec(CAND_D_US, dLo, dHi, dLoLim, dHiLim);
    Serial.printf("   ✔ %lu～%lu ms 都是 %d 枚", (unsigned long)(CAND_D_US[dLo] / 1000UL),
                  (unsigned long)(CAND_D_US[dHi] / 1000UL), target);
    if (dRec >= 0) Serial.printf("，建議 %lu ms", (unsigned long)(CAND_D_US[dRec] / 1000UL));
    Serial.println();
    if (dRec < 0) Serial.println("   ⚠ 可用的值都超過相貼兩枚的估計：正式機可能把相貼的兩枚算成一枚");
    else if (dHiLim > 0 && dHiLim < 3.0 * dLoLim) Serial.println("   ⚠ 可用範圍很窄（上下限不到 3 倍），實際使用可能不穩");
  } else {
    Serial.printf("   ✘ 沒有任何 DEBOUNCE 能剛好算出 %d 枚\n", target);
  }

  // ---- 方法二：亮區重新上膛 ----
  Serial.println();
  Serial.println("── 方法二：亮區重新上膛（光束要連續亮超過這段時間，下一次擋住才算新的一枚）");
  Serial.printf("   各值算出的枚數（ms→枚，✔＝等於 %d 枚）：", target);
  for (int j = 0; j < NCAND_G; j++) {
    if (j % 6 == 0) Serial.print("\n    ");
    Serial.printf("%5.1f→%-3d%s", CAND_G_US[j] / 1000.0, cntG[j], (cntG[j] == target) ? "✔ " : "  ");
  }
  Serial.println();
  double gLoLim = 500.0, gHiLim = 0;       // µs；下限至少 0.5 ms
  if (cut) {
    if (hasJit && gapX > gLoLim) gLoLim = gapX;
    if (hasJit) Serial.printf("   精確範圍：大於 %.3f ms（同一枚之內最長的亮縫）", gapX / 1000.0);
    else Serial.print("   精確範圍：沒有抖動亮縫");
    if (target >= 2) {
      gHiLim = gapY;
      Serial.printf("、不超過 %.1f ms（兩枚之間最短的亮區）", gapY / 1000.0);
    }
    Serial.println();
  }
  // 上限再考慮正式機兩枚相貼：有設定幣別用本次速度估計，沒有就用設計規格 R6 的最壞情形
  double touchCapUs = (touchBrightUs > 0) ? touchBrightUs : SPEC_TOUCH_BRIGHT_US;
  if (gHiLim <= 0 || touchCapUs < gHiLim) gHiLim = touchCapUs;
  if (touchBrightUs <= 0) {
    Serial.printf("   （沒設定幣別：建議值以設計規格 R6「相貼兩枚亮區最短約 %.0f ms」為上限）\n",
                  SPEC_TOUCH_BRIGHT_US / 1000.0);
  }
  int gLo = -1, gHi = -1, gRec = -1;
  bool gOk = bestRun(cntG, NCAND_G, target, &gLo, &gHi);
  if (gOk) {
    gRec = pickRec(CAND_G_US, gLo, gHi, gLoLim, gHiLim);
    Serial.printf("   ✔ %.1f～%.1f ms 都是 %d 枚", CAND_G_US[gLo] / 1000.0, CAND_G_US[gHi] / 1000.0, target);
    if (gRec >= 0) Serial.printf("，建議 %.1f ms", CAND_G_US[gRec] / 1000.0);
    Serial.println();
    if (gRec < 0) Serial.println("   ⚠ 可用的值都超過相貼兩枚的估計：正式機可能把相貼的兩枚算成一枚");
    else if (gHiLim < 3.0 * gLoLim) Serial.println("   ⚠ 可用範圍很窄（上下限不到 3 倍），實際使用可能不穩");
  } else {
    Serial.printf("   ✘ 沒有任何亮區門檻能剛好算出 %d 枚\n", target);
  }

  // ---- 結論 ----
  Serial.println();
  Serial.println("★ 結論");
  Serial.printf("   即時計數（亮區 %.1f ms、前緣 %lu ms）這次算出 %d 枚 %s\n",
                rearmUs / 1000.0, (unsigned long)(debounceUs / 1000UL), liveN, (liveN == target) ? "✔" : "✘");
  if (expectN <= 0) Serial.printf("   （沒有指定枚數，上面以 %d 枚當作正確；請自己核對實際丟了幾枚）\n", target);
  if (pN < target) {
    Serial.printf("   ✘ 只收到 %d 個脈衝，比 %d 枚少：有硬幣沒擋到光束。\n", pN, target);
    Serial.println("     → 檢查光束高度、硬幣有沒有貼著軌道滾、模組有沒有裝正、是不是兩枚疊在一起通過。");
  } else if (gRec >= 0) {
    Serial.printf("   ✔ %d 枚都有擋到光束，而且分得出來。\n", target);
    Serial.printf("   ★ 正式程式建議用方法二：光束連續亮 %.1f ms 以上，下一次擋住才算新的一枚\n",
                  CAND_G_US[gRec] / 1000.0);
    Serial.println("     （方法一遇到尾端抖動時，下限會變成整段遮光時間；慢的硬幣遮得久，速度差大時容易找不到安全值）");
    if (dRec >= 0) Serial.printf("   若沿用前緣 DEBOUNCE：建議 %lu ms\n", (unsigned long)(CAND_D_US[dRec] / 1000UL));
    for (int j = 0; j < NCAND_D; j++) {
      if (CAND_D_US[j] == 30000UL && cntD[j] != target) {
        Serial.printf("   ⚠ 原訂的前緣 30 ms 這次會算成 %d 枚\n", cntD[j]);
      }
    }
    rearmUs = CAND_G_US[gRec];
    debounceUs = 0;
    Serial.printf("   本工具的即時計數已改用「亮區 %.1f ms、前緣 0 ms」，可以直接再丟幣驗證。\n", rearmUs / 1000.0);
  } else {
    Serial.printf("   ✘ 找不到能穩定算出 %d 枚的設定。\n", target);
    if (!gOk) {
      Serial.println("     → 抖動的亮縫和兩枚之間的亮區混在一起：先讓硬幣一枚一枚隔開丟；");
      Serial.println("       輸入 v 看閒置穩不穩、p 看每一個脈衝。");
    } else {
      Serial.println("     → 抖動的亮縫比相貼兩枚的亮區還長：正式機可能把相貼的兩枚算成一枚。");
    }
  }
  Serial.println("   （參考：設計規格 R6 估計正式機兩枚相貼時亮區約 5～27 ms，建議 3～5 ms 重新上膛）");
  Serial.println("==============================================");
  Serial.println("輸入 c20 再測一次；r 歸零；? 說明。");
}

// ===== 指令 =====
void printHelp() {
  Serial.println();
  Serial.println("============ 光耦測試（ESP32，1 路，OUT→G27）============");
  Serial.println(" c20   丟幣測試：接下來丟 20 枚（數字可改；只打 c＝不指定），丟完輸入 e");
  Serial.println(" e     結束丟幣測試，印出報告與建議的 DEBOUNCE");
  Serial.println(" k5    設定幣別 k1／k5／k10／k50（k0 取消），用來估算速度");
  Serial.println(" b2.5  光束離軌道的高度（mm），用來估算速度");
  Serial.println(" v     每 50 ms 印出目前電位：開／關");
  Serial.println(" p     逐筆印出每一個原始脈衝：開／關（看抖動）");
  Serial.println(" h／l  強制設定：擋住時輸出 HIGH／LOW");
  Serial.println(" a     重新自動判定擋住電位（槽裡先清空）");
  Serial.println(" g3    即時計數：光束連續亮 3 ms 以上，下一次擋住才算新的一枚");
  Serial.println(" d0    即時計數：從擋住開始算，幾 ms 內再擋住都算同一枚（前緣 DEBOUNCE）");
  Serial.println(" r     歸零");
  Serial.println(" ?     說明");
  Serial.println("---------------------------------------------------------");
  Serial.println("每一枚印出：#第幾枚、遮光時間、和前一枚開始的間隔（括號＝中間亮了多久）；");
  Serial.println("設定幣別後多印估計速度（弦長 ÷ 遮光時間）。顯示器（可不接）顯示枚數。");
  Serial.println("不在丟幣測試時，擋住的當下先印「▼ 擋住（#N 開始）」，光束重新亮了才印「#N 遮光…」。");
  Serial.println("每次 e 印完報告後，即時計數會自動改用建議的亮區值；要每輪設定一樣，就在 c 之前輸入 g3 d0。");
  printSettings();
  Serial.println("=========================================================");
}

void runCommand(const char *s) {
  while (*s == ' ' || *s == '\t') s++;
  if (*s == '\0') return;
  char k = *s;
  if (k >= 'A' && k <= 'Z') k = (char)(k - 'A' + 'a');
  const char *arg = s + 1;
  bool hasNum = false;
  bool cleanArg = true;                   // 字母後面只能是數字（避免打 help 被當成 h）
  for (const char *q = arg; *q != '\0'; q++) {
    char ch = *q;
    if (ch >= '0' && ch <= '9') hasNum = true;
    else if (ch != '.' && ch != '-' && ch != '+' && ch != ' ' && ch != '\t') cleanArg = false;
  }
  if (!cleanArg) {
    printHelp();
    return;
  }
  double num = hasNum ? atof(arg) : -1.0;

  if (k == 'c') {
    int n = hasNum ? (int)num : 0;
    if (n < 0 || n > MAXP) {
      Serial.printf("枚數請輸入 0～%d，例如 c20\n", MAXP);
      return;
    }
    expectN = n;
    testing = true;
    resetState();
    Serial.println();
    Serial.print("▶ 丟幣測試開始");
    if (expectN > 0) Serial.printf("：請丟 %d 枚", expectN);
    Serial.println("，丟完輸入 e。");
    Serial.println("  建議：先一枚一枚隔開丟；再試幾次「兩枚相貼一起滾」，看分不分得出來。");
    if (coinIdx < 0) Serial.println("  （先輸入 k1／k5／k10／k50 設定幣別，報告會多估算速度）");
  } else if (k == 'e') {
    if (!testing) {
      Serial.println("目前不在丟幣測試中：先輸入 c20（或 c）開始。");
      return;
    }
    processEdges();
    if (coinOpen && !blocked) finalizeCoin();
    printReport();
    testing = false;
  } else if (k == 'k') {
    int v = hasNum ? (int)num : 0;
    int idx = -1;
    for (int i = 0; i < 4; i++) {
      if (COIN_VAL[i] == v) idx = i;
    }
    if (v == 0) {
      coinIdx = -1;
      Serial.println("幣別：取消（不估算速度）");
    } else if (idx < 0) {
      Serial.println("幣別請輸入 k1、k5、k10 或 k50（k0 取消）");
    } else if (beamH >= COIN_DIA[idx]) {
      Serial.println("光束高度比硬幣直徑還高，算不出弦長：先用 b 改光束高度");
    } else {
      coinIdx = idx;
      Serial.printf("幣別 %d 元（直徑 %.0f mm）：光束離軌道 %.1f mm 處弦長 %.2f mm，速度≈弦長÷遮光時間\n",
                    COIN_VAL[idx], (double)COIN_DIA[idx], beamH, chordNow());
    }
  } else if (k == 'b') {
    if (!hasNum) {
      Serial.printf("光束離軌道 %.1f mm（例如 b2.5 改成 2.5 mm）\n", beamH);
    } else if (num < 0.1 || num > 15.0) {
      Serial.println("光束高度請輸入 0.1～15 mm，例如 b2.5");
    } else if (coinIdx >= 0 && num >= COIN_DIA[coinIdx]) {
      Serial.println("光束高度比目前幣別的直徑還高，算不出弦長");
    } else {
      beamH = num;
      Serial.printf("光束離軌道改為 %.1f mm", beamH);
      if (coinIdx >= 0) Serial.printf("（%d 元弦長 %.2f mm）", COIN_VAL[coinIdx], chordNow());
      Serial.println();
    }
  } else if (k == 'v') {
    valueMode = !valueMode;
    lastValueMs = millis();
    winSeen = false;
    winEdges = 0;
    if (valueMode) {
      Serial.println("▶ 每 50 ms 印出電位：開（再輸入 v 關閉）");
      Serial.println("  時間｜G27 讀到的 0/1｜■擋住 ·沒擋｜* 這 50 ms 內擋過但已通過｜變化＝這 50 ms 內訊號變了幾次");
    } else {
      Serial.println("每 50 ms 印出電位：關");
    }
  } else if (k == 'p') {
    printPulses = !printPulses;
    Serial.println(printPulses ? "逐筆印出原始脈衝：開" : "逐筆印出原始脈衝：關");
  } else if (k == 'h' || k == 'l') {
    blockedLevel = (k == 'h') ? HIGH : LOW;
    Serial.printf("已設定：擋住時輸出 %s（沒擋＝%s）\n", levelName(blockedLevel),
                  levelName(blockedLevel == HIGH ? LOW : HIGH));
    resetState();
  } else if (k == 'a') {
    autoDetectLevel();
    resetState();
  } else if (k == 'g') {
    if (!hasNum || num < 0 || num > 10000) {
      Serial.println("用法：g3 → 光束連續亮 3 ms 以上，下一次擋住才算新的一枚（0～10000 ms，可有小數）");
    } else {
      rearmUs = (uint32_t)(num * 1000.0 + 0.5);
      Serial.printf("即時計數：亮區門檻改為 %.1f ms\n", rearmUs / 1000.0);
      if (testing) Serial.println("  （測試中改設定：報告仍會試算所有值；即時計數建議輸入 r 重新開始）");
    }
  } else if (k == 'd') {
    if (!hasNum || num < 0 || num > 10000) {
      Serial.println("用法：d30 → 從擋住開始算，30 ms 內再擋住都算同一枚（0～10000 ms）");
    } else {
      debounceUs = (uint32_t)num * 1000UL;
      Serial.printf("即時計數：前緣 DEBOUNCE 改為 %lu ms\n", (unsigned long)(debounceUs / 1000UL));
      if (testing) Serial.println("  （測試中改設定：報告仍會試算所有值；即時計數建議輸入 r 重新開始）");
    }
  } else if (k == 'r') {
    resetState();
    Serial.println(testing ? "已歸零（丟幣測試重新開始）" : "已歸零");
  } else {
    printHelp();
  }
}

// 讀序列埠：Enter（\n 或 \r）結束一行；換行設定選「沒有行尾」時，停 0.3 秒也算一行
void pollSerial() {
  while (Serial.available() > 0) {
    int ch = Serial.read();
    if (ch < 0) break;
    if (ch == '\n' || ch == '\r') {
      if (cmdLen > 0) {
        cmdBuf[cmdLen] = '\0';
        cmdLen = 0;
        runCommand(cmdBuf);
      }
      continue;
    }
    if (cmdLen < (int)sizeof(cmdBuf) - 1) cmdBuf[cmdLen++] = (char)ch;
    cmdLastMs = millis();
  }
  if (cmdLen > 0 && millis() - cmdLastMs > 300) {
    cmdBuf[cmdLen] = '\0';
    cmdLen = 0;
    runCommand(cmdBuf);
  }
}

void setup() {
  Serial.begin(115200);
  delay(300);
  // 開漏輸出＋可讀回（INPUT）＋內建上拉；兩版 core 的 pinMode 都接受這種組合
  pinMode(CLK_PIN, OUTPUT_OPEN_DRAIN | INPUT | PULLUP);
  pinMode(DIO_PIN, OUTPUT_OPEN_DRAIN | INPUT | PULLUP);
  lineHigh(CLK_PIN);
  lineHigh(DIO_PIN);
  dispOk = showNumber(0);

  pinMode(SENSOR_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(SENSOR_PIN), onEdge, CHANGE);

  Serial.println();
  Serial.println("光耦簡易測試原型：1 路槽型光耦（OUT→G27 的 S、VCC→V〔跳帽 3.3V〕、GND→G）");
  Serial.printf("顯示器（CLK→G14、DIO→G13）：%s\n", dispOk ? "有回應" : "沒有回應（沒接也能用）");
  autoDetectLevel();
  resetState();
  printHelp();
}

void loop() {
  pollSerial();

  // 先記下時間再清緩衝區：時間早於 now 的變化一定已經在緩衝區裡（中斷和 loop 在同一個核心），
  // 所以「亮了夠久，這一枚結束」不會判斷錯。比 now 晚的變化用有號差值排除。
  uint32_t now = micros();
  bool drained = processEdges();
  if (drained && coinOpen && !blocked) {
    int32_t sinceEnd = (int32_t)(now - coinEndUs);
    // sinceEnd ≥ 0 時 coinStart ≤ coinEnd ≤ now，離開始的時間用無號差值（擋住超過 35.8 分鐘也不會變成負數）
    if (sinceEnd >= (int32_t)rearmUs && (uint32_t)(now - coinStartUs) > debounceUs) finalizeCoin();
  }

  // 光束連續擋住太久：卡幣，或開機時槽裡有東西導致判定反了（每一段擋住只提醒一次）
  if (!blocked) {
    longBlockWarned = false;
  } else if (!longBlockWarned && (int32_t)(now - pulseStartUs) > (int32_t)LONG_BLOCK_US) {
    longBlockWarned = true;
    Serial.println("  ⚠ 光束已經連續擋住 3 秒：槽裡有東西卡住？或開機時槽裡有東西，擋住電位判定反了。");
    Serial.println("    → 輸入 v 看：槽空著卻顯示「■ 擋住」就是判定反了，清空後輸入 a（或用 h／l 指定）。");
  }

  // 漏記警告（最多每秒一次）
  uint32_t ov = takeOverflow();
  if (ov > 0) {
    ovfTotal += ov;
    ovfPending += ov;
  }
  if (ovfPending > 0 && millis() - lastOvfMsgMs >= 1000) {
    lastOvfMsgMs = millis();
    Serial.printf("  ⚠ 訊號變化太快，緩衝區滿了、漏記 %lu 筆（嚴重抖動或接觸不良）\n", (unsigned long)ovfPending);
    ovfPending = 0;
  }

  if (valueMode && millis() - lastValueMs >= VALUE_MS) {
    lastValueMs = millis();
    printValue();
  }

  // 顯示器最多每 50 ms 更新一次（更新約 20 ms，期間中斷照常記錄，不會漏）
  if (dispDirty && millis() - lastDispMs >= 50) {
    lastDispMs = millis();
    dispDirty = false;
    showNumber(liveCount);
  }
}
