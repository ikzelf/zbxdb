#!/usr/bin/env python
"""
 free clonable from https://github.com/ikzelf/zbxora/
 (@) ronald.rood@ciber.nl follow @ik_zelf on twitter
 follow @zbxdb on twitter
 push your added items/checks using git
 options: -c/--cfile configFile
                     configFile contains config for 1 database and
                                a reference to the checks
          -p/--parameter parametername to list parameter from configFile
               where password shows the decrypted form of password_enc
 NOTE: a section whose name contains 'discover' is considered to be handled
           as a special case for LLD -> json arrays
 NOTE: consider using Oracle Wallet instead of coding credentials in config
 NOTE: run as a regular database client, not a special account like root or oracle
"""
import json
import base64
import collections
import datetime
import time
import sys
import os
import configparser
import resource
import gc
import threading
import importlib
from argparse import ArgumentParser
from timeit import default_timer as timer
import platform
import sqlparse
# from pdb import set_trace
VERSION = "0.76"

def printf(format, *args):
    """just a simple c-style printf function"""
    sys.stdout.write(format % args)
    sys.stdout.flush()

def to_outfile(c, ikey, values):
    """uniform way to generate the output for items"""
    timestamp = int(time.time())
    if os.path.exists(c['out_file']):
        if not c['OUTF']:
            c['OUTF'] = open(c['out_file'], "a")
    else:
        c['OUTF'] = open(c['out_file'], "w")
    c['OUTF'].write(c['hostname'] + " " + ikey + " " + str(timestamp) + " " + str(values)+ "\n")
    c['OUTF'].flush()

class MyConfigParser(configparser.RawConfigParser):
    """strip comments"""
    def __init__(self):
        configparser.RawConfigParser.__init__(self, inline_comment_prefixes=('#', ';'))

def encrypted(plain):
    """encrypt plaintext password"""
    return base64.b64encode(bytes(plain, 'utf-8'))

def decrypted(pw_enc):
    """return decrypted password"""
    return base64.b64decode(pw_enc).decode("utf-8", "ignore")

def get_config(filename):
    """read the specified configuration file"""
    config = {'db_url': "", 'db_type': "", 'db_driver': "", 'instance_type': "rdbms",
              'server': "", 'db_name': "", 'instance_name': "", 'server_port': "",
              'username': "scott", 'password': "tiger", 'role': "normal", 'omode': 0,
              'out_dir': "", 'out_file': "", 'hostname': "", 'checkfile_prefix': "",
              'site_checks': "", 'password_enc': "", 'OUTF': 0,
              'sqltimeout': 0.0}
    CONFIG = MyConfigParser()
    if not os.path.exists(filename):
        raise ValueError("Configfile " + filename + " does not exist")

    INIF = open(filename, 'r')
    CONFIG.read_file(INIF)
    config['db_url'] = CONFIG.get(ME[0], "db_url")
    config['db_type'] = CONFIG.get(ME[0], "db_type")
    config['db_driver'] = CONFIG.get(ME[0], "db_driver")
    config['instance_type'] = CONFIG.get(ME[0], "instance_type")
    config['username'] = CONFIG.get(ME[0], "username")
    try:
        config['password'] = CONFIG.get(ME[0], "password")
    except configparser.NoOptionError:
        config['password'] = ""
    try:
        enc = CONFIG.get(ME[0], "password_enc")
    except configparser.NoOptionError:
        enc = ""
    config['password_enc'] = bytearray(enc, 'utf-8')

    config['role'] = CONFIG.get(ME[0], "role")
    config['out_dir'] = os.path.expandvars(CONFIG.get(ME[0], "out_dir"))
    config['out_file'] = os.path.join(config['out_dir'],
                                      str(os.path.splitext(os.path.basename(filename))[0]) +
                                      ".zbx")
    config['hostname'] = CONFIG.get(ME[0], "hostname")
    config['checksfile_prefix'] = os.path.expandvars(CONFIG.get(ME[0], "checks_dir"))
    config['site_checks'] = ""
    try:
        z = CONFIG.get(ME[0], "site_checks")
        if z != "NONE":
            config['site_checks'] = z
    except configparser.NoOptionError:
        pass
    try:
        config['sqltimeout'] = float(CONFIG.get(ME[0], "sql_timeout"))
    except configparser.NoOptionError:
        config['sqltimeout'] = 60.0
    try:
        config['server'] = CONFIG.get(ME[0], "server")
    except configparser.NoOptionError:
        pass
    try:
        config['server_port'] = CONFIG.get(ME[0], "server_port")
    except configparser.NoOptionError:
        pass
    try:
        config['db_name'] = CONFIG.get(ME[0], "db_name")
    except configparser.NoOptionError:
        pass
    try:
        config['instance_name'] = CONFIG.get(ME[0], "instance_name")
    except configparser.NoOptionError:
        pass

    INIF.close()

    if config['password']:
        enc = encrypted(config['password'])
        INIF = open(filename, 'w')
        CONFIG.set(ME[0], 'password', '')
        CONFIG.set(ME[0], 'password_enc', enc.decode())
        CONFIG.write(INIF)
        INIF.close()

    return config

ME = os.path.splitext(os.path.basename(__file__))
STARTTIME = int(time.time())
PARSER = ArgumentParser()
PARSER.add_argument("-c", "--cfile", dest="configfile", default=ME[0]+".cfg",
                    help="Configuration file", metavar="FILE", required=True)
PARSER.add_argument("-v", "--verbosity", action="count",
                    help="increase output verbosity")
PARSER.add_argument("-p", "--parameter", action="store",
                    help="show parameter from configfile")
ARGS = PARSER.parse_args()

config = get_config(ARGS.configfile)

if ARGS.parameter:
    if ARGS.parameter == 'password':
        print('parameter {}: {}\n'.format(ARGS.parameter,
                                           decrypted(config[ARGS.parameter+'_enc'])))
    else:
        print('parameter {}: {}\n'.format(ARGS.parameter, config[ARGS.parameter]))
    sys.exit(0)

printf("%s start python-%s %s-%s pid=%s Connecting for hostname %s...\n", \
       datetime.datetime.fromtimestamp(STARTTIME), \
       platform.python_version(), ME[0], VERSION, os.getpid(), config['hostname']
      )
if config['password']:
    printf("%s first encrypted the plaintext password and removed from config\n", \
           datetime.datetime.fromtimestamp(STARTTIME)
          )

printf("%s %s found db_type=%s, driver %s; checking for driver\n", \
       datetime.datetime.fromtimestamp(time.time()), ME[0], \
       config['db_type'], config['db_driver'])
try:
    dbdr= __import__(config['db_driver'])
    print(dbdr)
except:
    printf("%s supported will be oracle(cx_Oracle), postgres(psycopg2), \
           mysql(mysql.connector), mssql(pymssql/_mssql), db2(ibm_db_dbi)\n", ME[0])
    printf("%s tested are oracle(cx_Oracle), postgres(psycopg2)\n", ME[0])
    printf("Don't forget to install the drivers first ...\n")
    raise

printf("%s %s driver %s loaded\n",
       datetime.datetime.fromtimestamp(time.time()), ME[0], config['db_driver'])
try:
    dbe = importlib.import_module("drivererrors." + config['db_driver'])
except:
    printf("Failed to load driver error routines\n")
    printf("Looked in %s\n", sys.path)
    raise

printf("%s %s driver drivererrors for %s loaded\n",
       datetime.datetime.fromtimestamp(time.time()), ME[0], config['db_driver'])
try:
    dbc= importlib.import_module("dbconnections." + config['db_type'])
except:
    printf("Failed to load dbconnections routines for %s\n", config['db_type'])
    printf("Looked in %s\n", sys.path)
    raise

printf("%s %s dbconnections for %s loaded\n",
       datetime.datetime.fromtimestamp(time.time()), ME[0], config['db_type'])
print(dbc)
print(dbe)
if ARGS.verbosity:
    printf("%s %s connect string: %s\n",
           datetime.datetime.fromtimestamp(time.time()), ME[0], dbc.connect_string(config))

CHECKFILES = [{'name': __file__, 'lmod': os.stat(__file__).st_mtime},
              {'name': dbc.__file__, 'lmod': os.stat(dbc.__file__).st_mtime},
              {'name': dbe.__file__, 'lmod': os.stat(dbe.__file__).st_mtime}
             ]
CHECKSCHANGED = [0]

CONNECTCOUNTER = 0
CONNECTERROR = 0
QUERYCOUNTER = 0
QUERYERROR = 0
if config['site_checks']:
    printf("%s site_checks: %s\n", \
        datetime.datetime.fromtimestamp(time.time()), config['site_checks'])
printf("%s out_file:%s\n", \
    datetime.datetime.fromtimestamp(time.time()), config['out_file'])
SLEEPC = 0
SLEEPER = 1
PERROR = 0
while True:
    try:
        for i in range(0, 2):
            if CHECKFILES[i]['lmod'] != os.stat(CHECKFILES[i]['name']).st_mtime:
                printf("%s %s changed, restarting ..\n",
                       datetime.datetime.fromtimestamp(time.time()), CHECKFILES[i]['name'])
                os.execv(__file__, sys.argv)

        # reset list in case of a just new connection that reloads the config
        CHECKFILES = [{'name': __file__, 'lmod': os.stat(__file__).st_mtime},
                      {'name': dbc.__file__, 'lmod': os.stat(dbc.__file__).st_mtime},
                      {'name': dbe.__file__, 'lmod': os.stat(dbe.__file__).st_mtime}
                     ]
        config = get_config(ARGS.configfile)
        config['password'] = decrypted(config['password_enc'])

        START = timer()
        if ARGS.verbosity:
            printf('%s connecting to %s\n',
                   datetime.datetime.fromtimestamp(time.time()),
                   dbc.connect_string(config))
        # with dbc.connect(dbdr, config) as conn:
        # pymysql returns a cursor from __enter__() :-(
        conn_has_cancel = False
        conn = dbc.connect(dbdr, config)
        if "cancel" in dir(conn):
            conn_has_cancel = True
        print(conn)
        CONNECTCOUNTER += 1
        to_outfile(config, ME[0]+"[connect,status]", 0)
        CURS = conn.cursor()
        connect_info = dbc.connection_info(conn)
        printf('%s connected db_url %s type %s db_role %s version %s\n'\
               '%s user %s %s sid,serial %d,%d instance %s as %s cancel:%s\n',
               datetime.datetime.fromtimestamp(time.time()), \
               config['db_url'], connect_info['instance_type'], connect_info['db_role'], \
               connect_info['dbversion'], \
               datetime.datetime.fromtimestamp(time.time()), \
               config['username'], connect_info['uname'], connect_info['sid'], \
               connect_info['serial'], \
               connect_info['iname'], \
               config['role'], conn_has_cancel)
        if  connect_info['db_role'] in ["PHYSICAL STANDBY", "SLAVE"]:
            CHECKSFILE = os.path.join(config['checksfile_prefix'], \
                                       config['db_type'], "standby" +
                                      "." + connect_info['dbversion'] +".cfg")
        else:
            CHECKSFILE = os.path.join(config['checksfile_prefix'], \
                                      config['db_type'],
                                      connect_info['db_role'].lower() + "." + \
                                      connect_info['dbversion']+".cfg")

        printf('%s using sql_timeout %d\n',
               datetime.datetime.fromtimestamp(time.time()), \
               config['sqltimeout'])
        FILES = [CHECKSFILE]
        CHECKFILES.append({'name': CHECKSFILE, 'lmod': 0})
        if config['site_checks']:
            for addition in config['site_checks'].split(","):
                addfile = os.path.join(config['checksfile_prefix'], config['db_type'], \
                                       addition + ".cfg")
                CHECKFILES.append({'name': addfile, 'lmod': 0})
                FILES.extend([addfile])
        printf('%s using checks from %s\n',
               datetime.datetime.fromtimestamp(time.time()), FILES)

        for CHECKSFILE in CHECKFILES:
            if not os.path.exists(CHECKSFILE['name']):
                raise ValueError("Configfile " + CHECKSFILE['name']+ " does not exist")
        ## all checkfiles exist

        SLEEPC = 0
        SLEEPER = 1
        PERROR = 0
        CONMINS = 0
        OPENTIME = int(time.time())
        while True:
            if ARGS.verbosity:
                printf("%s %s while True\n",
                       datetime.datetime.fromtimestamp(time.time()), ME[0])
            NOWRUN = int(time.time()) # keep this to compare for when to dump stats
            RUNTIMER = timer() # keep this to compare for when to dump stats
            # loading checks from the various checkfiles:
            NEEDTOLOAD = "no"
            for i in range(len(CHECKFILES)): # at index 0 is the script itself
                # if CHECKSFILE became inaccessible in run -> crash and no output :-(
                # change the CHECKSCHANGED to catch that.
                if CHECKFILES[i]['lmod'] != os.stat(CHECKFILES[i]['name']).st_mtime:
                    if i < 3: # this is the script or module itself that changed
                        printf("%s %s changed, restarting ...\n",
                               datetime.datetime.fromtimestamp(time.time()),
                               CHECKFILES[i]['name'])
                        os.execv(__file__, sys.argv)
                    else:
                        if CHECKFILES[i]['lmod'] == 0:
                            printf("%s checks loading %s\n", \
                                datetime.datetime.fromtimestamp(time.time()),
                                   CHECKFILES[i]['name'])
                            NEEDTOLOAD = "yes"
                        else:
                            printf("%s checks changed, reloading %s\n", \
                                datetime.datetime.fromtimestamp(time.time()),
                                   CHECKFILES[i]['name'])
                            NEEDTOLOAD = "yes"

            if NEEDTOLOAD == "yes":
                to_outfile(config, ME[0] + "[version]", VERSION)
                to_outfile(config, ME[0] + "[config,db_type]", config['db_type'])
                to_outfile(config, ME[0] + "[config,db_driver]", config['db_driver'])
                to_outfile(config, ME[0] + "[config,instance_type]",
                           config['instance_type'])
                to_outfile(config, ME[0] + "[conn,db_role]",
                           connect_info['db_role'])
                to_outfile(config, ME[0] + "[conn,instance_type]",
                           connect_info['instance_type'])
                to_outfile(config, ME[0] + "[conn,dbversion]",
                           connect_info['dbversion'])
                OBJECTS_LIST = []
                SECTIONS_LIST = []
                FILES_LIST = []
                ALL_CHECKS = []
                for i in range(len(CHECKFILES)):
                    E = collections.OrderedDict()
                    E = {"{#CHECKS_FILE}": i}
                    FILES_LIST.append(E)

                FILES_JSON = '{\"data\":'+json.dumps(FILES_LIST)+'}'
                to_outfile(config, ME[0]+".files.lld", FILES_JSON)
                for i in range(3, len(CHECKFILES)):
                    # #0 is executable that is also checked for updates
                    # #1 dbc module
                    # #2 dbe module
                    CHECKS = configparser.RawConfigParser()
                    try:
                        CHECKSF = open(CHECKFILES[i]['name'], 'r')
                        to_outfile(config, ME[0] + "[checks," + str(i) + \
                               ",name]", CHECKFILES[i]['name'])
                        to_outfile(config, ME[0] + "[checks," + str(i) + \
                               ",lmod]",
                                   str(int(os.stat(CHECKFILES[i]['name']).st_mtime)))
                        try:
                            CHECKS.read_file(CHECKSF)
                            CHECKSF.close()
                            to_outfile(config, ME[0] + "[checks," + str(i) + \
                                   ",status]", 0)
                        except configparser.Error:
                            to_outfile(config, ME[0] + "[checks," + str(i) + \
                                   ",status]", 13)
                            printf("%s\tfile %s has parsing errors %s %s ->(13)\n",
                                   datetime.datetime.fromtimestamp(time.time()),
                                   CHECKFILES[i]['name'])
                    except IOError as io_error:
                        to_outfile(config, ME[0] + "[checks," + str(i) + ",status]", 11)
                        printf("%s\tfile %s IOError %s %s ->(11)\n",
                               datetime.datetime.fromtimestamp(time.time()),
                               CHECKFILES[i]['name'],
                               io_error.errno, io_error.strerror)

                    CHECKFILES[i]['lmod'] = os.stat(CHECKFILES[i]['name']).st_mtime
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
                        for key, sqls  in sorted(x.items()):
                            if sqls and key != "minutes":
                                d = collections.OrderedDict()
                                d = {"{#SECTION}": section, "{#KEY}": key}
                                OBJECTS_LIST.append(d)
                                printf("%s\t\t%s: %s\n", \
                                    datetime.datetime.fromtimestamp(time.time()), \
                                    key, sqls[0 : 60].replace('\n', ' ').replace('\r', ' '))
                # checks are loaded now.
                SECTIONS_JSON = '{\"data\":'+json.dumps(SECTIONS_LIST)+'}'
                # printf ("DEBUG lld key: %s json: %s\n", ME[0]+".lld", ROWS_JSON)
                to_outfile(config, ME[0]+".section.lld", SECTIONS_JSON)
                ROWS_JSON = '{\"data\":'+json.dumps(OBJECTS_LIST)+'}'
                # printf ("DEBUG lld key: %s json: %s\n", ME[0]+".lld", ROWS_JSON)
                to_outfile(config, ME[0] + ".query.lld", ROWS_JSON)
                # sqls can contain multiple statements per key. sqlparse to split them
                # now. Otherwise use a lot of extra cycles when splitting at runtime
                # all_sql { {section, key}: statements }
                all_sql = {}
                for CHECKS in ALL_CHECKS:
                    for section in sorted(CHECKS.sections()):
                        x = dict(CHECKS.items(section))
                        for key, sqls in sorted(x.items()):
                            if sqls and key != "minutes":
                                all_sql[(section, key)] = []
                                for statement in sqlparse.split(sqls):
                                    all_sql[(section, key)].append(statement)

            # checks discovery is also printed
            #
            # assume we are still connected. If not, exception will tell real story
            to_outfile(config, ME[0] + "[connect,status]", 0)
            to_outfile(config, ME[0] + "[uptime]", int(time.time() - STARTTIME))
            to_outfile(config, ME[0] + "[opentime]", int(time.time() - OPENTIME))

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
                        for key, sqls  in sorted(x.items()):
                            if sqls and key != "minutes":
                                if ARGS.verbosity:
                                    printf("%s %s section: %s key: %s\n",
                                           datetime.datetime.fromtimestamp(time.time()), ME[0],
                                           section, key)
                                try:
                                    QUERYCOUNTER += 1
                                    if conn_has_cancel:
                                        # pymysql has no cancel but does have timeout in connect
                                        sqltimeout = threading.Timer(config['sqltimeout'],
                                                                     conn.cancel)
                                        sqltimeout.start()
                                    START = timer()
                                    for statement in all_sql[(section, key)]:
                                        lstatement = statement
                                        if ARGS.verbosity and ARGS.verbosity > 1:
                                            printf("%s %s section: %s key: %s sql: %s\n",
                                                   datetime.datetime.fromtimestamp(time.time()),
                                                   ME[0],
                                                   section, key, statement)
                                        CURS.execute(statement)
                                    startf = timer()
                                    # output for the last query must include the
                                    # output for the preparing queries is ignored
                                    #        complete key and value
                                    rows = CURS.fetchall()
                                    if conn_has_cancel:
                                        sqltimeout.cancel()
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
                                        to_outfile(config, key, ROWS_JSON)
                                        to_outfile(config, ME[0] + \
                                               "[query," + section + "," + \
                                          key + ",status]", 0)
                                    else:
                                        if  rows and len(rows[0]) == 2:
                                            for row in rows:
                                                to_outfile(config, row[0], row[1])
                                            to_outfile(config, ME[0] +
                                                       "[query," + section + "," +
                                                       key + ",status]", 0)
                                        elif not rows:
                                            to_outfile(config, ME[0] + "[query," +
                                                       section + "," +
                                                       key + ",status]", 0)
                                        else:
                                            printf('%s key=%s.%s ZBXDB-%d: ' +
                                                   'SQL format error: %s\n',
                                                   datetime.datetime.fromtimestamp(time.time()),
                                                   section, key, 2, "expect key,value pairs")
                                            to_outfile(config, ME[0] +
                                                       "[query," + section + "," +
                                                       key + ",status]", 2)
                                    fetchela = timer() - startf
                                    ELAPSED = timer() - START
                                    to_outfile(config, ME[0] + "[query," +
                                               section + "," +
                                               key + ",ela]", ELAPSED)
                                    to_outfile(config, ME[0] + "[query," +
                                               section + "," +
                                               key + ",fetch]", fetchela)
                                except dbdr.DatabaseError as dberr:
                                    if conn_has_cancel:
                                        sqltimeout.cancel()
                                    ecode, emsg = dbe.db_errorcode(dbdr, dberr)

                                    ELAPSED = timer() - START
                                    QUERYERROR += 1
                                    to_outfile(config, ME[0] + "[query," + \
                                           section + "," + \
                                        key + ",status]", ecode)
                                    to_outfile(config, ME[0] + "[query," + \
                                           section + "," + \
                                        key + ",ela]", ELAPSED)
                                    printf('%s key=%s.%s ZBXDB-%s: Db execution error: %s\n', \
                                        datetime.datetime.fromtimestamp(time.time()), \
                                        section, key, ecode, emsg.strip())
                                    if dbe.db_error_needs_new_session(dbdr,
                                                                      ecode):
                                        raise
                                    if ARGS.verbosity:
                                        printf("%s %s rollback\n",
                                               datetime.datetime.fromtimestamp(time.time()), ME[0])
                                    conn.rollback()
                                    if ARGS.verbosity:
                                        printf("%s %s rolledback\n",
                                               datetime.datetime.fromtimestamp(time.time()), ME[0])
                        # end of a section ## time to run the checks again from this section
                        to_outfile(config, ME[0] + "[query," + section + ",,ela]",
                                   timer() - SectionTimer)
            # release locks that might have been taken
            if ARGS.verbosity:
                printf("%s %s rollback\n",
                       datetime.datetime.fromtimestamp(time.time()), ME[0])

            conn.rollback()
            if ARGS.verbosity:
                printf("%s %s rolledback\n",
                       datetime.datetime.fromtimestamp(time.time()), ME[0])
            # dump metric for summed elapsed time of this run
            to_outfile(config, ME[0] + "[query,,,ela]",
                       timer() - RUNTIMER)
            to_outfile(config, ME[0] + "[cpu,user]",
                       resource.getrusage(resource.RUSAGE_SELF).ru_utime)
            to_outfile(config, ME[0] + "[cpu,sys]",
                       resource.getrusage(resource.RUSAGE_SELF).ru_stime)
            to_outfile(config, ME[0] + "[mem,maxrss]",
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
            # try to keep activities on the same starting second:
            SLEEPTIME = 60 - ((int(time.time()) - STARTTIME) % 60)
            if ARGS.verbosity:
                printf("%s Sleeping for %d seconds\n", \
                    datetime.datetime.fromtimestamp(time.time()), SLEEPTIME)
            time.sleep(SLEEPTIME)
            CONMINS = CONMINS + 1 # not really mins since the checks could
            #                       have taken longer than 1 minute to complete
    except dbdr.DatabaseError as dberr:
        ecode, emsg = dbe.db_errorcode(dbdr, dberr)
        ELAPSED = timer() - START
        to_outfile(config, ME[0] + "[connect,status]", ecode)
        if not dbe.db_error_needs_new_session(dbdr, ecode):
            # from a killed session, crashed instance or similar
            CONNECTERROR += 1
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
        printf('%s: (%d.%d)connection error: [%s] %s for %s@%s\n', \
            datetime.datetime.fromtimestamp(time.time()), \
            SLEEPC, SLEEPER, ecode, emsg.strip().replace('\n', ' ').replace('\r', ' '), \
            config['username'], config['db_url'])
        # set_trace()
        time.sleep(SLEEPER)
    except (KeyboardInterrupt, SystemExit):
        raise
