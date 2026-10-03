# esp32-serial-communicator

The **sender**: firmware that streams COBS-framed, CRC-16-protected binary packets over
the USB serial link at 921600 baud. Today it sends simulated IMU samples at 100 Hz.

The protocol, the byte-level packet format and the sequence diagrams are documented in
the [root README](../README.md#protocol). This file covers the firmware itself.

Target: ESP32-C3 DevKitC-02 (2MB flash, CP2102N USB-UART bridge, so `Serial` is UART0).

## Layout

```
platformio.ini        board, 2MB flash override, PacketSerial dependency, logs silenced
partitions.csv        single-app partition table that fits 2MB (Arduino's default needs 4MB)
include/app_config.h  tunables: baud, sample rate, queue depth, task stack/priority/core
lib/framing/          the protocol definition: packet structs + crc16 (framing.h / framing.cpp)
src/main.cpp          the tasks: imuTask (producer), serialTask (consumer), simulated readImu()
```

## How it works

Producer/consumer through a FreeRTOS queue (see [Architecture](../README.md#architecture)).
See the [sender sequence diagram](../README.md#inside-the-sender-firmware).

- **`imuTask`** (producer) calls `readImu()` every `IMU_SAMPLE_PERIOD_MS` (10 ms = 100 Hz),
  timed with `vTaskDelayUntil` so the rate doesn't drift, and pushes an `ImuSample` onto
  the queue. If the queue is full it **drops the oldest** sample instead of blocking, so
  the sampling rate never stalls.
- **`serialTask`** (consumer) is the *only* task touching `Serial`/`PacketSerial`, which
  isn't thread-safe. Every 1 ms it calls `packetSerial.update()` to process incoming frames,
  then drains the queue: for each sample it fills an `ImuPacket`, calls `framing_seal()` to
  compute the CRC, and `send()`s it. PacketSerial does the COBS encoding and appends `0x00`.
- **Cores**: the ESP32-C3 is single-core, so both tasks run on core 0, time-sliced by
  priority (`serialTask` 3 > `imuTask` 2). On a dual-core ESP32, `app_config.h`
  pins them to cores 1/0 automatically (`CONFIG_FREERTOS_UNICORE`).
- **Simulated IMU**: `readImu()` returns a sine sway on X/Y and 9.81 on Z. See
  [the IMU example](../README.md#the-imu-example) for the fields and how to plug in a real sensor.
- **Incoming packets** (PC → device) reach `onPacketReceived()`, which is an empty stub
  for now. See [commands](../README.md#c-pc--device-commands).

### Tunables (`include/app_config.h`)

| Define | Default | Meaning |
|---|---|---|
| `SERIAL_BAUD` | 921600 | UART baud rate. Must match `baud` in the receiver's `receiver.toml`. |
| `IMU_SAMPLE_PERIOD_MS` | 10 | Sampling period: 1000 / value = Hz (1 ms minimum, the FreeRTOS tick). |
| `IMU_QUEUE_DEPTH` | 32 | Slack between producer and consumer (320 ms at 100 Hz). |
| `SERIAL_TASK_PRIORITY` / `IMU_TASK_PRIORITY` | 3 / 2 | The serial task wins ties, for low output jitter. |
| `SERIAL_TASK_STACK` / `IMU_TASK_STACK` | 4096 | Task stack size in bytes. |
| `SERIAL_TASK_CORE` / `IMU_TASK_CORE` | 0 / 0 (C3), 1 / 0 (dual-core) | Core pinning. |

## Build / flash

```bash
pio run                 # build
pio run -t upload       # build + flash
```

Don't use `pio device monitor` to look at the output, because it's binary. Use
[`serial-receiver`](../serial-receiver/) instead. Anything else printed on `Serial` corrupts
the stream, including the Arduino core's own logs (silenced with `CORE_DEBUG_LEVEL=0`
in `platformio.ini`). Stop the receiver before flashing: the upload needs the port.

## Adding a packet type

The full walkthrough, with environment-sensor and button examples on both sides, is in
[Extending to other examples](../README.md#extending-to-other-examples). On the firmware side:

1. Add a value to `PacketType` and a packed struct ending in `uint16_t crc` to
   `lib/framing/framing.h`, with a `static_assert` on its size.
2. Produce it: a producer task (or event source) enqueues the data. With more than one
   producer, make the queue item a tagged union (`type` + one member per sample kind).
3. In `serialTask`, build the struct, call `framing_seal()` and `packetSerial.send()` it.
4. Mirror the layout on the receiver side (a DTO + a `[[packets]]` entry) and add the
   type to the [packet type registry](../README.md#packet-type-registry).
