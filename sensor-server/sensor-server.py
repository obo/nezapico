try:
    import rp2
    import ubinascii
    import machine
    import onewire, ds18x20
    on_raspberry = True
except:
    import fake_machine as machine
    import fake_ds18x20 as ds18x20
    import fake_onewire as onewire
    on_raspberry = False
try:
    if on_raspberry:
        # on raspberry, we need network
        import network
        import urequests as requests
        # load custom credentials
        from secrets import secrets
    else:
        import requests
    import socket
    can_network = True
except:
    print("CANNOT NETWORK")
    can_network = False
import time
import select
try:
    import RGB1602 # the display
    # https://www.waveshare.com/wiki/LCD1602_RGB_Module#Download_the_demo
    # Then I flashed the .uf2 file onto pico
    #  (i.e. connect USB while holding the bootsel button and then copy the file to pico)
    can_display = True
except:
    can_display = False


relayPIN = 14
thermoPIN = 15


class Stats:
    def __init__(self):
        # for uptime
        self.starttime = time.time()
        self.heating_runtime_sum = 0
        self.heating_starttime = None
    def uptime_hours(self):
        return (time.time() - self.starttime)/3600
    def start_heating(self):
        if self.heating_starttime is None:
            self.heating_starttime = time.time()
    def stop_heating(self):
        if self.heating_starttime is None:
            print("BUG! stopping without having started")
        else:
            self.heating_runtime_sum += time.time()-self.heating_starttime
        self.heating_starttime = None
    def operated_hours(self):
        current_segment = 0 if self.heating_starttime is None else time.time()-self.heating_starttime
        return (self.heating_runtime_sum + current_segment)/3600

class Params:
    # constants and decisions about heating
    def __init__(self):
        self.min_runtime_minutes = 3
          # do not run heating for less than 3 minutes
        self.min_stoptime_minutes = 10
          # do not stop hearing for less than 10 minutes
    def decide_if_heat(self, temps):
        # decide if we should heat
        should_heat = (temps.houseTemp < 15 and temps.waterTemp > 50)
        if not should_heat:
            # second option: heat if house is cold
            should_heat = (temps.houseTemp < 10 and temps.waterTemp > 40)
        if not should_heat:
            # safety option: if water too hot, free the capacity regardless
            # house temperature
            should_heat = (temps.waterTemp > 80)
        ## Debugging heating: every 10 seconds switch on and off
        #should_heat = (time.time() - stats.starttime) % 20 < 10
        return should_heat

class Display:
    def __init__(self):
        if can_display:
            self.lcd = RGB1602.RGB1602(16,2)
        self.rotation_state = 0
    def set_color_for_failure(self):
        if can_display:
            # failure is yellow, not green, not blue, not red
            self.lcd.setRGB(255, 255, 0)
    def set_color_by_temperature(self, temp):
        # temperatures above "nice" level are red (we get hot showers)
        # the max value is fully red
        # the min value is fully blue (but for readability, we keep read at 100
        nicetemp = 40 # anything above this goes for read
        maxtemp = 60 # this is boiling
        mintemp = 20
        if temp <= nicetemp:
            # going blue, red at 100, blue between 255 and 0
            red = 100
            blue = int(255-255*(temp-mintemp)/(nicetemp-mintemp))
        else:
            # going red, between 100 and 255
            blue = 0
            red = int(100+(255-100)*(temp-nicetemp)/(nicetemp-mintemp))
        print(red, blue, 0)
        red = max(0, min(255, red))
        blue = max(0, min(255, blue))
        print(red, blue, 0)
        if can_display:
            self.lcd.setRGB(red, 0, blue)
    def report(self, stats, mynetwork, temps, heating, should_heat):
        if temps.waterRomIDX == -1:
            self.set_color_for_failure()
            water = '??'
        else:
            self.set_color_by_temperature(temps.waterTemp)
            water = '%2.0f' % (temps.waterTemp)
        if temps.houseRomIDX == -1:
            house = '??'
            house = '%2.0f' % (temps.boardTemp)
        else:
            house = '%2.0f' % (temps.houseTemp)
        line1 = 'Water '+water+' Room '+house
        
        if can_display:
            self.lcd.setCursor(0,0)
            self.lcd.printout(line1)
        up = int(stats.uptime_hours()/24)
        upstr = '99+' if up > 99 else '%2id' % up
        if can_network:
            if mynetwork.got_wlan:
                if mynetwork.got_socket:
                    wifistr = ' OK'
                else:
                    wifistr = 'BAD'
            else:
                wifistr = ' no'
        else:
            wifistr = ' --'
        if heating and should_heat:
            # rotstates = '-\|/' # backslash not available
            rotstates = '<^>v'
            self.rotation_state += 1
            self.rotation_state %= 4
            heatstr = rotstates[self.rotation_state]
        elif heating and not should_heat:
            heatstr =  'v' # will stop
        elif not heating and should_heat:
            heatstr =  '^' # will start
        else:
            heatstr = '.'
        line2 = 'up'+upstr+',wifi'+wifistr+'  '+heatstr
        
        if can_display:
            self.lcd.setCursor(0,1)
            self.lcd.printout(line2)
#  0123456789012345
#  Water 43 Room 22
#  up99+,wifi OK  -\|/-\|/
        

lcd=Display()
lcd.set_color_for_failure()

class Heating:
    def __init__(self, relayPIN, params):
        # Main relay for controlling the output
        self.relay = machine.Pin(relayPIN, machine.Pin.OUT)
        self.relay.value(0) # switch off by default
        self.heating_running = False
        self.lastONtime = 0 # when did I last turn the heating on
        self.lastOFFtime = 0 # when did I last turn the heating off
        self.params = params
    
    def set_heating(self, stats, should_heat, now = time.time()):
        # start or stop heating, but only if not switched too recenlty
        if self.heating_running:
            if not should_heat:
                if now - self.lastONtime > params.min_runtime_minutes*60:
                    # do not run less than 3 minutes
                    self.lastOFFtime = now
                    self.relay.value(0)
                    self.heating_running = False
                    stats.stop_heating()
        else:
            # heating not running
            if should_heat:
                if now - self.lastOFFtime > params.min_stoptime_minutes*60:
                    # do not pause for less than 10 minutes
                    self.lastONtime = now
                    ## self.relay.value(1)
                    ## DEBUG!! NESPOUSTIM
                    self.heating_running = True
                    stats.start_heating()
class FakeHeating (Heating):
    def __init__(self, relayPIN, params):
        print("FAKE Heating")
    def set_heating(**kwargs):
        print("FAKE set_heating")
        

params = Params()

heating = Heating(relayPIN, params)
# if on_raspberry:
#     heating = Heating(relayPIN, params)
# else:
#     heating = FakeHeating(relayPIN, params)


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

class DelayedWatchdog:
    # start the real hardware watchdog only after 5 minutes, for easier
    # debugging
    def __init__(self):
        self.watchdog = None
        self.inittime = time.time()
    def feed(self):
        if self.watchdog:
            self.watchdog.feed()
        else:
            if time.time() - self.inittime > 60*3:
                self.watchdog = machine.WDT(timeout=5*60*1000)
                # auto reboot when dead for more than a minute


# hardware watchdog
watchdog = DelayedWatchdog()



class MyNetwork:
    def __init__(self):
        if on_raspberry:
            self.got_wlan = False
            self.use_port = 80
        else:
            # assuming network is provided
            self.got_wlan = True
            self.use_port = 8080
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
            watchdog.feed() # this must be called regularly

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
                addr = socket.getaddrinfo('0.0.0.0', self.use_port)[0][-1]
                print('Listening on', addr)
                
                s = socket.socket()
                # s.setsockopt(s.SOL_SOCKET, s.SO_REUSEADDR,1)
                      # this is not defined on micropython
                s.bind(addr)
                s.listen(1)
                self.socket = s
                self.got_socket = True
            except:
                self.socket = 0
                print('Failed to get listening socket')
                self.got_socket = False

    def handle_network_requests(self, stats, temps, heating, should_heat):
        # handle network requests
        if can_network:
            if not self.got_socket:
                self.get_listening_socket()

            if self.got_socket:
                self.respond_on_socket(stats, temps, heating, should_heat)

    def respond_on_socket(self, stats, temps, heating, should_heat):
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
              response = response.replace('HeatingRunning', str(heating))
              response = response.replace('UptimeHours', str(stats.uptime_hours()))
              response = response.replace('OperationHours', str(stats.operated_hours()))
            
              if on_raspberry:
                cl.send('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
                cl.send(response)
              else:
                cl.send(b'HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
                cl.send(response.encode())
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
print('Before network')
mynetwork = MyNetwork()
print('After network')


# Listen for connections, with a non-blocking socket.accept
sleeptime = 1.5 # seconds
tempreaddelay = 5 # seconds
lastreadtime = time.time()
should_heat = None
stats = Stats()
while True:
    watchdog.feed() # this must be called regularly
    print('Idling...', 'Water: ', temps.waterTemp, '; House: ', temps.houseTemp, '; Board: ', temps.boardTemp, '; Up: ', stats.uptime_hours(), '; HoursOperated: ', stats.operated_hours())
    now = time.time()
    #print('now: ', now, ', diff: ', now-lastreadtime)
    if now - lastreadtime > tempreaddelay:
        temps.update()
        #houseTemp = ds_sensor.read_temp(thermoHouse)
        #waterTemp = ds_sensor.read_temp(thermoWater)
        lastreadtime = now
        # Consider heating
        should_heat = params.decide_if_heat(temps)
        heating.set_heating(stats, should_heat, now)
        print('Read temperatures, should heat? ', should_heat, '; heating running? ', heating.heating_running)
    
    lcd.report(stats, mynetwork, temps, heating.heating_running, should_heat)
    if can_network:
        mynetwork.handle_network_requests(stats, temps, heating.heating_running, should_heat)
    else:
        time.sleep(sleeptime)
