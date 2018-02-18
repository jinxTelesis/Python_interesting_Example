@author: dremon7
'''
version = "0.3.1"
__author__ = "Michael Krause"
__email__ = "michael@krause-software.com"

#
# CREDITS
#   The idea and first implementation of the mechanism used by this module
#   was first made public by Thomas Heller in a Usenet posting
#   to comp.lang.python in 2001 (named autoreload.py).
#   Updates for new-style classes were taken from a Usenet posting
#   by Jeremy Fincher.

'''

__all__ = ['run', 'stop', 'superreload'] # package import

import time # these are libraries 
import threading
import sys
import os ## added this
import types
import imp
import getopt

PY2 = sys.version_info[0] == 2 # checks the version of python
PY3 = sys.version_info[0] == 3 # checks the version of python

try: # attempts reload not a part of later python versions
    reload
except NameError:
    from importlib import reload # 

if PY2:
    TypeType = types.TypeType
    ClassType = types.ClassType
else:
    TypeType = type
    ClassType = type

def _get_compiled_ext(): # returns ext if file is compiled # python is not compiled normally 
    for ext, mode, typ in imp.get_suffixes():
        if typ == imp.PY_COMPILED:
            return ext

# the official way to get the extension of compiled files (.pyc or .pyo)
PY_COMPILED_EXT = _get_compiled_ext()

class ModuleWatcher: # class checks if module "linked is changed"
    SECONDS_BETWEEN_CHECKS = 0.1 # timer
    SKIP_SYSTEM_MODULES = False 
    NOTIFYFUNC = None
    VERBOSE = False # changes flag to print output somewhere
    running = 0 
    def __init__(self): # equivalent to c++ this->
        # If we don't do this, there may be tracebacks
        # when shutting down python.
        import atexit
        atexit.register(self.stop) # special exit condition changes how stack reporting closes

    def run(self, skipsystem=SKIP_SYSTEM_MODULES,
                  seconds=SECONDS_BETWEEN_CHECKS,
                  notifyfunc=NOTIFYFUNC,
                  verbose=VERBOSE): # defines conditions listed about
        if self.running:
            if verbose:
                print("# hotswap already running")
            return
        self.SKIP_SYSTEM_MODULES = skipsystem
        self.SECONDS_BETWEEN_CHECKS = seconds
        self.NOTIFYFUNC = notifyfunc
        self.VERBOSE = verbose

        if self.VERBOSE:
            print("# starting hotswap seconds=%s, skipsystem=%s" \
                % (self.SECONDS_BETWEEN_CHECKS, self.SKIP_SYSTEM_MODULES))
        self.running = 1 # think this is starting a thread to monitor main
        self.thread = threading.Thread(target=self._check_modules)
        self.thread.setDaemon(1)
        self.thread.start()

    def stop(self):
        if not self.running:
            if self.VERBOSE:
                print("# hotswap not running")
            return
        self.running = 0
        self.thread.join()
        if self.VERBOSE: # this rejoins the threads when hotswap of module over
            print("# hotswap stopped")

    def _check_modules(self):
        last_modified = {} # fills a list with module changes
        while self.running:
            time.sleep(self.SECONDS_BETWEEN_CHECKS)
            for m in list(sys.modules.values()):
                if not hasattr(m, '__file__'):
                    # We only check modules that have a plain file
                    # as Python source.
                    continue
                if m.__name__ == '__main__':
                    # __main__ cannot be reloaded without executing
                    # its code a second time, so we skip it.
                    continue
                file = m.__file__ # convention for loading files when they are read into
                path, ext = os.path.splitext(file) # pythons way of opening files

                if self.SKIP_SYSTEM_MODULES:
                    # do not check system modules
                    sysprefix = sys.prefix + os.sep # avoids system files
                    if file.startswith(sysprefix):
                        continue

                if ext.lower() == '.py':
                    ext = PY_COMPILED_EXT # if its a py file sets ext

                if ext != PY_COMPILED_EXT: # if its not a py file loops back
                    continue

                sourcefile = path + '.py' # sets source file with path
                try:
                    source_mtime = os.stat(sourcefile)[8]
                    if sourcefile not in last_modified: # checks if the last source file is in list above modified
                        last_modified[sourcefile] = source_mtime # if sourcefile not fond adds
                        continue
                    else:
                        if source_mtime <= last_modified[sourcefile]: 
                            continue
                        last_modified[sourcefile] = source_mtime 
                except OSError:
                    continue # loops back up if error thrown

                try:
                    superreload(m, verbose=self.VERBOSE) # attemps to run package
                except:
                    import traceback # imports lib while running
                    traceback.print_exc(0) # prints stack exit
                try:
                    if hasattr(m, 'onHotswap') and callable(m.onHotswap): # if file has hotswap call
                        # The module can invalidate cached results or post
                        # redisplay operations by defining function named
                        # onHotswap that is called after a reload.
                        m.onHotswap()
                    if callable(self.NOTIFYFUNC):# sets a condition if callable
                        self.NOTIFYFUNC(module=m)
                except:
                    import traceback #inports trackback to printout stack exit if error
                    traceback.print_exc(0)

def update_function(old, new, attrnames): # reloads mains files function to use hotswaped module
    for name in attrnames: # cyclers through the attributes
        try:
            setattr(old, name, getattr(new, name))
        except AttributeError:
            pass ## clears errors does nothing with them

def superreload(module, # think this is what you set the reloading module to
                reload=reload, # this is a variable as a default arg
                _old_objects = {}, # mangled list of old objects
                verbose=True):
    """superreload (module) -> module

    Enhanced version of the builtin reload function.
    superreload replaces the class dictionary of every top-level
    class in the module with the new one automatically,
    as well as every function's code object.
    """
    # retrieve the attributes from the module before the reload,
    # and remember them in _old_objects.
    for name, object in module.__dict__.items(): # grabs attribute conditions aka data from old
        key = (module.__name__, name)
        _old_objects.setdefault(key, []).append(object) # makes a dictionary out of them

    if verbose: # if verbose is set 
        print("# reloading module %r" % module)
    newmodule = reload(module)
    if newmodule is None:
        return module
    # XXX We have a problem here if importing the module fails!

    # iterate over all objects and update them
    for name, new_obj in newmodule.__dict__.items():
        # print "updating", `name`, type(new_obj), `new_obj`
        key = (newmodule.__name__, name) # repopulating certain data
        if key in _old_objects:
            for old_obj in _old_objects[key]:
                if type(new_obj) == ClassType:
                    if hasattr(old_obj.__dict__, 'update'):
                        old_obj.__dict__.update(new_obj.__dict__)
                elif type(new_obj) == types.FunctionType:
                    update_function(old_obj,
                           new_obj,
                           "func_code func_defaults func_doc".split())
                elif type(new_obj) == types.MethodType:
                    update_function(old_obj.im_func,
                           new_obj.im_func,
                           "func_code func_defaults func_doc".split())

    return newmodule 

_watcher = ModuleWatcher() # changes call to mangled version

run = _watcher.run # starts stop module watching
stop = _watcher.stop

def modulename(path):
    return os.path.splitext(path)[0].replace(os.sep, '.') # just a very dynamic way of getting paths

def importmodule(filename):
    """Returns the imported module of this source file. 

    This function tries to find this source file as module
    on the Python path, so that its typical module name is used.
    If this does not work, the directory of this file is inserted
    at the beginning of sys.path and the import is attempted again.
    """ ## this is crawling up and down a python directory 
    sourcefile = os.path.abspath(filename)
    modfile = os.path.basename(sourcefile)
    # Given an absolute filename of a python source file,
    # we need to find it on the Python path to calculate its
    # proper module name.
    candidates = []
    for p in sys.path:
        pdir = p + os.sep
        checkfile = os.path.join(p, modfile)
        if os.path.normcase(sourcefile).startswith(os.path.normcase(pdir)):
            relmodfile = sourcefile[len(pdir):]
            candidates.append((len(relmodfile), relmodfile))
    if candidates:
        # Pick the most specific module path from all candidates
        candidates.sort()
        modname = modulename(candidates[0][1])
    else:
        modname = modulename(os.path.basename(sourcefile))
    try:
        # In case the source file was in the Python path
        # it can be imported now.
        module = __import__(modname, globals(), locals(), [])
    except ImportError as e:
        failed_modname = str(e).split()[-1]
        failed_modname = failed_modname.replace("'", "")
        if failed_modname == modname:
            # The ImportError wasn't caused by some nested import
            # but our module was not found, so we add the source files
            # directory to the path and import it again.
            modname = modulename(os.path.basename(sourcefile))
            sys.path.insert(0, os.path.dirname(sourcefile))
            module = __import__(modname, globals(), locals(), [])
        else:
            import traceback
            tb = sys.exc_traceback
            if tb:
                tb = tb.tb_next
            traceback.print_exception(sys.exc_type, sys.exc_value, tb)
            # The module to be imported could be found but raised an
            # ImportError itself.
            raise e # this error is not caught

    # have to deal module nesting like logging.handlers
    # before calling the modules main function.
    components = modname.split('.') 
    for comp in components[1:]:
        module = getattr(module, comp)
    return module

#----------------------------------------------------------------------------

class Usage(Exception): # sets exception message
    def __init__(self, msg):
        self.msg = msg

def usage(argv0): # prints this out on interpreter prompt
    print >>sys.stderr, """Usage: %s [OPTIONS] <module.py>
Import module and call module.main() with hotswap enabled.
Subsequent modifications in module.py and other source files of
modules being used are monitored periodically and put into effect
without restarting the program.

Options:
-h, --help                Display this help then exit.
-w, --wait                Wait number of seconds between checks. [0.1]
-s, --skipsystem          Skip check of system modules beneath (%s). [False]
-v, --verbose             Display diagnostic messages. [False]
""" % (argv0, sys.prefix)

#----------------------------------------------------------------------------

def main(argv=None): ## default args none
    if argv is None:
        argv = sys.argv ## sets to system args if none

    wait = ModuleWatcher.SECONDS_BETWEEN_CHECKS 
    skipsystem = ModuleWatcher.SKIP_SYSTEM_MODULES
    verbose = ModuleWatcher.VERBOSE
    # parse command line arguments
    try:
        try:
            opts, args = getopt.getopt(argv[1:], "hw:sv",
                                       ["help", "wait",
                                        "skipsystem", "verbose"])
        except getopt.error as msg:
             raise Usage(msg) # raises that message we saw before

        for o, a in opts: # enumeration checks both index and value at once
            if o in ("-h", "--help"):
                usage(argv[0]) # reading the run type conditions
                return 0
            if o in ("-w", "--wait"):
                try:
                    wait = float(a)
                except ValueError:
                    raise Usage("Parameter -w/--wait expects a float value")
            if o in ("-s", "--skipsystem"):
                skipsystem = True
            if o in ("-v", "--verbose"):
                verbose = True

    except Usage as err:  ## just a fancy print statement
        print >>sys.stderr, "%s:" % argv[0],
        print >>sys.stderr, err.msg
        print >>sys.stderr, "for help use --help"
        return 2 # exit condition 

    # Remove hotswap options from arguments
    if args:
        del argv[1:-len(args)] # checking and removing hotswap from runtime condition
    else:
        del argv[1:]

    if len(argv) <= 1:
        usage(argv[0])
        sys.exit(1)

    firstarg = argv[1]
    sourcefile = os.path.abspath(firstarg)
    if not os.path.isfile(sourcefile):
        print("%s: File '%s' does not exist." % (os.path.basename(argv[0]),
                                                      sourcefile))
        sys.exit(1)
    try:
        module = importmodule(sourcefile)
    except ImportError as e:
        print("%s: Unable to import '%s' as module: %s" % (os.path.basename(argv[0]),
                                                          sourcefile, e))
        sys.exit(1)

    # Remove hotswap.py from arguments that argv looks as
    # if no additional wrapper was present.
    del argv[0]

    # Start hotswapping
    run(skipsystem=skipsystem,
        seconds=wait,
        verbose=verbose)

    # Run the Python source file with hotswapping enabled.
    module.main()

if __name__ == '__main__':
    main() # this is the only call, rest is just a module if not m
    
