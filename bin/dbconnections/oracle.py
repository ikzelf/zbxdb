def connection_info(con):
    """get connection info from connected database"""
    conn_info = {'dbversion': "", 'sid': 0, 'instance_type': "rdbms",
                 'serial': 0, 'db_role': "", 'uname': "",
                 'iname': ""}
    C = con.cursor()
    try:
        C.execute("""select substr(i.version,0,instr(i.version,'.')-1),
          s.sid, s.serial#, p.value instance_type, i.instance_name
          , s.username
          from v$instance i, v$session s, v$parameter p 
          where s.sid = (select sid from v$mystat where rownum = 1)
          and p.name = 'instance_type'""")

        DATA = C.fetchone()

        conn_info['dbversion'] = DATA[0]
        conn_info['sid'] = DATA[1]
        conn_info['serial'] = DATA[2]
        conn_info['instance_type'] = DATA[3]
        conn_info['iname'] = DATA[4]
        conn_info['uname'] = DATA[5]

    except db.DatabaseError as dberr:
        ecode, emsg = dbe.db_errorcode(config['db_driver'], dberr)
        if ecode == 904:
            conn_info['dbversion'] = "pre9"
        else:
            conn_info['dbversion'] = "unk"

    if conn_info['instance_type'] == "RDBMS":
        C.execute("""select lower(database_role) from v$database""")
        DATA = C.fetchone()
        conn_info['db_role'] = DATA[0]
    else:
        conn_info['db_role'] = "asm"
    C.close()
    return conn_info

def connect_string(config):

    return config['username'] + "/" + config['password'] + "@" + \
                   config['db_url']

def connect(db, c):
    if c['role'].upper() == "SYSASM":
        c['omode'] = db.SYSASM
    if c['role'].upper() == "SYSDBA":
        c['omode'] = db.SYSDBA
    return db.connect(connect_string(c), mode=c['omode'])
