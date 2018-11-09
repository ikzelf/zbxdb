def db_errorcode(driver, excep):
    """pass exception code and message from various drivers in standard way"""
    # print('db_errorcode:{}\n'.format(excep))
    # print(type(excep))
    # print(dir(excep))
    if "LoginError" in str(type(excep)):
        return 1031, excep.args[0]
    elif "OperationalError"  in str(type(excep)):
        return excep.msg_no, excep.args[0]
    else:
        print("type {}".format(type(excep)))
        print(excep)
        print(dir(excep))
        return excep.msg_no, excep.args[0]

def db_error_needs_new_session(driver, code):
    """some errors justify a new database connection. In that case return true"""
    return False
