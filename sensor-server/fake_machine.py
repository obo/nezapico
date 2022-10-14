class Pin:
    OUT = 0 # fake value
    def __init__(self, *args):
        print("FAKE machine Pin ", args)
    def value(self, *args):
        print("FAKE machine Pin value ", args)

class ADC:
    def __init__(self, *args):
        print("FAKE machine ADC ", args)
    def read_u16(self, *args):
        print("FAKE machine ADC read_u16 ", args)
        return 0

class WDT:
    def __init__(self, *args):
        print("FAKE machine WDT ", args)
        

