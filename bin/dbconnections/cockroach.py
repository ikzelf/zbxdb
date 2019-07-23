"""uniform connection methods for zbxdb"""


def current_role(*args):
    """cockroachDB has no standby"""

    return "primary"


def connection_info(conn):
    """get connection info from connected database"""
    conn_info = {'dbversion': "", 'sid': 0, 'instance_type': "rdbms",
                 'serial': 0, 'db_role': "", 'uname': "",
                 'iname': ""}
    _c = conn.cursor()
    _c.execute("set application_name = 'zbxdb'")
    _c.execute("set default_transaction_read_only = True")
    _c.execute("select substring(version from '[0-9]+') from version()")

    _data = _c.fetchone()

    conn_info['dbversion'] = _data[0]

    _c.execute("select pg_backend_pid()")
    _data = _c.fetchone()
    conn_info['sid'] = _data[0]
    _c.execute("SELECT current_database()")
    _data = _c.fetchone()
    conn_info['iname'] = _data[0]
    _c.execute("SELECT current_user")
    _data = _c.fetchone()
    conn_info['uname'] = _data[0]
    _c.execute("select pg_is_in_recovery()")
    _data = _c.fetchone()

    conn_info['db_role'] = current_role(conn)
    _c.close()

    return conn_info


def connect_string(config):
    return config['db_url']


def connect(db, c):
    return db.connect(connect_string(c))
