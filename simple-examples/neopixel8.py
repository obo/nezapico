import neopixel
import machine

# 8 LED strip connected to X7.
p = machine.Pin(7, machine.Pin.OUT) #.board.X7
n = neopixel.NeoPixel(p, 8)

# Draw a red gradient.
for i in range(8):
    n[i] = (i * 24, 0, i*24)

# Update the strip.
n.write()
