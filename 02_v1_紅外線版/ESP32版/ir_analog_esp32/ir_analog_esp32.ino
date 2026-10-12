/*
 * 4 路紅外線探頭「類比值」讀取（ESP32）
 *
 * 探頭本身輸出的是類比電壓（擋住程度不同，電壓就不同），
 * 主控板上的比較器再拿它和可變電阻設定的門檻比較，才變成 0/1 的 OUT。
 * 這支程式直接讀探頭的類比電壓，同時讀主控板的 OUT，方便看兩者的關係。
 *
 * ESP32 類比讀值範圍 0～4095（12 位元），約對應 0～3.3V。
 * ※ 擴展板黃色跳帽一定要在 3.3V，探頭電壓才不會超過 ESP32 能讀的範圍。
 *
 * 接線（類比，要另外拉線）：
 *   探頭 OUT（也就是主控板 IN 插座的訊號）另外接到 ESP32：
 *     1元探頭 → G35、5元探頭 → G34、10元探頭 → SN(G39)、50元探頭 → SP(G36)
 *   方法一：用小麵包板把探頭 OUT 分成兩條，一條照舊接主控板 IN、一條接 ESP32。
 *   方法二：只看類比值時，探頭直接接 ESP32：VCC→V、GND→G、OUT→上面的腳位。
 * 數位 OUT（沿用原本接線，沒接也可以）：
 *   主控板 OUT4(1元)→G27、OUT3(5元)→G26、OUT2(10元)→G25、OUT1(50元)→G33
 *
 * 序列埠 115200，每 50 ms 一行。輸入指令後按 Enter：
 *   p   切換「序列繪圖家」格式（工具 → 序列繪圖家）
 *   s   顯示開機（或歸零）以來每一路的最低／最高值
 *   r   最低／最高值歸零
 */

const byte ANALOG_PIN[4]  = {35, 34, 39, 36};   // 1元、5元、10元、50元（ADC1，只能輸入）
const byte DIGITAL_PIN[4] = {27, 26, 25, 33};   // 主控板 OUT4、OUT3、OUT2、OUT1
const char *NAME[4]       = {" 1元", " 5元", "10元", "50元"};
const char *PLOT_NAME[4]  = {"1yuan", "5yuan", "10yuan", "50yuan"};
const unsigned long INTERVAL_MS = 50;           // 印出間隔

bool plotMode = false;
unsigned long lastPrint = 0;

// 每個印出區間內的統計（程式會在 50 ms 內連續讀很多次，快速通過的硬幣也抓得到）
long sum[4];
int  cnt[4];
int  winMin[4], winMax[4];
bool winBlocked[4];
// 開機以來的最低／最高
int  allMin[4], allMax[4];

void resetWindow() {
  for (int i = 0; i < 4; i++) {
    sum[i] = 0; cnt[i] = 0;
    winMin[i] = 4095; winMax[i] = 0;
    winBlocked[i] = false;
  }
}

void resetAll() {
  for (int i = 0; i < 4; i++) { allMin[i] = 4095; allMax[i] = 0; }
  resetWindow();
}

void printHelp() {
  Serial.println();
  Serial.println("===== 4 路紅外線探頭類比值（0～4095）=====");
  Serial.println("每行格式： 名稱 平均值(電壓) [區間最低～最高] D=主控板OUT");
  Serial.println("  D=1 沒擋、D=0 擋住（這 50 ms 內只要擋過就顯示 0）");
  Serial.println("  區間最低／最高＝這 50 ms 內讀到的範圍，硬幣快速通過時看這裡");
  Serial.println("指令：p 繪圖格式切換、s 顯示最低/最高紀錄、r 紀錄歸零");
  Serial.println("==========================================");
}

void printSummary() {
  Serial.println();
  Serial.println("---- 開機（或歸零）以來的範圍 ----");
  for (int i = 0; i < 4; i++) {
    Serial.printf("%s：最低 %4d（%.2fV）、最高 %4d（%.2fV）、差距 %4d\n",
                  NAME[i], allMin[i], allMin[i] * 3.3 / 4095, allMax[i], allMax[i] * 3.3 / 4095,
                  allMax[i] - allMin[i]);
  }
  Serial.println("差距越大，代表擋住與沒擋的差別越明顯，比較容易調到穩定。");
  Serial.println("----------------------------------");
}

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(200);
  analogReadResolution(12);
  for (int i = 0; i < 4; i++) {
    pinMode(ANALOG_PIN[i], INPUT);
    pinMode(DIGITAL_PIN[i], INPUT_PULLUP);
  }
  delay(300);
  resetAll();
  printHelp();
}

void loop() {
  // 指令
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    cmd.toLowerCase();
    if (cmd == "p") { plotMode = !plotMode; if (!plotMode) printHelp(); }
    else if (cmd == "s") printSummary();
    else if (cmd == "r") { resetAll(); Serial.println("已歸零"); }
    else if (cmd.length()) printHelp();
  }

  // 連續取樣
  for (int i = 0; i < 4; i++) {
    int v = analogRead(ANALOG_PIN[i]);
    sum[i] += v;
    cnt[i]++;
    if (v < winMin[i]) winMin[i] = v;
    if (v > winMax[i]) winMax[i] = v;
    if (v < allMin[i]) allMin[i] = v;
    if (v > allMax[i]) allMax[i] = v;
    if (digitalRead(DIGITAL_PIN[i]) == LOW) winBlocked[i] = true;
  }

  if (millis() - lastPrint < INTERVAL_MS) return;
  lastPrint = millis();

  if (plotMode) {
    for (int i = 0; i < 4; i++) {
      Serial.printf("%s:%ld", PLOT_NAME[i], cnt[i] ? sum[i] / cnt[i] : 0L);
      Serial.print(i < 3 ? "," : "\n");
    }
  } else {
    char line[240];
    int n = 0;
    for (int i = 0; i < 4; i++) {
      long avg = cnt[i] ? sum[i] / cnt[i] : 0;
      n += snprintf(line + n, sizeof(line) - n, "%s %4ld(%.2fV) [%4d~%4d] D=%d | ",
                    NAME[i], avg, avg * 3.3 / 4095, winMin[i], winMax[i], winBlocked[i] ? 0 : 1);
    }
    Serial.println(line);
  }
  resetWindow();
}
