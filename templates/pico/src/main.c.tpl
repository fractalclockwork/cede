#include <stdio.h>
#include "pico/stdlib.h"

#ifndef CEDE_IMAGE_ID
#define CEDE_IMAGE_ID "unknown"
#endif

int main() {
    stdio_init_all();
    sleep_ms(2000);

    printf("CEDE {{app_name}} rp2 ok digest=%s\n", CEDE_IMAGE_ID);

    while (1) {
        printf("{{app_name}} running\n");
        sleep_ms(5000);
    }
    return 0;
}
