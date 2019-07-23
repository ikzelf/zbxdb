"""postgres specific implementations of zbxdb functions"""


def current_role(conn, info):
    """return current role of database"""
    _c = conn.cursor()
    _c.execute("select pg_is_in_recovery()")
    _data = _c.fetchone()
    _c.close()

    if not _data[0]:
        return "primary"
    return "slave"


def connection_info(conn):
    """get connection info from connected database"""
    conn_info = {'dbversion': "", 'sid': 0, 'instance_type': "rdbms",
                 'serial': 0, 'db_role': "", 'uname': "",
                 'iname': ""}
    _c = conn.cursor()
    _c.execute("select substring(version from '[0-9]+') from version()")

    _data = _c.fetchone()

    conn_info['dbversion'] = _data[0]

    _c.execute("select pg_backend_pid()")
    _data = _c.fetchone()
    conn_info['sid'] = _data[0]
    _c.execute("""select inet_server_addr()||':'||p.setting||':'|| d.setting
          from pg_settings p, pg_settings d
          where p.name = 'port'
          and   d.name = 'data_directory'""")
    _data = _c.fetchone()
    conn_info['iname'] = _data[0]
    _c.execute("SELECT current_user")
    _data = _c.fetchone()
    conn_info['uname'] = _data[0]

    conn_info['db_role'] = current_role(conn, conn_info)

    return conn_info


def connect_string(config):
    """return connect string including application_name"""

    return "postgresql://" + config['username'] + ":" + config['password'] + "@" + \
        config['db_url'] + "?application_name={}".format(config['ME'])


def connect(_db, _c):
    """create the actual connection"""
    _c = _db.connect(connect_string(_c))
    _c.set_session(readonly=True)

    return _c
