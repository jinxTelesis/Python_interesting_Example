# https://github.com/mikr/pyqtboiler/blob/master/baseapp/utils/hotswap.py
# see if you can understand that

import imp # are these standard
import time # that standard
import hashlib # is this standard
import threading # is this standard
import logging

logger = logging.getLogger("")

class MonitorThread(threading.Thread):
    def __init__(self, engine, frequency=1):
        super(MonitorThread, self).__init__()
        self.engine = engine
        self.frequency = frequency
        # daemonize the thread so that it ends with the master program
        self.daemon = True 

    def run(self):
        while True:
            with open(self.engine.source, "rb") as fp:
                fingerprint = hashlib.sha1(fp.read()).hexdigest()
            if not fingerprint == self.engine.fingerprint:
                self.engine.notify(fingerprint)
            time.sleep(self.frequency)

class Engine(object):
    def __init__(self, source):
        # store the path to the engine source
        self.source = source        
        # load the module for the first time and create a fingerprint
        # for the file
        self.mod = imp.load_source("source", self.source)
        with open(self.source, "rb") as fp:
            self.fingerprint = hashlib.sha1(fp.read()).hexdigest()
        # turn on monitoring thread
        monitor = MonitorThread(self)
        monitor.start()

    def notify(self, fingerprint):
        logger.info("received notification of fingerprint change ({0})".\
                        format(fingerprint))
        self.fingerprint = fingerprint
        self.mod = imp.load_source("source", self.source)

    def __getattr__(self, attr):
        return getattr(self.mod, attr)

def main():
    logging.basicConfig(level=logging.INFO, 
                        filename="hotswap.log")
    engine = Engine("engine.py")
    # this silly loop is a sample of how the program can be running in
    # one thread and the monitoring is performed in another.
    while True:
        engine.f1()
        engine.f2()
        time.sleep(1)


if __name__ == "__main__":
    main()
    