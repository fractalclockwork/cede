cmake_minimum_required(VERSION 3.13)
include($ENV{PICO_SDK_PATH}/pico_sdk_init.cmake)

project({{app_name}} C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

add_executable({{app_name}} src/main.c)

target_link_libraries({{app_name}} pico_stdlib)

# Enable USB serial, disable UART
pico_enable_stdio_usb({{app_name}} 1)
pico_enable_stdio_uart({{app_name}} 0)

pico_add_extra_outputs({{app_name}})
