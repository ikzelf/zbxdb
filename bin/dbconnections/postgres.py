def connection_info(conn):
    """get connection info from connected database"""
    conn_info = {'dbversion': "", 'sid': 0, 'instance_type': "rdbms",
                 'serial': 0, 'db_role': "", 'uname': "",
                 'iname': ""}
    C = conn.cursor()
    C.execute("select substring(version from '[0-9]+') from version()")

    DATA = C.fetchone()

    conn_info['dbversion'] = DATA[0]

    C.execute("select pg_backend_pid()")
    DATA = C.fetchone()
    conn_info['sid'] = DATA[0]
    C.execute("SELECT current_database()")
    DATA = C.fetchone()
    conn_info['iname'] = DATA[0]
    C.execute("SELECT current_user")
    DATA = C.fetchone()
    conn_info['uname'] = DATA[0]
    C.execute("select pg_is_in_recovery()")
    DATA = C.fetchone()
    if not DATA[0]:
        conn_info['db_role'] = "primary"
    else:
        conn_info['db_role'] = "slave"
    C.close()
    return conn_info
