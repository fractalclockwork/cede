#include <stdio.h>
#include "pico/stdlib.h"

#ifndef CEDE_IMAGE_ID
#define CEDE_IMAGE_ID "unknown"
#endif

int main() {
    stdio_init_all();
    sleep_ms(2000);

    printf("CEDE gv2 rp2 ok digest=%s\n", CEDE_IMAGE_ID);
    fflush(stdout);

    while (1) {
        sleep_ms(3000);
        printf("CEDE gv2 rp2 ok digest=%s\n", CEDE_IMAGE_ID);
        fflush(stdout);
    }
    return 0;
}
