""" functions to return zbxdb info needed for mssql"""


def connection_info(conn):
    """get connection info from connected database"""
    conn_info = {'dbversion': "", 'sid': 0, 'instance_type': "rdbms",
                 'serial': 0, 'db_role': "primary", 'uname': "",
                 'iname': ""}
    _c = conn.cursor()

    _c.execute("""
SELECT LEFT(cast(serverproperty('ProductVersion') as varchar), CHARINDEX('.',
cast(serverproperty('ProductVersion') as varchar)) - 1)""")

    data = _c.fetchone()

    conn_info['dbversion'] = data[0]

    # C.execute("select pg_backend_pid()")
    # DATA = C.fetchone()
    # conn_info['sid'] = DATA[0]
    _c.execute("SELECT @@servername, ORIGINAL_LOGIN()")
    data = _c.fetchone()
    conn_info['iname'] = data[0]
    conn_info['uname'] = data[1]
    _c.close()

    return conn_info


def connect_string(_c):
    """construct connect string, just incase"""

    return "{usr}/{pwd}@{url},{port}/{db}".format(usr=_c['username'], pwd=_c['password'],
                                                  url=_c['server'], port=_c['server_port'],
                                                  db=_c['db_name'])


def connect(_db, _c):
    """the actual connect, also specifying the appname"""

    return _db.connect(server=_c['server'],
                       database=_c['db_name'],
                       port=_c['server_port'],
                       user=_c['username'],
                       password=_c['password'],
                       timeout=_c['sqltimeout'],
                       appname=_c['ME']
                       )
