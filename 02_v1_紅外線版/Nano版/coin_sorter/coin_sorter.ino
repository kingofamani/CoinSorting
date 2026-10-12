/*
 * 智能分幣機（研習精簡版）
 * Arduino Nano + 4 路紅外線避障模組 + 4 位數七段顯示器（TM1637，4 腳）
 * 硬幣經過感測器就計數，七段顯示器顯示總金額
 * 歸零：按 Nano 板上的 RESET 鍵
 * 不需安裝任何函式庫
 *
 * 接線：探頭由左至右 1、5、10、50 元 → 主控板 IN4、IN3、IN2、IN1
 *       主控板 OUT4→D5、OUT3→D4、OUT2→D3、OUT1→D2
 *       顯示器 CLK → D8、DIO → D9
 */

// ===== 1. 腳位 =====
const byte SENSOR_PIN[4] = {5, 4, 3, 2};   // 1元=D5(OUT4)、5元=D4(OUT3)、10元=D3(OUT2)、50元=D2(OUT1)
const int  COIN_VALUE[4] = {1, 5, 10, 50};
const byte CLK_PIN = 8;    // 顯示器 CLK
const byte DIO_PIN = 9;    // 顯示器 DIO

// ===== 2. 設定 =====
const bool BLOCKED_LEVEL = LOW;          // 硬幣經過時的輸出電位；完全不計數就改成 HIGH
const unsigned long DEBOUNCE_MS = 50;    // 丟一枚卻 +2，就調大到 80
const byte BRIGHTNESS = 4;               // 顯示器亮度 0~7
const bool TEST_MODE = false;            // 改 true：序列埠持續顯示 4 個感測器狀態

// 數字 0~9 的七段碼（bit0=a … bit6=g）
const byte SEG_CODE[10] = {0x3F, 0x06, 0x5B, 0x4F, 0x66, 0x6D, 0x7D, 0x07, 0x7F, 0x6F};

long counts[4] = {0, 0, 0, 0};
bool wasBlocked[4] = {false, false, false, false};
unsigned long lastHit[4] = {0, 0, 0, 0};

// ===== TM1637 驅動（兩條線：CLK、DIO）=====
// 線拉低＝設成 OUTPUT 輸出 LOW；放開＝設成 INPUT，由模組上的電阻拉高
void lineLow(byte p)  { pinMode(p, OUTPUT); }
void lineHigh(byte p) { pinMode(p, INPUT); }
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

long getTotal() {
  long t = 0;
  for (int i = 0; i < 4; i++) t += counts[i] * COIN_VALUE[i];
  return t;
}

// 檢查 4 個感測器：從「沒擋住」變成「擋住」就算一枚
void checkSensors() {
  for (int i = 0; i < 4; i++) {
    bool blocked = (digitalRead(SENSOR_PIN[i]) == BLOCKED_LEVEL);
    if (blocked && !wasBlocked[i] && millis() - lastHit[i] > DEBOUNCE_MS) {
      counts[i]++;
      lastHit[i] = millis();
      long total = getTotal();
      showNumber(total);
      Serial.print(COIN_VALUE[i]);
      Serial.print(F(" 元 +1，總額 "));
      Serial.println(total);
    }
    wasBlocked[i] = blocked;
  }
}

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 4; i++) pinMode(SENSOR_PIN[i], INPUT_PULLUP);
  digitalWrite(CLK_PIN, LOW);   // 先設定「輸出時為 LOW」
  digitalWrite(DIO_PIN, LOW);
  lineHigh(CLK_PIN);
  lineHigh(DIO_PIN);

  // 開機自我測試：顯示 1234 一秒半
  showNumber(1234);
  delay(1500);
  showNumber(0);
  Serial.println(F("分幣機就緒"));
}

void loop() {
  checkSensors();

  if (TEST_MODE) {
    static unsigned long lastPrint = 0;
    if (millis() - lastPrint > 200) {
      lastPrint = millis();
      for (int i = 0; i < 4; i++) {
        Serial.print(digitalRead(SENSOR_PIN[i]));
        Serial.print(i < 3 ? "  " : "\n");
      }
    }
  }
}
