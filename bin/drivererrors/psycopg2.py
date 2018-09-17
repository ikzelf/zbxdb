def db_errorcode(driver, excep):
    """pass exception code and message from various drivers in standard way"""
    # print ("db_errorcode ***{}***{}***\n".format(excep, excep.pgcode))
    if excep.pgcode is None:
        c = "zbxdb-1031"
    else:
        c = excep.pgcode
    return str(c), str(excep.args[0])

def db_error_needs_new_session(driver, code):
    """some errors justify a new database connection. In that case return true"""
    if code in ("57P01"):
        return True
    return False
