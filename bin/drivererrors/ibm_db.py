"""standardize driver errors for zbxdb"""
import logging

LOGGER = logging.getLogger(__name__)


def fullname(_o):
    """return fqn of  this module"""
    # _o.__module__ + "." + _o.__class__.__qualname__ is an example in
    # this context of H.L. Mencken's "neat, plausible, and wrong."
    # Python makes no guarantees as to whether the __module__ special
    # attribute is defined, so we take a more circumspect approach.
    # Alas, the module name is explicitly excluded from __qualname__
    # in Python 3.
    module = _o.__class__.__module__

    if module is None or module == str.__class__.__module__:
        return _o.__class__.__name__  # Avoid reporting __builtin__

    return module + '.' + _o.__class__.__name__


def db_errorcode(driver, excep):
    """pass exception code and message from various drivers in standard way"""
    LOGGER.debug('db_errorcode: %s\n', excep)

    if fullname(excep) == "ConnectionResetError":
        return fullname(excep), str(excep.args[0])
    _error = driver.stmt_error()

    return _error, str(excep.args[0])


def db_error_needs_new_session(driver, code):
    """some errors justify a new database connection. In that case return true
        mostly due to strange issues
        added 1000 (open_cursors exceeded) after adding a test over dg4odbc
        added 55524 (Too many recursive autonomous transactions for temporary
        undo) after adding a test over dg4odbc
    """

    if code in(28, 1000, 1012, 1041, 3113, 3114, 3117, 3135, 12153, 55524):
        # print('db_error_needs_new_session:{}\n'.format(code))

        return True

    return False
