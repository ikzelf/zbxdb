#!/usr/bin/env python
"""
 free clonable from https://github.com/ikzelf/zbxora/
 (@) ronald.rood@ciber.nl follow @ik_zelf on twitter
 follow @zbxdb on twitter
 push your added items/checks using git
 options: -c/--cfile configFile
                     configFile contains config for 1 database and
                                a reference to the checks
 NOTE: a section whose name contains 'discover' is considered to be handled
           as a special case for LLD -> json arrays
 NOTE: consider using Oracle Wallet instead of coding credentials in config
 NOTE: run as a regular database client, not a special account like root or oracle
"""
import json
import collections
import datetime
import time
import sys
import os
import configparser
import resource
import gc
import subprocess
import threading
from argparse import ArgumentParser
from timeit import default_timer as timer
import platform
from pdb import set_trace
VERSION = "0.05"

def printf(format, *args):
    """just a simple c-style printf function"""
    sys.stdout.write(format % args)
    sys.stdout.flush()

def output(host, ikey, values):
    """uniform way to generate the output"""
    timestamp = int(time.time())
    OUTF.write(host + " " + ikey + " " + str(timestamp) + " " + str(values)+ "\n")
    OUTF.flush()

def errorcode(driver, excep):
    """pass exception code and message from various drivers in standard way"""
    if driver == 'psycopg2':
        return excep.pgcode, excep.args[0]
    elif driver == 'Cx_Oracle':
        ERROR, = dberr.args
        return ERROR.code, excep.args[0]

def error_needs_new_session(driver, code):
    """some errors justify a new database connection. In that case return true"""
    if driver == "Cx_Oracle":
        if code in(28, 1012, 1041, 3113, 3114, 3135):
            return True
        if code == 15000:
            printf('%s: asm requires sysdba role\n', \
            datetime.datetime.fromtimestamp(time.time()))
            return True
    return False

def get_config(filename):
    """read the specified configuration file"""
    config = {'db_url': "", 'db_type': "", 'db_driver': "", 'instance_type': "rdbms",
              'username': "scott", 'password': "tiger", 'role': "normal", 'omode': 0,
              'out_dir': "", 'out_file': "", 'hostname': "", 'checkfile_prefix': "",
              'site_checks': "", 'to_zabbic_method': "", 'to_zabbix_args': "",
              'sqltimeout': 0.0}
    CONFIG = configparser.RawConfigParser()
    if not os.path.exists(filename):
        raise ValueError("Configfile " + filename + " does not exist")

    INIF = open(filename, 'r')
    CONFIG.read_file(INIF)
    config['db_url'] = CONFIG.get(ME[0], "db_url")
    config['db_type'] = CONFIG.get(ME[0], "db_type")
    config['db_driver'] = CONFIG.get(ME[0], "db_driver")
    config['instance_type'] = CONFIG.get(ME[0], "instance_type")
    config['username'] = CONFIG.get(ME[0], "username")
    config['password'] = CONFIG.get(ME[0], "password")
    config['role'] = CONFIG.get(ME[0], "role")
    config['out_dir'] = os.path.expandvars(CONFIG.get(ME[0], "out_dir"))
    config['out_file'] = os.path.join(config['out_dir'],
                                      str(os.path.splitext(os.path.basename(filename))[0]) +
                                      ".zbx")
    config['hostname'] = CONFIG.get(ME[0], "hostname")
    config['checksfile_prefix'] = CONFIG.get(ME[0], "checks_dir")
    config['site_checks'] = CONFIG.get(ME[0], "site_checks")
    config['to_zabbix_method'] = CONFIG.get(ME[0], "to_zabbix_method")
    config['to_zabbix_args'] = os.path.expandvars(CONFIG.get(ME[0], "to_zabbix_args")) + \
                                                              " " + config['out_file']
    INIF.close()
    config['omode'] = 0
    if config['db_type'] == "oracle":
        if config['role'].upper() == "SYSASM":
            config['omode'] = db.SYSASM
        if config['role'].upper() == "SYSDBA":
            config['omode'] = db.SYSDBA

    if config['db_type'] == "oracle":
        config['CS'] = config['username'] + "/" + config['password'] + "@" + \
                       config['db_url'] + " as " + config['role'].upper()
    elif config['db_type'] == "postgres":
        config['CS'] = "postgresql://" + config['username'] + ":" + config['password'] + "@" + \
                       config['db_url']
    else:
        printf('%s DB_TYPE %s not -yet- implemented\n',
               datetime.datetime.fromtimestamp(time.time()),
               config['db_type'])
    try:
        config['sqltimeout'] = float(CONFIG.get(ME[0], "sql_timeout"))
    except configparser.NoOptionError:
        config['sqltimeout'] = 60.0
    return config

def connection_info(dbtype):
    """get connection info from connected database"""
    conn_info = {'dbversion': "", 'sid': 0, 'itype': "rdbms",
                 'serial': 0, 'dbrol': "", 'uname': "",
                 'iname': ""}
    C = conn.cursor()
    try:
        if dbtype == "oracle":
            C.execute("""select substr(i.version,0,instr(i.version,'.')-1),
              s.sid, s.serial#, p.value instance_type, i.instance_name
              , s.username
              from v$instance i, v$session s, v$parameter p 
              where s.sid = (select sid from v$mystat where rownum = 1)
              and p.name = 'instance_type'""")
        elif dbtype == "postgres":
            C.execute("select substring(version from '[0-9]+') from version()")

        DATA = C.fetchone()

        if dbtype == "oracle":
            conn_info['dbversion'] = DATA[0]
            conn_info['sid'] = DATA[1]
            conn_info['serial'] = DATA[2]
            conn_info['itype'] = DATA[3]
            conn_info['iname'] = DATA[4]
            conn_info['uname'] = DATA[5]
        elif dbtype == "postgres":
            conn_info['dbversion'] = DATA[0]

    except db.DatabaseError as dberr:
        ecode, emsg = errorcode(config['db_driver'], dberr)
        if ecode == 904:
            conn_info['dbversion'] = "pre9"
        else:
            conn_info['dbversion'] = "unk"

    if dbtype == "oracle": 
        if conn_info['itype'] == "RDBMS":
            C.execute("""select database_role from v$database""")
            DATA = C.fetchone()
            conn_info['dbrol'] = DATA[0]
        else:
            conn_info['dbrol'] = "asm"
    elif dbtype == "postgres":
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
            conn_info['dbrol'] = "primary"
        else:
            conn_info['dbrol'] = "slave"
    C.close()
    return conn_info

ME = os.path.splitext(os.path.basename(__file__))
STARTTIME = int(time.time())
PARSER = ArgumentParser()
PARSER.add_argument("-c", "--cfile", dest="configfile", default=ME[0]+".cfg",
                    help="Configuration file", metavar="FILE")
ARGS = PARSER.parse_args()

config = get_config(ARGS.configfile)
printf("%s start python-%s %s-%s pid=%s Connecting for hostname %s...\n", \
       datetime.datetime.fromtimestamp(STARTTIME), \
       platform.python_version(), ME[0], VERSION, os.getpid(), config['hostname']
      )
printf("%s %s found db_type=%s, driver %s; checking for driver\n", \
       datetime.datetime.fromtimestamp(time.time()), ME[0], \
       config['db_type'], config['db_driver'])
try:
  db= __import__(config['db_driver'])
except:
    printf("%s supported will be oracle(cx_Oracle), postgres(psycopg2), \
           mysql(mysql.connector), mssql(pymssql/_mssql), db2(ibm_db_dbi)\n", ME[0])
    printf("%s tested are oracle(cx_Oracle), postgres(psycopg2)\n", ME[0])
    printf("Don't forget to install the drivers first ...\n")
    raise

printf("%s %s driver %s loaded\n",
       datetime.datetime.fromtimestamp(time.time()), ME[0], config['db_driver'])

CHECKFILES = [[__file__, os.stat(__file__).st_mtime]]
CHECKSCHANGED = [0]

CONNECTCOUNTER = 0
CONNECTERROR = 0
QUERYCOUNTER = 0
QUERYERROR = 0
if config['site_checks'] != "NONE":
    printf("%s site_checks: %s\n", \
        datetime.datetime.fromtimestamp(time.time()), config['site_checks'])
printf("%s to_zabbix_method: %s %s\n", \
    datetime.datetime.fromtimestamp(time.time()), config['to_zabbix_method'], \
       config['to_zabbix_args'])
printf("%s out_file:%s\n", \
    datetime.datetime.fromtimestamp(time.time()), config['out_file'])
SLEEPC = 0
SLEEPER = 1
PERROR = 0
while True:
    try:
        Z = CHECKFILES[0]
        CHECKSFILE = Z[0]
        CHECKSCHANGED = Z[1]
        if CHECKSCHANGED != os.stat(CHECKSFILE).st_mtime:
            printf("%s %s changed, restarting ...\n",
                   datetime.datetime.fromtimestamp(time.time()), CHECKSFILE)
            os.execv(__file__, sys.argv)

        # reset list in case of a just new connection that reloads the config
        CHECKFILES = [[__file__, os.stat(__file__).st_mtime]]
        config = get_config(ARGS.configfile)
        if os.path.exists(config['out_file']):
            OUTF = open(config['out_file'], "a")
        else:
            OUTF = open(config['out_file'], "w")

        START = timer()
        with db.connect(config['CS']) as conn:
            CONNECTCOUNTER += 1
            output(config['hostname'], ME[0]+"[connect,status]", 0)
            CURS = conn.cursor()
            connect_info = connection_info ( config['db_type'] )
            printf('%s connected db_url %s type %s db_role %s version %s\n'\
                   '%s user %s %s sid,serial %d,%d instance %s as %s\n',
                   datetime.datetime.fromtimestamp(time.time()), \
                   config['db_url'], connect_info['itype'], connect_info['dbrol'], \
                   connect_info['dbversion'], \
                   datetime.datetime.fromtimestamp(time.time()), \
                   config['username'], connect_info['uname'], connect_info['sid'], \
                   connect_info['serial'], \
                   connect_info['iname'], \
                   config['role'])
            if  connect_info['dbrol'] in ["PHYSICAL STANDBY", "MASTER"]:
                CHECKSFILE = os.path.join(config['checksfile_prefix'], \
                                           config['db_type'], "standby" +
                                           "." + connect_info['dbversion'] +".cfg")
            else:
                CHECKSFILE = os.path.join(config['checksfile_prefix'], \
                                          config['db_type']  ,
                                          connect_info['dbrol'] + "." + \
                                          connect_info['dbversion']+".cfg")

            printf('%s using sql_timeout %d\n',
                   datetime.datetime.fromtimestamp(time.time()), \
                   config['sqltimeout'])
            FILES = [CHECKSFILE]
            CHECKFILES.extend([[CHECKSFILE, 0]])
            if config['site_checks'] != "NONE":
                for addition in config['site_checks'].split(","):
                    addfile = os.path.join(config['checksfile_prefix'], config['db_type'], \
                                           addition + ".cfg")
                    CHECKFILES.extend([[addfile, 0]])
                    FILES.extend([addfile])
            printf('%s using checks from %s\n',
                   datetime.datetime.fromtimestamp(time.time()), FILES)

            for CHECKSFILE in CHECKFILES:
                if not os.path.exists(CHECKSFILE[0]):
                    raise ValueError("Configfile " + CHECKSFILE[0]+ " does not exist")
            ## all checkfiles exist

            SLEEPC = 0
            SLEEPER = 1
            PERROR = 0
            CONMINS = 0
            OPENTIME = int(time.time())
            while True:
                NOWRUN = int(time.time()) # keep this to compare for when to dump stats
                RUNTIMER = timer() # keep this to compare for when to dump stats
                if os.path.exists(config['out_file']):
                    OUTF = open(config['out_file'], "a")
                else:
                    OUTF = open(config['out_file'], "w")
                # loading checks from the various checkfiles:
                NEEDTOLOAD = "no"
                for i in range(len(CHECKFILES)): # at index 0 is the script itself
                    z = CHECKFILES[i]
                    CHECKSFILE = z[0]
                    CHECKSCHANGED = z[1]
                    # if CHECKSFILE became inaccessible in run -> crash and no output :-(
                    # change the CHECKSCHANGED to catch that.
                    if CHECKSCHANGED != os.stat(CHECKSFILE).st_mtime:
                        if i == 0: # this is the script itself that changed
                            printf("%s %s changed, restarting ...\n",
                                   datetime.datetime.fromtimestamp(time.time()), CHECKSFILE)
                            os.execv(__file__, sys.argv)
                        else:
                            if CHECKSCHANGED == 0:
                                printf("%s checks loading %s\n", \
                                    datetime.datetime.fromtimestamp(time.time()), CHECKSFILE)
                                NEEDTOLOAD = "yes"
                            else:
                                printf("%s checks changed, reloading %s\n", \
                                    datetime.datetime.fromtimestamp(time.time()), CHECKSFILE)
                                NEEDTOLOAD = "yes"

                if NEEDTOLOAD == "yes":
                    output(config['hostname'], ME[0] + "[version]", VERSION) # try once in a while
                    OBJECTS_LIST = []
                    SECTIONS_LIST = []
                    FILES_LIST = []
                    ALL_CHECKS = []
                    for i in range(len(CHECKFILES)):
                        z = CHECKFILES[i]
                        CHECKSFILE = z[0]
                        E = collections.OrderedDict()
                        E = {"{#CHECKS_FILE}": i}
                        FILES_LIST.append(E)

                    FILES_JSON = '{\"data\":'+json.dumps(FILES_LIST)+'}'
                    output(config['hostname'], ME[0]+".files.lld", FILES_JSON)
                    CRASH = 0
                    for i in range(1, len(CHECKFILES)):
                        z = CHECKFILES[i]
                        CHECKSFILE = z[0]
                        CHECKS = configparser.RawConfigParser()
                        try:
                            CHECKSF = open(CHECKSFILE, 'r')
                            output(config['hostname'], ME[0] + "[checks," + str(i) + \
                                   ",name]", CHECKSFILE)
                            output(config['hostname'], ME[0] + "[checks," + str(i) + \
                                   ",lmod]",
                                   str(int(os.stat(CHECKSFILE).st_mtime)))
                            try:
                                CHECKS.read_file(CHECKSF)
                                CHECKSF.close()
                                output(config['hostname'], ME[0] + "[checks," + str(i) + \
                                       ",status]", 0)
                            except configparser.Error:
                                output(config['hostname'], ME[0] + "[checks," + str(i) + \
                                       ",status]", 13)
                                printf("%s\tfile %s has parsing errors %s %s ->(13)\n",
                                       datetime.datetime.fromtimestamp(time.time()),
                                       CHECKSFILE)
                                # CRASH=13
                                # raise
                        except IOError as io_error:
                            output(config['hostname'], ME[0] + "[checks," + str(i) + ",status]", 11)
                            printf("%s\tfile %s IOError %s %s ->(11)\n",
                                   datetime.datetime.fromtimestamp(time.time()), CHECKSFILE,
                                   io_error.errno, io_error.strerror)
                            CRASH = 11
                            # raise

                        z[1] = os.stat(CHECKSFILE).st_mtime

                        CHECKFILES[i] = z
                        ALL_CHECKS.append(CHECKS)
                        for section in sorted(CHECKS.sections()):
                            secMins = int(CHECKS.get(section, "minutes"))
                            if secMins == 0:
                                printf("%s\t%s run at connect only\n", \
                                    datetime.datetime.fromtimestamp(time.time()), section)
                            else:
                                printf("%s\t%s run every %d minutes\n", \
                                    datetime.datetime.fromtimestamp(time.time()), section, \
                                    secMins)
                            # dump own discovery items of the queries per section
                            E = collections.OrderedDict()
                            E = {"{#SECTION}": section}
                            SECTIONS_LIST.append(E)
                            x = dict(CHECKS.items(section))
                            for key, sql  in sorted(x.items()):
                                if sql and key != "minutes":
                                    d = collections.OrderedDict()
                                    d = {"{#SECTION}": section, "{#KEY}": key}
                                    OBJECTS_LIST.append(d)
                                    printf("%s\t\t%s: %s\n", \
                                        datetime.datetime.fromtimestamp(time.time()), \
                                        key, sql[0 : 60].replace('\n', ' ').replace('\r', ' '))
                    # checks are loaded now.
                    SECTIONS_JSON = '{\"data\":'+json.dumps(SECTIONS_LIST)+'}'
                    # printf ("DEBUG lld key: %s json: %s\n", ME[0]+".lld", ROWS_JSON)
                    output(config['hostname'], ME[0]+".section.lld", SECTIONS_JSON)
                    ROWS_JSON = '{\"data\":'+json.dumps(OBJECTS_LIST)+'}'
                    # printf ("DEBUG lld key: %s json: %s\n", ME[0]+".lld", ROWS_JSON)
                    output(config['hostname'], ME[0] + ".query.lld", ROWS_JSON)
                # checks discovery is also printed
                #
                # assume we are still connected. If not, exception will tell real story
                output(config['hostname'], ME[0] + "[connect,status]", 0)
                output(config['hostname'], ME[0] + "[uptime]", int(time.time() - STARTTIME))
                output(config['hostname'], ME[0] + "[opentime]", int(time.time() - OPENTIME))

                # the connect status is only real if executed a query ....
                for CHECKS in ALL_CHECKS:
                    for section in sorted(CHECKS.sections()):
                        SectionTimer = timer() # keep this to compare for when to dump stats
                        secMins = int(CHECKS.get(section, "minutes"))
                        if ((CONMINS == 0 and secMins == 0) or
                                (secMins > 0 and CONMINS % secMins == 0)):
                            ## time to run the checks again from this section
                            x = dict(CHECKS.items(section))
                            CURS = conn.cursor()
                            for key, sql  in sorted(x.items()):
                                if sql and key != "minutes":
                                    # printf ("%s DEBUG Running %s.%s\n", \
                                    # datetime.datetime.fromtimestamp(time.time()), section, key)
                                    try:
                                        QUERYCOUNTER += 1
                                        sqltimeout = threading.Timer(config['sqltimeout'], \
                                                                     conn.cancel)
                                        sqltimeout.start()
                                        START = timer()
                                        CURS.execute(sql)
                                        startf = timer()
                                        # output for the query must include the
                                        #        complete key and value
                                        rows = CURS.fetchall()
                                        if os.path.exists(config['out_file']):
                                            OUTF = open(config['out_file'], "a")
                                        else:
                                            OUTF = open(config['out_file'], "w")
                                        if "discover" in section:
                                            OBJECTS_LIST = []
                                            for row in rows:
                                                d = collections.OrderedDict()
                                                for col in range(0, len(CURS.description)):
                                                    d[CURS.description[col][0]] = row[col]
                                                OBJECTS_LIST.append(d)
                                            ROWS_JSON = '{\"data\":'+json.dumps(OBJECTS_LIST)+'}'
                                            # printf ("DEBUG lld key: %s json: %s\n", key,
                                            #          ROWS_JSON)
                                            output(config['hostname'], key, ROWS_JSON)
                                            output(config['hostname'], ME[0] + \
                                                   "[query," + section + "," + \
                                              key + ",status]", 0)
                                        else:
                                            if  rows and len(rows[0]) == 2:
                                                for row in rows:
                                                    output(config['hostname'], row[0], row[1])
                                                output(config['hostname'], ME[0] + \
                                                       "[query," + section + "," +
                                                       key + ",status]", 0)
                                            elif not rows:
                                                output(config['hostname'], ME[0] + \
                                                       "[query," + section + "," +
                                                       key + ",status]", 0)
                                            else:
                                                printf('%s key=%s.%s ZBXDB-%d: ' +
                                                       'SQL format error: %s\n',
                                                       datetime.datetime.fromtimestamp(time.time()),
                                                       section, key, 2, "expect key,value pairs")
                                                output(config['hostname'], ME[0] + \
                                                       "[query," + section + "," +
                                                       key + ",status]", 2)
                                        sqltimeout.cancel()
                                        fetchela = timer() - startf
                                        ELAPSED = timer() - START
                                        output(config['hostname'], ME[0] + "[query," + \
                                               section + "," +
                                               key + ",ela]", ELAPSED)
                                        output(config['hostname'], ME[0] + "[query," + \
                                               section + "," +
                                               key + ",fetch]", fetchela)
                                    except db.DatabaseError as dberr:
                                        ecode, emsg = errorcode(config['db_driver'], dberr)

                                        if os.path.exists(config['out_file']):
                                            OUTF = open(config['out_file'], "a")
                                        else:
                                            OUTF = open(config['out_file'], "w")
                                        ELAPSED = timer() - START
                                        QUERYERROR += 1
                                        output(config['hostname'], ME[0] + "[query," + \
                                               section + "," + \
                                            key + ",status]", ecode)
                                        output(config['hostname'], ME[0] + "[query," + \
                                               section + "," + \
                                            key + ",ela]", ELAPSED)
                                        printf('%s key=%s.%s ZBXDB-%s: Db execution error: %s\n', \
                                            datetime.datetime.fromtimestamp(time.time()), \
                                            section, key, ecode, emsg.strip())
                                        if error_needs_new_session(config['db_driver'], ecode):
                                            raise
                                    conn.rollback()
                            # end of a section ## time to run the checks again from this section
                            output(config['hostname'], ME[0] + "[query," + section + ",,ela]",
                                   timer() - SectionTimer)
                # dump metric for summed elapsed time of this run
                output(config['hostname'], ME[0] + "[query,,,ela]",
                       timer() - RUNTIMER)
                output(config['hostname'], ME[0] + "[cpu,user]",
                       resource.getrusage(resource.RUSAGE_SELF).ru_utime)
                output(config['hostname'], ME[0] + "[cpu,sys]",
                       resource.getrusage(resource.RUSAGE_SELF).ru_stime)
                output(config['hostname'], ME[0] + "[mem,maxrss]",
                       resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
                # passed all sections
                if ((NOWRUN - STARTTIME) % 3600) == 0:
                    gc.collect()
                    # dump stats
                    printf("%s connect %d times, %d fail; started %d queries, " +
                           "%d fail memrss:%d user:%f sys:%f\n",
                           datetime.datetime.fromtimestamp(time.time()),
                           CONNECTCOUNTER, CONNECTERROR, QUERYCOUNTER, QUERYERROR,
                           resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                           resource.getrusage(resource.RUSAGE_SELF).ru_utime,
                           resource.getrusage(resource.RUSAGE_SELF).ru_stime)
                # now pass data to zabbix, if possible
                if config['to_zabbix_method'] == "zabbix_sender":
                    STOUT = open(config['out_file'] + ".log", "w")
                    RESULT = subprocess.call(config['to_zabbix_args'].split(), \
                        shell=False, stdout=STOUT, stderr=STOUT)
                    if RESULT not in(0, 2):
                        printf("%s zabbix_sender failed: %d\n", \
                            datetime.datetime.fromtimestamp(time.time()), RESULT)
                    else:
                        OUTF.close()
                        # create a datafile / day
                        if datetime.datetime.now().strftime("%H:%M") < "00:10":
                            TOMORROW = datetime.datetime.now() + datetime.timedelta(days=1)
                            Z = open(config['out_file'] + "." + TOMORROW.strftime("%a"), 'w')
                            Z.close()

                        with open(config['out_file'] + "." + \
                                  datetime.datetime.now().strftime("%a"), \
                                  'a') as outfile:
                            with open(config['out_file'], "r") as infile:
                                outfile.write(infile.read())
                        OUTF = open(config['out_file'], "w")

                    STOUT.close()

                # OUTF.close()
                if CRASH > 0:
                    printf("%s crashing due to error %d\n", \
                        datetime.datetime.fromtimestamp(time.time()), \
                        CRASH)
                    sys.exit(CRASH)
                # try to keep activities on the same starting second:
                SLEEPTIME = 60 - ((int(time.time()) - STARTTIME) % 60)
                # printf ("%s DEBUG Sleeping for %d seconds\n", \
                    # datetime.datetime.fromtimestamp(time.time()), SLEEPTIME)
                for i in range(SLEEPTIME):
                    time.sleep(1)
                CONMINS = CONMINS + 1 # not really mins since the checks could
                #                       have taken longer than 1 minute to complete
    except db.DatabaseError as dberr:
        ecode, emsg = errorcode(config['db_driver'], dberr)
        ELAPSED = timer() - START
        if not error_needs_new_session(config['db_driver'], ecode):
            # from a killed session, crashed instance or similar
            CONNECTERROR += 1
            output(config['hostname'], ME[0] + "[connect,status]", ecode)
        # output(config['hostname'], ME[0] + "[uptime]", int(time.time()) - STARTTIME))
        if PERROR != ecode:
            SLEEPC = 0
            SLEEPER = 1
            PERROR = ecode
        SLEEPC += 1
        if SLEEPC >= 10:
            if SLEEPER <= 301:
                # don't sleep longer than 5 mins after connect failures
                SLEEPER += 10
            SLEEPC = 0
        printf('%s: (%d.%d)connection error: %s for %s@%s\n', \
            datetime.datetime.fromtimestamp(time.time()), \
            SLEEPC, SLEEPER, emsg.strip().replace('\n', ' ').replace('\r', ' '), \
            config['username'], config['db_url'])
        time.sleep(SLEEPER)
    except (KeyboardInterrupt, SystemExit):
        OUTF.close()
        raise
