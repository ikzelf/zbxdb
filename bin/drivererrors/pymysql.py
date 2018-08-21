def db_errorcode(driver, excep):
    """pass exception code and message from various drivers in standard way"""
    try:
        return excep.args[0], excep.args[1]
    except AttributeError:
        print("AttributeError")
        print("type {}".format(type(excep)))
        print(excep)
        print(dir(excep))

def db_error_needs_new_session(driver, code):
    """some errors justify a new database connection. In that case return true"""
    if str(code) in ("2013"):
        return True
    if driver == "Cx_Oracle":
        if code in(28, 1012, 1041, 3113, 3114, 3135):
            return True
    return False
