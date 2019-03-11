import sys
def fullname(o):
    # o.__module__ + "." + o.__class__.__qualname__ is an example in
    # this context of H.L. Mencken's "neat, plausible, and wrong."
    # Python makes no guarantees as to whether the __module__ special
    # attribute is defined, so we take a more circumspect approach.
    # Alas, the module name is explicitly excluded from __qualname__
    # in Python 3.  
    module = o.__class__.__module__
    if module is None or module == str.__class__.__module__:
        return o.__class__.__name__  # Avoid reporting __builtin__
    else:
        return module + '.' + o.__class__.__name__

def db_errorcode(driver, excep):
    """pass exception code and message from various drivers in standard way"""
    if "LoginError" in str(type(excep)):
        return "LoginError", excep.args[0]
    elif "OperationalError"  in str(type(excep)):
        return excep.msg_no, excep.args[0]
    elif "ConnectionResetError" in str(type(excep)):
        return "ConnectionResetError", str(excep.args[0])
    elif "timed out" == str(excep.args[0]):
        return fullname(excep), excep.args[0]
    else:
        print('db_errorcode:{}\n'.format(excep))
        print(type(excep))
        print(dir(excep))
        sys.stdout.flush()
        return excep.msg_no, str(excep.args[0])

def db_error_needs_new_session(driver, code):
    """some errors justify a new database connection. In that case return true"""
    if code == "ConnectionResetError":
        return True
    return False
