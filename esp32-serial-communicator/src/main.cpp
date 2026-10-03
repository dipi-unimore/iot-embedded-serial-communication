#include <Arduino.h>
#include <PacketSerial.h> // COBS framing + 0x00 delimiter + packet-received callback

#include "app_config.h"
#include "framing.h" // packet structs + crc16, shared with every target

// What the sensor task hands to the serial task: just the reading and when it
// was taken. Turning it into a wire packet (type byte, CRC) is the serial task's job.
struct ImuSample {
    uint32_t timestamp;
    float ax, ay, az;
};

// PacketSerial is not thread-safe (its decode buffer has no mutex), so it and
// Serial are owned exclusively by serialTask. Every other task talks to it only
// through a queue - no mutex needed.
static PacketSerial packetSerial;
static QueueHandle_t imuQueue;

// No IMU is wired yet: synthesize a plausible signal (slow sway on X/Y, gravity
// on Z) so the receiver has something non-constant to decode. Swap this for the
// real driver read once a sensor is connected.
static ImuSample readImu() {
    const uint32_t now = millis();
    const float t = now / 1000.0f;
    return {
        now,
        0.5f * sinf(TWO_PI * 0.5f * t),
        0.5f * cosf(TWO_PI * 0.5f * t),
        9.81f,
    };
}

// Producer: samples the IMU at a fixed rate and enqueues each reading.
static void imuTask(void *param) {
    TickType_t lastWake = xTaskGetTickCount();
    for (;;) {
        ImuSample sample = readImu();
        if (xQueueSend(imuQueue, &sample, 0) != pdTRUE) {
            // Queue full: the serial task fell behind. For a live stream the newest
            // sample is worth more than the oldest, so evict one and retry instead
            // of blocking the producer (which would skew the sampling rate).
            ImuSample discarded;
            xQueueReceive(imuQueue, &discarded, 0);
            xQueueSend(imuQueue, &sample, 0);
        }
        vTaskDelayUntil(&lastWake, pdMS_TO_TICKS(IMU_SAMPLE_PERIOD_MS)); // steady rate, also yields the CPU
    }
}

// Called by packetSerial.update(), i.e. inside serialTask. PC -> device commands
// will be decoded here; nothing to handle yet.
static void onPacketReceived(const uint8_t *buffer, size_t size) {
    (void) buffer;
    (void) size;
}

static void sendImuPacket(const ImuSample &sample) {
    ImuPacket pkt;
    pkt.type = PACKET_TYPE_IMU;
    pkt.timestamp = sample.timestamp;
    pkt.ax = sample.ax;
    pkt.ay = sample.ay;
    pkt.az = sample.az;
    framing_seal(pkt);
    packetSerial.send(reinterpret_cast<const uint8_t *>(&pkt), sizeof(pkt)); // COBS-encodes + appends 0x00
}

// Consumer: the only task that ever touches Serial / packetSerial.
static void serialTask(void *param) {
    Serial.begin(SERIAL_BAUD);
    packetSerial.setStream(&Serial);
    packetSerial.setPacketHandler(&onPacketReceived);

    ImuSample sample;
    for (;;) {
        packetSerial.update(); // reads incoming bytes, fires onPacketReceived per complete frame
        while (xQueueReceive(imuQueue, &sample, 0) == pdTRUE) {
            sendImuPacket(sample);
        }
        vTaskDelay(1); // not optional: yields so other tasks run and the watchdog stays fed
    }
}

void setup() {
    imuQueue = xQueueCreate(IMU_QUEUE_DEPTH, sizeof(ImuSample));
    configASSERT(imuQueue != NULL);

    xTaskCreatePinnedToCore(serialTask, "serial", SERIAL_TASK_STACK, NULL, SERIAL_TASK_PRIORITY, NULL, SERIAL_TASK_CORE);
    xTaskCreatePinnedToCore(imuTask, "imu", IMU_TASK_STACK, NULL, IMU_TASK_PRIORITY, NULL, IMU_TASK_CORE);
}

void loop() {
    vTaskDelay(portMAX_DELAY); // unused: all the work happens in the tasks above
}
