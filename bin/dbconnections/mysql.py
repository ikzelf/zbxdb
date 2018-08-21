def connection_info(conn):
    """get connection info from connected database"""
    conn_info = {'dbversion': "", 'sid': 0, 'instance_type': "rdbms",
                 'serial': 0, 'db_role': "primary", 'uname': "",
                 'iname': ""}
    C = conn.cursor()

    C.execute("select left(version(),locate('.',version())-1)")

    DATA = C.fetchone()

    conn_info['dbversion'] = DATA[0]

    C.execute("select concat(@@basedir,':',@@port), current_user()")
    DATA = C.fetchone()
    conn_info['iname'] = DATA[0]
    conn_info['uname'] = DATA[1]

    try:
      C.execute("select count(*) from performance_schema.replication_applier_status")
      DATA = C.fetchone()
      if DATA[0] > 0:
          conn_info['db_role'] = "slave"
    except:
      # a bit dirty ... assume primary replication_applier_status is pretty new
      pass

    C.close()
    return conn_info

# def connect_string(c):
#     return 'server="'+ c['server']+'",'+\
#             'database="'+ c['db_name']+'",'+\
#             'port="'+ c['server_port']+'",'+\
#             'user="'+ c['username']+'",'+ 'password="'+ c['password']+'"'
def connect_string(c):
    return "{usr}/{pwd}@{url},{port}/{db}".format(usr=c['username'],pwd=c['password'],
                      url=c['server'],port=c['server_port'],db=c['db_name'])
def connect(db, c):
    dbc = db.connect(host=c['server'],
                      user=c['username'],
                      password=c['password'],
                      db=c['db_name'],
                      port=int(c['server_port']),
                      read_timeout=int(c['sqltimeout'])#,
                    #  cursorclass=pymysql.cursors.DictCursor
                    )
    return dbc
