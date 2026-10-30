# Portions Copyright (c) 2026 Microsoft Corporation

cmake_minimum_required(VERSION 3.18)
project(remote VERSION 0.1.0 LANGUAGES C)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

#
# Dependencies
#
find_package(LibVNCServer REQUIRED)
find_package(Threads REQUIRED)
find_library(CARBON_LIBRARY Carbon REQUIRED)
find_library(IOKIT_LIBRARY IOKit REQUIRED)
find_library(APPKIT_FRAMEWORK AppKit REQUIRED)
find_library(SCREEN_CAPTURE_KIT ScreenCaptureKit REQUIRED)
find_library(CORE_MEDIA CoreMedia)
find_library(CORE_VIDEO CoreVideo)
find_library(FOUNDATION Foundation)

#
# Sources
#
set(SOURCE_FILES
    src/ScreenCapturer.h
    src/ScreenCapturer.m
    src/mac.m
)

#
# Build bundle
#
add_executable(${PROJECT_NAME} MACOSX_BUNDLE ${SOURCE_FILES})

target_link_libraries(${PROJECT_NAME} LibVNCServer::vncserver ${CMAKE_THREAD_LIBS_INIT} ${CARBON_LIBRARY} ${IOKIT_LIBRARY}
  ${APPKIT_FRAMEWORK}
  ${SCREEN_CAPTURE_KIT}
  ${CORE_MEDIA}
  ${CORE_VIDEO}
  ${FOUNDATION})
