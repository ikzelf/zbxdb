""" functions to return zbxdb info needed for SAPhana"""
import logging
import os
from hdbcli import dbapi

LOGGER = logging.getLogger(__name__)


def current_role(*args):
    """return current role of database needs to be improved, I have no standby
       config"""

    return "primary"


def connection_info(conn):
    """get connection info from connected database"""
    conn_info = {'dbversion': "", 'sid': 0, 'instance_type': "rdbms",
                 'serial': 0, 'db_role': "primary", 'uname': "",
                 'iname': ""}
    _c = conn.cursor()

    _c.execute("select substr_before (version, '.'), system_id from sys.m_database")

    data = _c.fetchone()

    conn_info['dbversion'] = data[0]
    conn_info['iname'] = data[1]

    _c.execute('SELECT CURRENT_USER "current user" FROM DUMMY')
    data = _c.fetchone()
    conn_info['uname'] = data[0]
    _c.close()
    conn_info['db_role'] = 'primary'

    return conn_info


def connect_string(_c):
    """construct connect string, just incase"""

    return "{usr}/{pwd}@{url}:{port}".format(usr=_c['username'],
                                             pwd=_c['password'],
                                             url=_c['server'],
                                             port=_c['server_port'],
                                             )


def connect(_db, _c):
    """the actual connect, also specifying the appname"""

    sslTrustStore = None
    if 'sslTrustStore' in _c:
        sslTrustStore = _c['sslTrustStore']
    LOGGER.warning("sslTrustStore = %s", sslTrustStore)
    if sslTrustStore:
        LOGGER.warning("Enable tls encryption with sslTrustStore=%s", sslTrustStore)
        try:
            x = open(sslTrustStore,'r')
            x.close()
            try:
                import OpenSSL
            except ModuleNotFoundError:
                LOGGER.fatal("pyOpenSSL not installed")
                raise
        except FileNotFoundError:
            LOGGER.fatal("sslTrustStore=%s does not exist or not readable", sslTrustStore)
            raise

    sslValidateCertificate = 'false'
    if 'sslValidateCertificate' in _c:
        sslValidateCertificate = _c['sslValidateCertificate']
    LOGGER.warning("sslValidateCertificate = %s", sslValidateCertificate)

    encrypt = 'false'
    if 'encrypt' in _c:
        encrypt = _c['encrypt']
    LOGGER.warning("encrypt = %s", encrypt)

    r = dbapi.connect(address=_c['server'],
                       port=int(_c['server_port']),
                       user=_c['username'],
                       password=_c['password'],
                       sslValidateCertificate=sslValidateCertificate,
                       sslTrustStore=sslTrustStore,
                       APPLICATION=_c['ME'],
                       encrypt=encrypt
                       # timeout=_c['sqltimeout'],
                       # appname=_c['ME']
                       )
    print("Connected") if r.isconnected() else print("Not connected")
    return r
