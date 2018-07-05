def db_errorcode(driver, excep):
    """pass exception code and message from various drivers in standard way"""
    return excep.pgcode, excep.args[0]

def db_error_needs_new_session(driver, code):
    """some errors justify a new database connection. In that case return true"""
    return False
