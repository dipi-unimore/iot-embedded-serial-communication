#pragma once

#include "sdkconfig.h" // CONFIG_FREERTOS_UNICORE

// Serial link. 921600 is reliable on ESP32 through the board's USB-UART bridge;
// the receiver's --baud must match.
#define SERIAL_BAUD 921600

// IMU sampling: 10 ms = 100 Hz.
#define IMU_SAMPLE_PERIOD_MS 10

// Slack between producer and consumer: a few hundred ms of samples, so a brief
// stall in the serial task doesn't lose data. When it does fill up, the sensor
// task drops the OLDEST sample (see imuTask in main.cpp).
#define IMU_QUEUE_DEPTH 32

#define SERIAL_TASK_STACK 4096
#define IMU_TASK_STACK 4096

// Serial task gets a slightly higher priority so packets go out with low jitter.
#define SERIAL_TASK_PRIORITY 3
#define IMU_TASK_PRIORITY 2

// Producer and consumer are pinned to different cores where possible, so they
// run truly in parallel. The ESP32-C3 is single-core (only core 0 exists), so there both tasks
// share core 0 and are simply time-sliced; on a dual-core ESP32 they split 1/0.
#if CONFIG_FREERTOS_UNICORE
#define SERIAL_TASK_CORE 0
#define IMU_TASK_CORE 0
#else
#define SERIAL_TASK_CORE 1
#define IMU_TASK_CORE 0
#endif
