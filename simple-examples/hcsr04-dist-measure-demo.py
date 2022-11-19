## From https://github.com/andrey-git/micropython-hcsr04
## To measure distance
## using: Ultrasonic Distance Sensor - 3V or 5V - HC-SR04 compatible - RCWL-1601
##    https://www.adafruit.com/product/4007

import machine
import time

from hcsr04 import HCSR04
sensor = HCSR04(trigger_pin=10, echo_pin=11)

import neopixel
# 8 LED strip connected to X7.
p = machine.Pin(7, machine.Pin.OUT) #.board.X7
n = neopixel.NeoPixel(p, 8)

lo = 0
hi = 4200
curr = 0

while True:
  try:
    distance = sensor.distance_mm()
    print('Distance:', distance, 'mm')
    k = int((max(distance,lo)-lo)/(hi-lo)*8)
    print('k', k)
    for i in range(8):
      if i <= k:
        n[i] = (100,100,100)
      else:
        n[i] = (0,0,0)
  except:
    print('Out of range')
    for i in range(8):
      n[i] = (100,0,0)

  n.write()
  time.sleep_ms(500)
