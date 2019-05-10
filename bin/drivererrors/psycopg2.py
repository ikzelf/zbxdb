"""driver specific errors, simplified for zbxdb"""
import logging

LOGGER = logging.getLogger(__name__)
def db_errorcode(driver, excep):
    """pass exception code and message from various drivers in standard way
       driver is the loaded driver object"""
    LOGGER.debug("db_errorcode %s %s\n", excep, excep.pgcode)
    # how to catch one of:
    # - psycopg2.OperationalError: FATAL:  no pg_hba.conf entry for host
    # - psycopg2.OperationalError: server closed the connection unexpectedly
    # - psycopg2.OperationalError: could not connect to server: Connection refused
    if driver.OperationalError and (not excep.pgcode):
        _c = 1001
    elif excep.pgcode is None:
        _c = 1031
    else:
        _c = excep.pgcode
    return str(_c), str(excep.args[0])

def db_error_needs_new_session(driver, code):
    """some errors justify a new database connection. In that case return true"""
    if code in ("1001", "57P01"):
        return True
    return False
