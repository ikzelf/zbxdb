def connection_info(conn):
    """get connection info from connected database"""
    conn_info = {'dbversion': "", 'sid': 0, 'instance_type': "rdbms",
                 'serial': 0, 'db_role': "primary", 'uname': "",
                 'iname': ""}
    C = conn.cursor()
    # C.execute("select substring(version from '[0-9]+') from version()")
    # C.execute("""SELECT SUBSTRING(ver, 1, CHARINDEX('.', ver) - 1) FROM (SELECT CAST(serverproperty('ProductVersion') AS nvarchar) ver)""")

    C.execute("""
SELECT LEFT(cast(serverproperty('ProductVersion') as varchar), CHARINDEX('.',
cast(serverproperty('ProductVersion') as varchar)) - 1)""")

    DATA = C.fetchone()

    conn_info['dbversion'] = DATA[0]

    # C.execute("select pg_backend_pid()")
    # DATA = C.fetchone()
    # conn_info['sid'] = DATA[0]
    C.execute("SELECT name, ORIGINAL_LOGIN() from Sys.Servers")
    DATA = C.fetchone()
    conn_info['iname'] = DATA[0]
    conn_info['uname'] = DATA[1]
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
    return db.connect(server=c['server'],
                      database=c['db_name'],
                      port=c['server_port'],
                      user=c['username'],
                      password=c['password'],
                      timeout=c['sqltimeout']
                    )
