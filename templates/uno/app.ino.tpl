#include "cede_build_id.h"

void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.print("CEDE {{app_name}} ok digest=");
    Serial.println(CEDE_IMAGE_ID);
}

void loop() {
    Serial.println("{{app_name}} running");
    delay(5000);
}
