"""Receiver for COBS-framed, CRC-16-protected binary packets streamed over a serial port.

How the pieces fit together
===========================

There are two phases: wiring, once at startup, and the read loop, for every byte
received afterwards.

1. Wiring (cli.main -> config):

       receiver.toml --load_config()--> ReceiverConfig
           (one PacketBindingConfig per [[packets]]: type byte + DTO class + handler instances)
       ReceiverConfig --build_receiver()--> Receiver(decoder, dispatcher)
           DtoRegistry       packet type -> DTO class         (inside PacketDecoder)
           PacketDispatcher  packet type -> [PacketHandler]   (called back per packet)

2. Read loop (Receiver.run_forever, single thread):

       serial bytes
         -> protocol.FrameSplitter.feed()    bytes between 0x00 delimiters
         -> protocol.cobs.decode()           frame -> payload (zeros restored)
         -> decoding.PacketDecoder.decode()  CRC check, type lookup, DTO.from_bytes()
         -> handlers.PacketDispatcher.dispatch(Packet)
         -> PacketHandler.handle(Packet)     user-defined callbacks: log, store, forward...

   A frame failing any step raises a CobsDecodeError or PacketError. The Receiver
   catches it, counts it in ReceiverStats and moves on to the next frame.

The discovery package reuses steps 2a-2c (DeviceProber) to tell which serial ports
carry decodable traffic, without dispatching anything.

Packages, one topic each, one class per file:
    protocol/   wire level, knows nothing about packet meaning
    dto/        the data structures payloads are deserialized into
    decoding/   payload <-> Packet (type byte + DTO)
    handlers/   what happens to decoded packets
    receiver/   the serial read loop and its statistics
    discovery/  probing ports for protocol traffic
    config/     receiver.toml -> a wired Receiver
"""
