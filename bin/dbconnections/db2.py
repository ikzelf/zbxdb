""" db2 specific connection methods"""
import logging

LOGGER = logging.getLogger(__name__)


def current_role(conn, info):
    """return current role of database"""

    _c_role = "primary"

    return _c_role


def connection_info(con):
    """get connection info from connected database"""
    conn_info = {'dbversion': "", 'sid': 0, 'instance_type': "rdbms",
                 'serial': 0, 'db_role': "", 'uname': "",
                 'iname': ""}
    _c = con.cursor()
    _c.execute("""SELECT 
    substr(replace(service_level,'DB2 v',''),
            1,
            locate_in_string(replace(service_level,'DB2 v',''),'.')-1
          )
     , inst_name
     , SESSION_USER
     FROM SYSIBMADM.ENV_INST_INFO
     """)

    _data = _c.fetchone()

    conn_info['dbversion'] = _data[0]
    conn_info['instance_type'] = "rdbms"
    conn_info['iname'] = _data[1]
    conn_info['uname'] = _data[2]
    conn_info['db_role'] =  current_role(con, conn_info)

    _c.close()

    return conn_info


def connect_string(config):
    """return connect string"""

    return "DATABASE={};HOSTNAME={};PORT={};PROTOCOL=TCPIP;UID={};PWD={};".format(
            config['db_name'], config['server'], config['server_port'],
            config['username'], config['password'])


def connect(_db, _c):
    """the actual connect"""
    import ibm_db_dbi

    LOGGER.debug("Connecting %s as %s",
                 connect_string(_c).replace(_c['password'], '*X*X*X*'),'user')

    con = _db.pconnect(connect_string(_c),"","")
    conn = ibm_db_dbi.Connection(con)
    LOGGER.error(_db)
    LOGGER.error(dir(_db))
    return conn
