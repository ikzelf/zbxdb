def db_errorcode(driver, excep):
    """pass exception code and message from various drivers in standard way"""
    try:
        return excep.msg_no, excep.args[0]
    except AttributeError:
        if type(excep) is LoginError:
            return 1031, excep.args[0]
        else:
            print("type {type}".format(type(excep)))
            print(excep)
            print(dir(excep))

def db_error_needs_new_session(driver, code):
    """some errors justify a new database connection. In that case return true"""
    return False
