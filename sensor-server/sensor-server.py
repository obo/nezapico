import rp2
try:
    import network
    import socket
    import urequests as requests
    # load custom credentials
    from secrets import secrets
    can_network = True
except:
    can_network = False
import ubinascii
import machine
import time
import select

import onewire, ds18x20

relayPIN = 14
thermoPIN = 15


# hardware watchdog
watchdog = None
#watchdog = machine.WDT(timeout=60*1000) # auto reboot when dead for more than a minute
##watchdog.feed() # this must be called regularly

class Heating:
    def __init__(self, relayPIN):
        # Main relay for controlling the output
        self.relay = machine.Pin(relayPIN, machine.Pin.OUT)
        self.relay.value(0) # switch off by default
        self.heating_running = False
        self.lastONtime = 0 # when did I last turn the heating on
        self.lastOFFtime = 0 # when did I last turn the heating off
    
    def set_heating(self, should_heat, now = time.time()):
        # start or stop heating, but only if not switched too recenlty
        if self.heating_running:
            if not should_heat:
                if now - self.lastONtime > 3*60:
                    # do not run less than 3 minutes
                    self.lastOFFtime = now
                    self.relay.value(0)
                    self.heating_running = False
        else:
            # heating not running
            if should_heat:
                if now - self.lastOFFtime > 10*60:
                    # do not pause for less than 10 minutes
                    self.lastONtime = now
                    self.relay.value(1)
                    self.heating_running = True
            
heating = Heating(relayPIN)


class Temperatures:
    def __init__(self, thermoPIN):
        self.thermoPIN = thermoPIN
        # find external thermometers
        self.find_thermometers()
        # find on-board thermometer
        self.onboard_tempsensor = machine.ADC(4)
        self.conversion_factor = 3.3 / 65535
        self.boardTemp = 0.0

        
    def find_thermometers(self):
        thermoHouse = bytearray(b'(\x956\x81\xe3w<\xec')
        thermoWater = bytearray(b'(D\xc1\x81\xe3\x8f<\x07')

        # Find thermometers
        ds_pin = machine.Pin(self.thermoPIN)
        self.ds_sensor = ds18x20.DS18X20(onewire.OneWire(ds_pin))
        self.roms = self.ds_sensor.scan()
        print('Found DS devices (thermometers): ', self.roms)
        self.houseRomIDX = -1
        self.waterRomIDX = -1
        for i in range(len(self.roms)):
            self.houseRomIDX = i if self.roms[i] == thermoHouse else self.houseRomIDX
            self.waterRomIDX = i if self.roms[i] == thermoWater else self.waterRomIDX
        #assert self.houseRomIDX != -1, "Failed to find house thermometer"
        #assert self.waterRomIDX != -1, "Failed to find water thermometer"
        if self.houseRomIDX == -1:
            print("Failed to find house thermometer")
        if self.waterRomIDX == -1:
            print("Failed to find water thermometer")
        self.found_thermometers = self.houseRomIDX != -1 and self.waterRomIDX != -1
        self.houseTemp = 0.0
        self.waterTemp = 0.0
    def update(self):
        data = self.onboard_tempsensor.read_u16() * self.conversion_factor
        self.boardTemp = 27-(data-0.706)/0.001721
        if self.found_thermometers:
            # some strange waiting needed
            self.ds_sensor.convert_temp()
            time.sleep_ms(750)
            temps = [self.ds_sensor.read_temp(rom) for rom in self.roms]
            #print(temps)
            self.houseTemp = temps[self.houseRomIDX]
            self.waterTemp = temps[self.waterRomIDX]
        else:
            print("Retrying to find thermometers")
            self.find_thermometers()

temps = Temperatures(thermoPIN)
print('House temp: ', temps.houseTemp)
print('Water temp: ', temps.waterTemp)
print('Board temp: ', temps.boardTemp)

temps.update()
print('House temp: ', temps.houseTemp)
print('Water temp: ', temps.waterTemp)
print('Board temp: ', temps.boardTemp)

#print(ds_sensor.read_temp(houseTemp))

class MyNetwork:
    def __init__(self):
        self.got_wlan = False
        self.get_listening_socket()

    def get_wlan(self):
        if can_network:
            try:
                self.initialize_wlan()
                self.got_wlan = True
            except:
                self.got_wlan = False
        else:
            self.got_wlan = False

    def initialize_wlan(self):
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
            #raise RuntimeError('Wi-Fi connection failed')
            print('Wi-Fi connection failed')
            got_wlan = False
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
            got_wlan = True
        self.wlan = wlan

    def get_listening_socket(self):
        if not self.got_wlan:
            # try setting up wlan again
            print('Trying to get wlan')
            self.get_wlan()
        # and if we got it, try to get the socket
        if self.got_wlan:
            try:
                # HTTP server with socket
                addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
                print('Listening on', addr)
                
                s = socket.socket()
                # s.setsockopt(s.SOL_SOCKET, s.SO_REUSEADDR,1)
                      # this is not defined on micropython
                s.bind(addr)
                s.listen(1)
                self.socket = s
            except:
                self.socket = None

    def handle_network_requests(self, uptimehours, temps, heating, should_heat):
        # handle network requests
        if can_network:
            if self.socket is None:
                self.get_listening_socket()

            if self.socket is not None:
                self.respond_on_socket(uptimehours, temps, heating, should_heat)

    def respond_on_socket(self, uptimehours, temps, heating, should_heat):
        # knowing that socket is ready, check connections
        try:
          read_list = [self.socket] # which sockets to check
          readable, writable, errored = select.select(read_list, [], [], sleeptime)
          for s1 in readable:
            if s1 is self.socket:
              cl, addr = self.socket.accept()
              print('Client connected from', addr)
              cl_file = cl.makefile('rwb', 0)
              while True:
                  line = cl_file.readline()
                  if not line or line == b'\r\n':
                      break
                
              response = get_html('index.html')
              response = response.replace('TempH', str(temps.houseTemp))
              response = response.replace('TempW', str(temps.waterTemp))
              response = response.replace('HeatingShould', str(should_heat))
              response = response.replace('HeatingRunning', str(heating.heating_running))
              response = response.replace('UptimeHours', str(uptimehours))
            
              cl.send('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
              cl.send(response)
              cl.close()
              print('Done serving')
        except OSError as e:
            cl.close()
            print('Connection closed')


# Function to load in html page    
def get_html(html_name):
    with open(html_name, 'r') as file:
        html = file.read()
    return html

# initialize my failsafe networking
mynetwork = MyNetwork()

# Listen for connections, with a non-blocking socket.accept
sleeptime = 1.5 # seconds
tempreaddelay = 5 # seconds
lastreadtime = time.time()
starttime = lastreadtime
should_heat = None
while True:
    if watchdog:
        watchdog.feed() # this must be called regularly
    print('Idling...', 'Water: ', temps.waterTemp, '; House: ', temps.houseTemp, '; Board: ', temps.boardTemp)
    now = time.time()
    uptimehours = (now - lastreadtime)/3600
    #print('now: ', now, ', diff: ', now-lastreadtime)
    if now - lastreadtime > tempreaddelay:
        temps.update()
        #houseTemp = ds_sensor.read_temp(thermoHouse)
        #waterTemp = ds_sensor.read_temp(thermoWater)
        lastreadtime = now
        # Consider heating
        should_heat = (temps.houseTemp < 20 and temps.waterTemp > 40)
        heating.set_heating(should_heat, now)
        print('Read temperatures, should heat? ', should_heat, '; heating running? ', heating.heating_running)
    
    if can_network:
        mynetwork.handle_network_requests(uptimehours, temps, heating, should_heat)
    else:
        time.sleep(sleeptime)
