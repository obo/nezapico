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
    import json
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
paramsFilename = "parameters.txt"


class Stats:
    def __init__(self):
        # for uptime
        self.starttime = time.time()
        self.heating_runtime_sum = 0
        self.heating_starttime = None
        self.electric_runtime_sum = 0
        self.electric_starttime = None
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

    def monitor_electric_heating(self, electric_running):
        if electric_running:
            if self.electric_starttime is None:
                self.electric_starttime = time.time()
            else:
                pass
                # print("Electric heating running")
        else: # electric_not_running
            if self.electric_starttime is None:
                pass
                # print("Electric heating not running")
            else:
                self.electric_runtime_sum += time.time()-self.electric_starttime
                self.electric_starttime = None
    def electric_operated_hours(self):
        current_segment = 0 if self.electric_starttime is None else time.time()-self.electric_starttime
        return (self.electric_runtime_sum + current_segment)/3600

def ucfirst(s):
    return s[0].upper() + s[1:]

class Params:
    # constants and decisions about heating
    def __init__(self):
        self.min_runtime_minutes = 3
          # do not run heating for less than 3 minutes
        self.min_stoptime_minutes = 10
          # do not stop hearing for less than 10 minutes
        self.desiredHouseMin = 20
          # start heating if house below this
        self.desiredWaterMin = 50
          # stop heating if water below this
        self.desiredWaterMinNeverSaveLessThanThis = 33
          # for safety reasons, never save lower value for water than this
        try:
            infile = open(paramsFilename, "r")
            params = json.load(infile)
            infile.close()
            print("Loaded saved params: ", params)
            self.desiredWaterMin = params["desiredWaterMin"];
            self.desiredHouseMin = params["desiredHouseMin"];
        except:
            print("Failed to load params, using defaults.")
    def store_params(self, desiredHouseMin=None, desiredWaterMin=None):
        if desiredWaterMin is not None:
            self.desiredWaterMin = desiredWaterMin
        if desiredHouseMin is not None:
            self.desiredHouseMin = desiredHouseMin
        # safe param values to a file
        data = {
          "desiredHouseMin": self.desiredHouseMin,
          "desiredWaterMin": self.desiredWaterMin if self.desiredWaterMin > self.desiredWaterMinNeverSaveLessThanThis else self.desiredWaterMinNeverSaveLessThanThis,
        }
        outfile = open(paramsFilename, "w")
        json.dump(data, outfile)
        outfile.close()
    def decide_if_heat(self, temps):
        house = temps.temperatures["house"]
        if house is None: return False
        water = temps.temperatures["water"]
        if water is None: return False
        # decide if we should heat
        should_heat = (house < self.desiredHouseMin and water > self.desiredWaterMin)
        #if not should_heat:
        #    # second option: heat if house is cold
        #    should_heat = (temps.houseTemp < 10 and temps.waterTemp > 40)
        if not should_heat:
            # safety option: if water too hot, free the capacity regardless
            # house temperature
            should_heat = (water > 55)
        ## Debugging heating: every 10 seconds switch on and off
        #should_heat = (time.time() - stats.starttime) % 20 < 10
        return should_heat

class Display:
    def __init__(self):
        global can_display
        if can_display:
            try:
                self.lcd = RGB1602.RGB1602(16,2)
            except:
                print("Failed to init display, disabling.")
                can_display = False
        self.rotation_state = 0
    def set_color_for_failure(self):
        global can_display
        if can_display:
            # failure is yellow, not green, not blue, not red
            try:
                self.lcd.setRGB(255, 255, 0)
            except:
                print("Disabling display, some error")
                can_display = False
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
        red = max(0, min(255, red))
        blue = max(0, min(255, blue))
        if can_display:
            self.lcd.setRGB(red, 0, blue)
    def report(self, stats, mynetwork, temps, heating, should_heat):
        if temps.temperatures["water"] is None:
            self.set_color_for_failure()
            water = '??'
        else:
            self.set_color_by_temperature(temps.temperatures["water"])
            water = '%2.0f' % (temps.temperatures["water"])
        if temps.temperatures["house"] is None:
            house = '??'
            house = '%2.0f' % (temps.boardTemp)
        else:
            house = '%2.0f' % (temps.temperatures["house"])
        line1 = 'Water '+water+' Room '+house
        
        print("[[", line1, "]]")
        if True and can_display:
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
        guessed_electric = heating.guess_electric_heating_running(temps)
        if guessed_electric:
            rotstates = 'Elec' # we are guessing that the electric heating is on
        elif heating.heating_running and should_heat:
            # rotstates = '-\|/' # backslash not available
            rotstates = '<^>v'
        elif heating.heating_running and not should_heat:
            rotstates = 'v_v_' # will stop
        elif not heating.heating_running and should_heat:
            rotstates = '^.^.' # will start
        else:
            rotstates = '. . '
        self.rotation_state += 1
        self.rotation_state %= 4
        heatstr = rotstates[self.rotation_state]
        line2 = 'up'+upstr+',wifi'+wifistr+'  '+heatstr
        
        print("[[", line2, "]]")
        if True and can_display:
            self.lcd.setCursor(0,1)
            self.lcd.printout(line2)
#  0123456789012345
#  Water 43 Room 22
#  up99+,wifi OK  -\|/-\|/
#
#  Alternative ideas:
#  0123456789012345
#  W 43<50, R 22>10
#  W 50>50, R  8<10
#  up99+,wifi OK  -\|/-\|/
        

lcd=Display()
lcd.set_color_for_failure()

class Heating:
    def __init__(self, relayPIN, watchdog, params):
        # Main relay for controlling the output
        self.relay = machine.Pin(relayPIN, machine.Pin.OUT)
        self.relay.value(0) # switch off by default
        self.heating_running = False
        self.lastONtime = 0 # when did I last turn the heating on
        self.lastOFFtime = 0 # when did I last turn the heating off
        self.params = params
        self.watchdog = watchdog
    
    def guess_electric_heating_running(self, temps):
        # guess based on temp differences if electric heating is on
        intemp = temps.temperatures["heaterIn"]
        outtemp = temps.temperatures["heaterOut"]
        if intemp is None or outtemp is None:
            return None
        return (outtemp - intemp > 27) # more than 7 degrees means heating

    def set_heating(self, stats, temps, should_heat, now = time.time()):
        # start or stop heating, but only if not switched too recently
        # immediately stop our heating if we diagnose that electric
        # heating is on

        electric_guessed = self.guess_electric_heating_running(temps)
        stats.monitor_electric_heating(electric_guessed)

        # first check if electric heating is on
        if False and electric_guessed: # DISABLED
            # immediate stop!
            self.lastOFFtime = now
            self.relay.value(0)
            self.heating_running = False
            stats.stop_heating()
        elif self.heating_running:
            if not should_heat:
                if now - self.lastONtime > params.min_runtime_minutes*60:
                    # do not run less than 3 minutes
                    self.lastOFFtime = now
                    self.watchdog.start_immediately()
                    self.relay.value(0)
                    self.heating_running = False
                    stats.stop_heating()
        else:
            # heating not running
            if should_heat:
                if now - self.lastOFFtime > params.min_stoptime_minutes*60:
                    # do not pause for less than 10 minutes
                    self.lastONtime = now
                    self.watchdog.start_immediately()
                    self.relay.value(1)
                    self.heating_running = True
                    stats.start_heating()

class DelayedWatchdog:
    # start the real hardware watchdog only after 1 minutes, for easier
    # debugging
    def __init__(self):
        self.watchdog = None
        self.inittime = time.time()
    def start_immediately(self):
        if not self.watchdog:
            self.watchdog = machine.WDT(timeout=8388)
            # strangely only 8 secs allowed, not my previous value: 5*60*1000)
    def feed(self):
        if self.watchdog:
            self.watchdog.feed()
        else:
            if time.time() - self.inittime > 60*3:
                self.start_immediately()
                # auto reboot when dead for more than a minute


# hardware watchdog
watchdog = DelayedWatchdog()

params = Params()

heating = Heating(relayPIN, watchdog, params)


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
        thermometers = {
          # thermoWater:
          "water" : bytearray(b'(D\xc1\x81\xe3\x8f<\x07'),
          # thermoHouse:
          "house" : bytearray(b'(\x956\x81\xe3w<\xec'),
          "heaterIn" : bytearray(b'(du\x81\xe3\xdd<\x07'),
          "heaterOut" : bytearray(b'(\x8c\x19\x81\xe3P<\x19'),
        }

        # Find thermometers
        ds_pin = machine.Pin(self.thermoPIN)
        self.ds_sensor = ds18x20.DS18X20(onewire.OneWire(ds_pin))
        self.roms = self.ds_sensor.scan()
        # # DEBUG:
        # self.roms = [bytearray(b'(D\xc1\x81\xe3\x8f<\x07'), bytearray(b'(\x956\x81\xe3w<\xec')]
        print('Found DS devices (thermometers): ', self.roms)
        self.thermoIDX = dict.fromkeys(thermometers.keys())
          # thermometer name -> thermometer index
        for i in range(len(self.roms)):
            print("I", i)
            print("type", type(self.roms))
            print("type", type(self.roms[i]))
            r = self.roms[i]
            print("Who's this thermo?", self.roms[i])
            # can't hash bytearrays, so walk through dictionary
            t = None # this termometer's name
            for k, v in thermometers.items():
                print("  Is it?", v)
                if v == r:
                    print("  yes!", k)
                    t = k # found the thermometer
            if t is not None:
              self.thermoIDX[t] = i
            else:
              print("Found unexpected thermometer", r, "at index", i)
            # self.houseRomIDX = i if self.roms[i] == thermoHouse else self.houseRomIDX
            # self.waterRomIDX = i if self.roms[i] == thermoWater else self.waterRomIDX
        #assert self.houseRomIDX != -1, "Failed to find house thermometer"
        #assert self.waterRomIDX != -1, "Failed to find water thermometer"
        for n in thermometers.keys():
            if self.thermoIDX[n] is None:
                print("Failed to find thermometer:", n)
        self.temperatures = dict.fromkeys(thermometers.keys())
          # thermometer name -> thermometer index
        # self.found_thermometers = self.houseRomIDX != -1 and self.waterRomIDX != -1
        # self.houseTemp = 0.0
        # self.waterTemp = 0.0
    def update(self):
        print("update called; thermometers: ", self.thermoIDX)
        data = self.onboard_tempsensor.read_u16() * self.conversion_factor
        self.boardTemp = 27-(data-0.706)/0.001721
        if len(self.roms) > 0:
            # some thermometers were found
            # some strange waiting needed
            self.ds_sensor.convert_temp()
            time.sleep_ms(750)
            temps = [self.ds_sensor.read_temp(rom) for rom in self.roms]
            print("update got temperatures: ", temps)
            for t, idx in self.thermoIDX.items():
                if idx is not None:
                    self.temperatures[t] = temps[idx]
            # self.houseTemp = temps[self.houseRomIDX]
            # self.waterTemp = temps[self.waterRomIDX]
        else:
            print("Retrying to find thermometers")
            self.find_thermometers()

temps = Temperatures(thermoPIN)
# print('House temp: ', temps.houseTemp)
# print('Water temp: ', temps.waterTemp)
# print('Board temp: ', temps.boardTemp)
# 
temps.update()
for t, temp in temps.temperatures.items():
    print('temp in', t, ':', temp)
# print('Water temp: ', temps.waterTemp)

#print(ds_sensor.read_temp(houseTemp))




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
            self.got_wlan = False
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
            self.got_wlan = True
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
                print('Will be listening on', addr)
                
                s = socket.socket()
                # s.setsockopt(s.SOL_SOCKET, s.SO_REUSEADDR,1)
                      # this is not defined on micropython
                s.bind(addr)
                s.listen(1)
                print('Listening on', addr)
                self.socket = s
                self.got_socket = True
            except:
                self.socket = 0
                print('Failed to get listening socket')
                self.got_socket = False

    def handle_network_requests(self, stats, temps, heating, should_heat):
        # handle network requests; return True if we got a request
        if can_network:
            if not self.got_socket:
                self.get_listening_socket()

            if self.got_socket:
                got_a_request = self.respond_on_socket(stats, temps, heating, should_heat)
                print('Got a network request?', got_a_request)
                return got_a_request

    def respond_on_socket(self, stats, temps, heating, should_heat):
        # knowing that socket is ready, check connections
        # return True if got a contact
        try:
          read_list = [self.socket] # which sockets to check
          readable, writable, errored = select.select(read_list, [], [], sleeptime)
          for s1 in readable:
            if s1 is self.socket:
              cl, addr = self.socket.accept()
              print('Client connected from', addr)

              query = cl.recv(1024)
              print('QUERY:', query)
              
              query = str(query)
              
              # QUERY: b'GET /?house=30&water=24&Save=Save HTTP/1.1\r\nHost: localhost:...
              start = query.find('GET /?') + 6
              end = query.find('HTTP', start)
              args = query[start:end]
              print('ARGS:', args)
              try:
                pairs = dict([pair.split('=') for pair in args.split('&')])
              except:
                pairs = {}
              print('PAIRS:', pairs) # the args that we received
              try:
                queryHouse = 0+int(pairs["house"])
              except:
                queryHouse = params.desiredHouseMin
              try:
                queryWater = 0+int(pairs["water"])
              except:
                queryWater = params.desiredWaterMin

              params.store_params(desiredHouseMin=queryHouse, desiredWaterMin=queryWater)

### OLD, reading all input
#               cl_file = cl.makefile('rwb', 0)
#               while True:
#                   line = cl_file.readline()
#                   if not line or line == b'\r\n':
#                       break
              guessed_electric = heating.guess_electric_heating_running(temps)
              
              tempsStr = " | ".join([("%s: %s"%(ucfirst(n), "%.1f"%t if t is not None else "--"))
                for n, t in temps.temperatures.items()])

              response = get_html('index.html')
              response = response.replace('TempsStr', str(tempsStr))
              # response = response.replace('TempW', str(temps.temperatures["water"]))
              response = response.replace('DefaultHouseQuery', str(queryHouse))
              response = response.replace('DefaultWaterQuery', str(queryWater))
              response = response.replace('HeatingShould', str(should_heat))
              response = response.replace('HeatingRunning', str(heating.heating_running))
              response = response.replace('ElectricRunning', str(guessed_electric))
              response = response.replace('UptimeHours', str(stats.uptime_hours()))
              response = response.replace('OperationHours', str(stats.operated_hours()))
              response = response.replace('ElectricHours', str(stats.electric_operated_hours()))
            
              if on_raspberry:
                cl.send('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
                cl.send(response)
              else:
                cl.send(b'HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
                cl.send(response.encode())
              cl.close()
              print('Done serving')
              return True
          return False
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
sleeptime = 1.0 # seconds
tempreaddelay = 5 # seconds
lastreadtime = time.time()
lastcontactedtime = None
should_heat = None
stats = Stats()
while True:
    watchdog.feed() # this must be called regularly
    print('Idling...', " ".join([("%s:%s"%(n, "%.1f"%t if t is not None else "--"))
    for n, t in temps.temperatures.items()]))
    # ]'Water: ', temps.temps["water"], '; House: ', temps.houseTemp, '; Board: ', temps.boardTemp, '; Up: ', stats.uptime_hours(), '; HoursOperated: ', stats.operated_hours())
    now = time.time()
    #print('now: ', now, ', diff: ', now-lastreadtime)
    if now - lastreadtime > tempreaddelay:
        temps.update()
        #houseTemp = ds_sensor.read_temp(thermoHouse)
        #waterTemp = ds_sensor.read_temp(thermoWater)
        lastreadtime = now
        # Consider heating
        should_heat = params.decide_if_heat(temps)
        heating.set_heating(stats, temps, should_heat, now)
        print('Read temperatures, should heat? ', should_heat, '; heating running? ', heating.heating_running)
    
    try:
        lcd.report(stats, mynetwork, temps, heating, should_heat)
    except:
        print(" !!! Error reporting to the display")
    if can_network:
        got_a_request = mynetwork.handle_network_requests(stats, temps, heating, should_heat)
        if got_a_request:
            lastcontactedtime = now
    time.sleep(sleeptime)
    if stats.uptime_hours() > 48:
        # safety reset every two days
        os.system("sudo reboot")
    if lastcontactedtime is not None and now - lastcontactedtime > 60*30:
        # safety reset after 30 mins of no contact with outside world
        os.system("sudo reboot")
    if lastcontactedtime is None and stats.uptime_hours() > 0.5:
        # safety reset every 30 mins of no contact
        os.system("sudo reboot")
