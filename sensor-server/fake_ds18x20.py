class DS18X20:
    def __init__(self, *args):
        print("FAKE DS18X20 ", args)
    def scan(self, *args):
        print("FAKE DS18X20 scan ", args)
        return []
