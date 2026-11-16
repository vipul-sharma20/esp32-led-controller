#include <Arduino.h>
#include <Adafruit_NeoPixel.h>

// Standalone wiring diagnostic, not WLED. Uploading replaces installed firmware.
constexpr uint16_t LEDS_PER_STRIP = 300;
constexpr uint8_t BRIGHTNESS = 32;  // Start dim; this sketch has no current limiter.
Adafruit_NeoPixel strip18(LEDS_PER_STRIP, 18, NEO_GRB + NEO_KHZ800);
Adafruit_NeoPixel strip19(LEDS_PER_STRIP, 19, NEO_GRB + NEO_KHZ800);

void showColor(Adafruit_NeoPixel &strip, uint8_t r, uint8_t g, uint8_t b) {
  strip.clear();
  strip.fill(strip.Color(r, g, b));
  strip.show();
}

void identify() {
  showColor(strip18, 0, 255, 0);
  showColor(strip19, 0, 0, 255);
  Serial.printf("TEST ACTIVE: GPIO18 = %u green LEDs; GPIO19 = %u blue LEDs; brightness %u/255\n",
                LEDS_PER_STRIP, LEDS_PER_STRIP, BRIGHTNESS);
}

void setup() {
  Serial.begin(115200);
  strip18.begin();
  strip19.begin();
  strip18.setBrightness(BRIGHTNESS);
  strip19.setBrightness(BRIGHTNESS);
  delay(500);
  identify();
  Serial.println("Commands: i=identify, r=red, g=green, b=blue, w=white, o=off");
}

void loop() {
  if (Serial.available()) {
    const char command = Serial.read();
    if (command == 'i') {
      identify();
    } else {
      uint8_t r = 0, g = 0, b = 0;
      switch (command) {
        case 'r': r = 255; break;
        case 'g': g = 255; break;
        case 'b': b = 255; break;
        case 'w': r = g = b = 255; break;
        case 'o': break;
        default: delay(10); return;
      }
      showColor(strip18, r, g, b);
      showColor(strip19, r, g, b);
      Serial.printf("Applied command: %c\n", command);
    }
  }
  delay(10);
}
