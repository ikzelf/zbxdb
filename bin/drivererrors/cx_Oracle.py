def db_errorcode(driver, excep):
    """pass exception code and message from various drivers in standard way"""
    # print('db_errorcode:{}\n'.format(excep))
    ERROR, = excep.args
    return ERROR.code, str(excep.args[0])

def db_error_needs_new_session(driver, code):
    """some errors justify a new database connection. In that case return true
        mostly due to strange issues
        added 1000 (open_cursors exceeded) after adding a test over dg4odbc
    """
    if code in(28, 1000, 1012, 1041, 3113, 3114, 3117, 3135, 12153):
        print('db_error_needs_new_session:{}\n'.format(code))
        return True
    if code == 15000:
        printf('%s: asm requires sysdba role\n', \
        datetime.datetime.fromtimestamp(time.time()))
        return True
    return False
