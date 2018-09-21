def db_errorcode(driver, excep):
    """pass exception code and message from various drivers in standard way
       driver is the loaded driver object"""
    # print ("driver: {}".format(driver))
    print ("db_errorcode ***{}***{}***\n".format(excep, excep.pgcode))
    # how to catch one of:
    # - psycopg2.OperationalError: FATAL:  no pg_hba.conf entry for host
    # - psycopg2.OperationalError: server closed the connection unexpectedly
    # - psycopg2.OperationalError: could not connect to server: Connection refused
    if driver.OperationalError and (not excep.pgcode):
        c = 1001
    elif excep.pgcode is None:
        c = 1031
    else:
        c = excep.pgcode
    return str(c), str(excep.args[0])

def db_error_needs_new_session(driver, code):
    """some errors justify a new database connection. In that case return true"""
    if code in ("1001", "57P01"):
        return True
    return False
