import rp2
import network
import ubinascii
import machine
import urequests as requests
import time
from secrets import secrets
import socket
import select

import onewire, ds18x20

# Main relay for controlling the output
rele = machine.Pin(16, machine.Pin.OUT)
rele.value(0) # switch off by default


class Temperatures:
    def __init__(self):
        thermoHouse = bytearray(b'(\x956\x81\xe3w<\xec')
        thermoWater = bytearray(b'(D\xc1\x81\xe3\x8f<\x07')

        # Find thermometers
        ds_pin = machine.Pin(22)
        self.ds_sensor = ds18x20.DS18X20(onewire.OneWire(ds_pin))
        self.roms = self.ds_sensor.scan()
        print('Found DS devices (thermometers): ', self.roms)
        self.houseRomIDX = -1
        self.waterRomIDX = -1
        for i in range(len(self.roms)):
            self.houseRomIDX = i if self.roms[i] == thermoHouse else self.houseRomIDX
            self.waterRomIDX = i if self.roms[i] == thermoWater else self.waterRomIDX
        assert self.houseRomIDX != -1, "Failed to find house thermometer"
        assert self.waterRomIDX != -1, "Failed to find water thermometer"
        self.houseTemp = 0.0
        self.waterTemp = 0.0
    def update(self):
      # some strange waiting needed
      self.ds_sensor.convert_temp()
      time.sleep_ms(750)
      #for rom in self.roms:
      #  print(rom)
      #  print(self.ds_sensor.read_temp(rom))
      temps = [self.ds_sensor.read_temp(rom) for rom in self.roms]
      #print(temps)
      self.houseTemp = temps[self.houseRomIDX]
      self.waterTemp = temps[self.waterRomIDX]

temps = Temperatures()
print('House temp: ', temps.houseTemp)
print('Water temp: ', temps.waterTemp)

temps.update()
print('House temp: ', temps.houseTemp)
print('Water temp: ', temps.waterTemp)

#print(ds_sensor.read_temp(houseTemp))

# Set country to avoid possible errors
rp2.country('CZ')

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
# If you need to disable powersaving mode
# wlan.config(pm = 0xa11140)

# See the MAC address in the wireless chip OTP
mac = ubinascii.hexlify(network.WLAN().config('mac'),':').decode()
print('mac = ' + mac)

# Other things to query
# print(wlan.config('channel'))
# print(wlan.config('essid'))
# print(wlan.config('txpower'))

# Load login data from different file for safety reasons
ssid = secrets['ssid']
pw = secrets['pw']

wlan.connect(ssid, pw)

# Wait for connection with 10 second timeout
timeout = 10
while timeout > 0:
    if wlan.status() < 0 or wlan.status() >= 3:
        break
    timeout -= 1
    print('Waiting for connection...')
    time.sleep(1)
    
# Handle connection error
# Error meanings
# 0  Link Down
# 1  Link Join
# 2  Link NoIp
# 3  Link Up
# -1 Link Fail
# -2 Link NoNet
# -3 Link BadAuth
if wlan.status() != 3:
    raise RuntimeError('Wi-Fi connection failed')
else:
    led = machine.Pin('LED', machine.Pin.OUT)
    for i in range(wlan.status()):
        led.on()
        time.sleep(0.2)
        led.off()
        time.sleep(0.2)
    print('Connected')
    status = wlan.ifconfig()
    print('ip = ' + status[0])
    
# Function to load in html page    
def get_html(html_name):
    with open(html_name, 'r') as file:
        html = file.read()
        
    return html



# HTTP server with socket
addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]

s = socket.socket()
# s.setsockopt(s.SOL_SOCKET, s.SO_REUSEADDR,1) # is not defined on micropython
s.bind(addr)
s.listen(1)

print('Listening on', addr)

# Listen for connections, with a non-blocking socket.accept
read_list = [s] # which sockets to check
sleeptime = 1.5 # seconds
tempreaddelay = 5 # seconds
lastreadtime = time.time()
while True:
    print('Idling...', 'Water: ', temps.waterTemp, '; House: ', temps.houseTemp)
    now = time.time()
    #print('now: ', now, ', diff: ', now-lastreadtime)
    if now - lastreadtime > tempreaddelay:
        temps.update()
        #houseTemp = ds_sensor.read_temp(thermoHouse)
        #waterTemp = ds_sensor.read_temp(thermoWater)
        lastreadtime = now
        # Consider heating
        do_heat = (temps.houseTemp < 25 and temps.waterTemp > 26)
        rele.value(1 if do_heat else 0)
        print('Read temperatures, should heat? ', do_heat)
    try:
      readable, writable, errored = select.select(read_list, [], [], sleeptime)
      for s1 in readable:
        if s1 is s:
          cl, addr = s.accept()
          print('Client connected from', addr)
          cl_file = cl.makefile('rwb', 0)
          while True:
              line = cl_file.readline()
              if not line or line == b'\r\n':
                  break
            
          response = get_html('index.html')
          response = response.replace('TempH', str(temps.houseTemp))
          response = response.replace('TempW', str(temps.waterTemp))
        
          cl.send('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
          cl.send(response)
          cl.close()
          print('Done serving')
    except OSError as e:
        cl.close()
        print('Connection closed')
