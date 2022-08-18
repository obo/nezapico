from picozero import pico_led
from machine import Timer

timer = Timer()

def blink(timer):
    pico_led.toggle()

timer.init(freq=2.5, mode=Timer.PERIODIC, callback=blink)