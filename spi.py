import spidev

spi = spidev.SpiDev()
spi.open(0, 0)
spi.mode = 0b01
spi.bits_per_word = 8
spi.max_speed_hz = 500000

angle1 = 3000
angle2 = 4560
to_send = [int(angle1 / 256), angle1 % 256, int(angle2 / 256), angle2 % 256]

for i in range(len(to_send)):
    print(hex(to_send[i]))

spi.xfer(to_send)

# received = spi.transfer([0x11, 0x22, 0xFF])
# received = spi.read(10)
