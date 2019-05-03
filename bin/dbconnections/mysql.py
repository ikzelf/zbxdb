""" mysql specific connection methods"""
import pymysql


def connection_info(conn):
    """get connection info from connected database"""
    conn_info = {'dbversion': "", 'sid': 0, 'instance_type': "rdbms",
                 'serial': 0, 'db_role': "primary", 'uname': "",
                 'iname': ""}
    _c = conn.cursor()

    _c.execute("select left(version(),locate('.',version())-1)")

    _data = _c.fetchone()

    conn_info['dbversion'] = _data[0]

    _c.execute("select concat(@@basedir,':',@@port), current_user()")
    _data = _c.fetchone()
    conn_info['iname'] = _data[0]
    conn_info['uname'] = _data[1]

    try:
        _c.execute(
            "select count(*) from performance_schema.replication_applier_status")
        _data = _c.fetchone()

        if _data[0] > 0:
            conn_info['db_role'] = "slave"
    except pymysql.ProgrammingError:
        # a bit dirty ... assume primary replication_applier_status is pretty new
        pass

    _c.close()

    return conn_info


def connect_string(_c):
    """ return connect string"""

    return "{usr}/{pwd}@{url},{port}/{db}".format(usr=_c['username'], pwd=_c['password'],
                                                  url=_c['server'], port=_c['server_port'],
                                                  db=_c['db_name'])


def connect(_db, _c):
    """  the actual connect"""
    dbc = _db.connect(host=_c['server'],
                      user=_c['username'],
                      password=_c['password'],
                      db=_c['db_name'],
                      port=int(_c['server_port']),
                      read_timeout=int(_c['sqltimeout']),
                      program_name=_c['ME']
                      )

    return dbc
