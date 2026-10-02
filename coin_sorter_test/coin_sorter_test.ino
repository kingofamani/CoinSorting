/*
 * 分幣機 講師測試程式（研習前使用，老師不需要）
 * 接線與正式程式相同：
 *   探頭由左至右 1、5、10、50 元 → 主控板 IN4、IN3、IN2、IN1
 *   主控板 OUT4→D5、OUT3→D4、OUT2→D3、OUT1→D2
 *   顯示器 CLK → D8、DIO → D9
 *
 * 序列埠監控視窗設 115200，在上方輸入框打指令再按 Enter：
 *   d   顯示器測試（開機預設）：1234 → 8888（全亮）→ 亮度 0~7 → 重複
 *   s   感測器對應測試：擋住探頭，序列埠與顯示器會顯示是幾元的探頭
 *   ?   顯示說明
 * 不需安裝任何函式庫
 */

const byte SENSOR_PIN[4] = {5, 4, 3, 2};   // 1元、5元、10元、50元
const int  COIN_VALUE[4] = {1, 5, 10, 50};
const byte CLK_PIN = 8;
const byte DIO_PIN = 9;
const bool BLOCKED_LEVEL = LOW;
const unsigned long DEBOUNCE_MS = 50;

const byte SEG_CODE[10] = {0x3F, 0x06, 0x5B, 0x4F, 0x66, 0x6D, 0x7D, 0x07, 0x7F, 0x6F};

byte brightness = 4;
char mode = 'd';
int step = 0;
unsigned long stepStart = 0;

bool wasBlocked[4] = {false, false, false, false};
unsigned long lastHit[4] = {0, 0, 0, 0};
long hits[4] = {0, 0, 0, 0};

// ---------- TM1637 ----------
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

bool tmShow(const byte seg[4]) {
  bool ok = true;
  tmStart(); ok &= tmWrite(0x40); tmStop();
  tmStart(); ok &= tmWrite(0xC0);
  for (int i = 0; i < 4; i++) ok &= tmWrite(seg[i]);
  tmStop();
  tmStart(); ok &= tmWrite(0x88 | (brightness & 7)); tmStop();
  return ok;
}

void reportAck(bool ok) {
  if (ok) {
    Serial.println(F("  顯示器有回應 ✔"));
  } else {
    Serial.println(F("  ✘ 顯示器沒有回應：檢查 VCC/GND 是否接上、CLK→D8、DIO→D9 是否接反或鬆脫"));
  }
}

// ---------- 顯示器測試 ----------
void doDisplayStep() {
  byte seg[4];
  bool ok;
  switch (step) {
    case 0:
      brightness = 4;
      for (int i = 0; i < 4; i++) seg[i] = SEG_CODE[i + 1];
      ok = tmShow(seg);
      Serial.println(F("[1] 應顯示「1234」（從左到右）"));
      reportAck(ok);
      break;
    case 1:
      for (int i = 0; i < 4; i++) seg[i] = 0xFF;     // 含小數點/冒號全亮
      ok = tmShow(seg);
      Serial.println(F("[2] 應顯示「8888」且所有段都亮（有冒號的模組，冒號也會亮）→ 檢查有沒有壞段"));
      reportAck(ok);
      break;
    default: {                                         // 步驟 2~9：亮度 0~7
      brightness = step - 2;
      for (int i = 0; i < 4; i++) seg[i] = SEG_CODE[8];
      seg[3] = SEG_CODE[brightness];
      ok = tmShow(seg);
      Serial.print(F("[3] 亮度 "));
      Serial.print(brightness);
      Serial.println(F("（最右邊顯示亮度數字，看哪個亮度最清楚，填入正式程式 BRIGHTNESS）"));
      if (!ok) reportAck(ok);
      break;
    }
  }
}

// ---------- 感測器 ----------
void showValue(int v) {        // 靠右顯示 1、5、10、50
  byte seg[4] = {0, 0, 0, SEG_CODE[v % 10]};
  if (v >= 10) seg[2] = SEG_CODE[v / 10];
  tmShow(seg);
}

void checkSensors() {
  for (int i = 0; i < 4; i++) {
    bool blocked = (digitalRead(SENSOR_PIN[i]) == BLOCKED_LEVEL);
    if (blocked && !wasBlocked[i] && millis() - lastHit[i] > DEBOUNCE_MS) {
      lastHit[i] = millis();
      hits[i]++;
      showValue(COIN_VALUE[i]);
      Serial.print(F("D"));
      Serial.print(SENSOR_PIN[i]);
      Serial.print(F("（主控板 OUT"));
      Serial.print(4 - i);
      Serial.print(F(" / IN"));
      Serial.print(4 - i);
      Serial.print(F("，應接 "));
      Serial.print(COIN_VALUE[i]);
      Serial.print(F(" 元探頭）觸發，累計 "));
      Serial.print(hits[i]);
      Serial.println(F(" 次"));
    }
    wasBlocked[i] = blocked;
  }
}

void printHelp() {
  Serial.println();
  Serial.println(F("===== 分幣機 講師測試程式（TM1637 版）====="));
  Serial.println(F("d ：顯示器測試（1234 → 8888 → 亮度 0~7，每步 2 秒，會重複）"));
  Serial.println(F("s ：感測器對應測試"));
  Serial.println(F("? ：顯示本說明"));
  Serial.println();
}

void handleSerial() {
  if (!Serial.available()) return;
  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  cmd.toLowerCase();
  if (cmd.length() == 0) return;

  if (cmd == "d") {
    mode = 'd';
    step = 0;
    doDisplayStep();
    stepStart = millis();
  } else if (cmd == "s") {
    mode = 's';
    brightness = 4;
    for (int i = 0; i < 4; i++) {
      hits[i] = 0;
      wasBlocked[i] = (digitalRead(SENSOR_PIN[i]) == BLOCKED_LEVEL);
    }
    byte blank[4] = {0, 0, 0, 0};
    tmShow(blank);
    Serial.println(F("感測器測試：用手指或白紙逐一擋住探頭，看序列埠顯示是幾元的探頭（顯示器也會顯示 1、5、10、50）。"));
    for (int i = 0; i < 4; i++) {
      if (wasBlocked[i]) {
        Serial.print(F("注意：D"));
        Serial.print(SENSOR_PIN[i]);
        Serial.println(F(" 目前沒擋也是「觸發」狀態 → 靈敏度太高或探頭對到牆，請調低該路可變電阻"));
      }
    }
  } else {
    printHelp();
  }
}

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(300);
  for (int i = 0; i < 4; i++) pinMode(SENSOR_PIN[i], INPUT_PULLUP);
  digitalWrite(CLK_PIN, LOW);
  digitalWrite(DIO_PIN, LOW);
  lineHigh(CLK_PIN);
  lineHigh(DIO_PIN);
  printHelp();
  step = 0;
  doDisplayStep();
  stepStart = millis();
}

void loop() {
  handleSerial();
  if (mode == 'd') {
    if (millis() - stepStart >= 2000) {
      step = (step + 1) % 10;
      doDisplayStep();
      stepStart = millis();
    }
  } else {
    checkSensors();
  }
}
