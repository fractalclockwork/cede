cmake_minimum_required(VERSION 3.13)
include($ENV{PICO_SDK_PATH}/pico_sdk_init.cmake)

project(gv2 C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

# Build Identity injection (DS-9.3): prefer CEDE_IMAGE_ID from the build env
# (set by `cede build`), fall back to a git short SHA, finally to "unknown".
set(_REPO_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../..")
if(DEFINED ENV{CEDE_IMAGE_ID} AND NOT "$ENV{CEDE_IMAGE_ID}" STREQUAL "")
  set(CEDE_IMAGE_ID "$ENV{CEDE_IMAGE_ID}")
else()
  execute_process(
    COMMAND git -C "${_REPO_ROOT}" rev-parse --short=12 HEAD
    OUTPUT_VARIABLE CEDE_IMAGE_ID
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
  )
endif()
if(NOT CEDE_IMAGE_ID)
  set(CEDE_IMAGE_ID "unknown")
endif()
string(REGEX REPLACE "[^A-Za-z0-9._-]" "" CEDE_IMAGE_ID "${CEDE_IMAGE_ID}")
if(CEDE_IMAGE_ID STREQUAL "")
  set(CEDE_IMAGE_ID "unknown")
endif()

add_executable(gv2 src/main.c)

target_compile_definitions(gv2 PRIVATE CEDE_IMAGE_ID="${CEDE_IMAGE_ID}")

target_link_libraries(gv2 pico_stdlib)

pico_enable_stdio_usb(gv2 1)
pico_enable_stdio_uart(gv2 0)

pico_add_extra_outputs(gv2)
