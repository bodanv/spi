import spi
spi = SPI("/dev/spidev1.0")
spi.mode = SPI.MODE_0
spi.bits_per_word = 8
spi.speed = 500000

angle = 30

spi.write([0x00, 0x00, 0x00, hex(angle)])

# received = spi.transfer([0x11, 0x22, 0xFF])
# received = spi.read(10)