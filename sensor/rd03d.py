from machine import UART, Pin
import time
import math


class Target:
    def __init__(self, x, y, speed, pixel_distance):
        self.x = x
        self.y = y
        self.speed = speed
        self.pixel_distance = pixel_distance
        self.distance = math.sqrt(x**2 + y**2)
        self.angle = math.degrees(math.atan2(x, y))

    def __str__(self):
        return (
            'Target(x={}mm, y={}mm, speed={}cm/s, pixel_dist={}mm, '
            'distance={:.1f}mm, angle={:.1f}°)'
        ).format(
            self.x,
            self.y,
            self.speed,
            self.pixel_distance,
            self.distance,
            self.angle,
        )


class RD03D:
    SINGLE_TARGET_CMD = bytes([0xFD, 0xFC, 0xFB, 0xFA, 0x02, 0x00, 0x80, 0x00, 0x04, 0x03, 0x02, 0x01])
    MULTI_TARGET_CMD = bytes([0xFD, 0xFC, 0xFB, 0xFA, 0x02, 0x00, 0x90, 0x00, 0x04, 0x03, 0x02, 0x01])

    def __init__(self, uart_id=1, tx_pin=4, rx_pin=5, multi_mode=True):
        self.uart = UART(uart_id, baudrate=256000, tx=Pin(tx_pin), rx=Pin(rx_pin))
        self.targets = []
        self.multi_mode = multi_mode
        self._buffer = bytearray()
        time.sleep(0.2)
        self.set_multi_mode(multi_mode)

    def set_multi_mode(self, multi_mode=True):
        cmd = self.MULTI_TARGET_CMD if multi_mode else self.SINGLE_TARGET_CMD
        self.uart.write(cmd)
        time.sleep(0.2)
        self.uart.read()
        self._buffer = bytearray()
        self.multi_mode = multi_mode

    @staticmethod
    def parse_signed16(high, low):
        raw = (high << 8) + low
        sign = 1 if (raw & 0x8000) else -1
        value = raw & 0x7FFF
        return sign * value

    def _decode_frame(self, data):
        targets = []
        if len(data) < 30:
            return targets
        if data[0] != 0xAA or data[1] != 0xFF or data[-2] != 0x55 or data[-1] != 0xCC:
            return targets

        for i in range(3):
            base = 4 + i * 8
            x = self.parse_signed16(data[base + 1], data[base])
            y = self.parse_signed16(data[base + 3], data[base + 2])
            speed = self.parse_signed16(data[base + 5], data[base + 4])
            pixel_dist = data[base + 6] + (data[base + 7] << 8)
            targets.append(Target(x, y, speed, pixel_dist))
        return targets

    def update(self):
        deadline = time.ticks_add(time.ticks_ms(), 200)

        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            n = self.uart.any()
            if n:
                chunk = self.uart.read(n) or b""
                if chunk:
                    self._buffer.extend(chunk)

                    start = self._buffer.find(b"\xAA\xFF")
                    if start != -1:
                        if len(self._buffer) >= start + 30:
                            frame = bytes(self._buffer[start:start + 30])
                            self._buffer = self._buffer[start + 30:]
                            decoded = self._decode_frame(frame)
                            if decoded:
                                self.targets = decoded
                                return True
                    elif len(self._buffer) > 128:
                        self._buffer = self._buffer[-32:]
            else:
                time.sleep(0.01)

        return False

    def get_target(self, target_number=1):
        if 1 <= target_number <= len(self.targets):
            return self.targets[target_number - 1]
        return None
