"""uniform exception handling for zbxdb"""
import logging

LOGGER = logging.getLogger(__name__)
def fullname(_o):
    """return fqn for this module"""
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
    if str(excep.args[0]) == "timed out":
        return fullname(excep), excep.args[0]
    try:
        return excep.args[0], excep.args[1]
    except AttributeError:
        LOGGER.debug("AttributeError")
        LOGGER.debug("type %s", type(excep))
        LOGGER.debug(excep)
        LOGGER.debug(dir(excep))

def db_error_needs_new_session(driver, code):
    """some errors justify a new database connection. In that case return true"""
    if str(code) in "2013":
        return True
    return False
