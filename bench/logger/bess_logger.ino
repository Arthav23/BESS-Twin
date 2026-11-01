/*
  BESS-Twin bench logger for ESP32 (Arduino core 2.x or 3.x)
  Logs cell voltage, current and two temperatures at 10 Hz as CSV over USB serial, in exactly the
  format bench/calibrate.py reads:   t_s,V,I_A,T_C,Tamb_C
  and opens a relay (cuts the load or charger) if a safety limit is crossed.

  NOT YET TESTED ON HARDWARE. Check every reading against a multimeter before the first real test.

  Wiring (see WIRING.md):
    INA226 module  VCC 3.3V, GND, SDA GPIO21, SCL GPIO22, address 0x40 (A0 = A1 = GND)
                   IN+ to cell +, IN- to load/charger +, VBUS to cell +, cell - to GND and load -
                   REPLACE the module's 0.1 ohm shunt with a 10 mOhm 1 % 2 W shunt (5 A -> 50 mV)
    NTC 10k B3950  on the cell can: 3.3V - 10k 1 % - GPIO34 - NTC - GND
    NTC 10k B3950  in the air:      3.3V - 10k 1 % - GPIO35 - NTC - GND
    Relay module   IN on GPIO26, active HIGH = load connected (fail-safe: relay off on reset or alarm)
*/
#include <Wire.h>

const uint8_t  INA_ADDR   = 0x40;
const float    R_SHUNT    = 0.010;     // ohm, the shunt you fitted (measure it if you can)
const float    I_SIGN     = 1.0;       // set to -1.0 if discharge reads negative
const int      PIN_NTC    = 34, PIN_AMB = 35, PIN_RELAY = 26;
const float    R_PULL     = 10000.0, NTC_R25 = 10000.0, NTC_B = 3950.0;
const float    V_MAX = 4.25, V_MIN = 2.50, T_MAX = 60.0;   // stop limits from the bench guide
const uint32_t PERIOD_MS  = 100;       // 10 samples per second

uint32_t t0, next_ms;
bool tripped = false;

void inaWrite(uint8_t reg, uint16_t v) {
  Wire.beginTransmission(INA_ADDR); Wire.write(reg); Wire.write(v >> 8); Wire.write(v & 0xFF); Wire.endTransmission();
}
int16_t inaRead(uint8_t reg) {
  Wire.beginTransmission(INA_ADDR); Wire.write(reg); Wire.endTransmission(false);
  Wire.requestFrom((int)INA_ADDR, 2);
  uint16_t hi = Wire.read(), lo = Wire.read();
  return (int16_t)((hi << 8) | lo);
}
float ntcC(int pin) {
  uint32_t mv = 0;
  for (int i = 0; i < 16; i++) mv += analogReadMilliVolts(pin);   // factory-calibrated ADC reading
  float v = mv / 16.0 / 1000.0;
  if (v <= 0.01 || v >= 3.29) return NAN;                          // open or shorted sensor
  float r = R_PULL * v / (3.3 - v);
  return 1.0 / (1.0 / 298.15 + log(r / NTC_R25) / NTC_B) - 273.15;
}
void trip(const char *why) {
  digitalWrite(PIN_RELAY, LOW); tripped = true;
  Serial.print("# ALARM: "); Serial.print(why); Serial.println(" - relay opened. Reset the board to continue.");
}

void setup() {
  pinMode(PIN_RELAY, OUTPUT); digitalWrite(PIN_RELAY, LOW);
  Serial.begin(115200);
  Wire.begin(21, 22);
  analogSetAttenuation(ADC_11db);
  // INA226: average 16, bus and shunt conversion 1.1 ms each, continuous -> about 35 ms per result
  inaWrite(0x00, 0x4927);
  delay(200);
  Serial.println("# BESS-Twin bench logger. Relay closes 3 s after start; send 's' to open it at any time.");
  Serial.println("t_s,V,I_A,T_C,Tamb_C");
  t0 = millis(); next_ms = t0;
}

void loop() {
  if (Serial.available() && Serial.read() == 's') trip("stop requested");
  if (!tripped && millis() - t0 > 3000) digitalWrite(PIN_RELAY, HIGH);
  if ((int32_t)(millis() - next_ms) < 0) return;
  next_ms += PERIOD_MS;

  float vsh = inaRead(0x01) * 2.5e-6;          // shunt voltage, 2.5 uV per bit
  float V   = inaRead(0x02) * 1.25e-3;         // bus voltage, 1.25 mV per bit
  float I   = I_SIGN * vsh / R_SHUNT;
  float T   = ntcC(PIN_NTC), Ta = ntcC(PIN_AMB);
  float t   = (millis() - t0) / 1000.0;

  Serial.print(t, 2); Serial.print(','); Serial.print(V, 4); Serial.print(',');
  Serial.print(I, 3); Serial.print(','); Serial.print(T, 2); Serial.print(','); Serial.println(Ta, 2);

  if (tripped) return;
  if (V > V_MAX) trip("cell above 4.25 V");
  else if (V < V_MIN && I > 0.05) trip("cell below 2.5 V");
  else if (isnan(T)) trip("cell thermistor open or shorted");
  else if (T > T_MAX) trip("cell above 60 C");
}
