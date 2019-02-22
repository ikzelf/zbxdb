import sys

def db_errorcode(driver, excep):
    """pass exception code and message from various drivers in standard way"""
    if "LoginError" in str(type(excep)):
        return "LoginError", excep.args[0]
    elif "OperationalError"  in str(type(excep)):
        return excep.msg_no, excep.args[0]
    elif "ConnectionResetError" in str(type(excep)):
        return "ConnectionResetError", str(excep.args[0])
    elif "timed out" == str(excep.args[0]):
        return type(excep), excep.args[0]
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
