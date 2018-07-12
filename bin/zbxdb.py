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
import base64
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
import importlib
import sqlparse
from argparse import ArgumentParser
from timeit import default_timer as timer
import platform
from pdb import set_trace
VERSION = "0.14"

def printf(format, *args):
    """just a simple c-style printf function"""
    sys.stdout.write(format % args)
    sys.stdout.flush()

def output(host, ikey, values):
    """uniform way to generate the output for items"""
    timestamp = int(time.time())
    OUTF.write(host + " " + ikey + " " + str(timestamp) + " " + str(values)+ "\n")
    OUTF.flush()

class MyConfigParser(configparser.RawConfigParser):
    def __init__(self):
      configparser.RawConfigParser.__init__(self, inline_comment_prefixes=('#', ';'))

def encrypted(plain):
    """encrypt plaintext password"""
    return base64.b64encode(bytes(plain,'utf-8'))

def decrypted(pw_enc):
    return base64.b64decode(pw_enc).decode("utf-8", "ignore")  

def get_config(filename):
    """read the specified configuration file"""
    config = {'db_url': "", 'db_type': "", 'db_driver': "", 'instance_type': "rdbms",
              'server': "", 'db_name': "", 'instance_name': "", 'server_port': "",
              'username': "scott", 'password': "tiger", 'role': "normal", 'omode': 0,
              'out_dir': "", 'out_file': "", 'hostname': "", 'checkfile_prefix': "",
              'site_checks': "",'password_enc': "",
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
    config['checksfile_prefix'] = CONFIG.get(ME[0], "checks_dir")
    config['site_checks'] = CONFIG.get(ME[0], "site_checks")
    try:
        config['sqltimeout'] = float(CONFIG.get(ME[0], "sql_timeout"))
    except configparser.NoOptionError:
        config['sqltimeout'] = 60.0
    try:
        config['server'] = CONFIG.get(ME[0], "server")
    except:
        pass
    try:
        config['server_port'] = CONFIG.get(ME[0], "server_port")
    except:
        pass
    try:
        config['db_name'] = CONFIG.get(ME[0], "db_name")
    except:
        pass
    try:
        config['instance_name'] = CONFIG.get(ME[0], "instance_name")
    except:
        pass

    INIF.close()
    
    if config['password']:
        enc=encrypted(config['password'])
        INIF = open(filename, 'w')
        CONFIG.set(ME[0],'password','')
        CONFIG.set(ME[0],'password_enc',enc.decode())
        CONFIG.write(INIF)
        INIF.close()

    return config

ME = os.path.splitext(os.path.basename(__file__))
STARTTIME = int(time.time())
PARSER = ArgumentParser()
PARSER.add_argument("-c", "--cfile", dest="configfile", default=ME[0]+".cfg",
                    help="Configuration file", metavar="FILE")
PARSER.add_argument("-v", "--verbosity", action="count",
                    help="increase output verbosity")
ARGS = PARSER.parse_args()

config = get_config(ARGS.configfile)
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
  db= __import__(config['db_driver'])
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

CHECKFILES = [[__file__, os.stat(__file__).st_mtime]]
CHECKSCHANGED = [0]

CONNECTCOUNTER = 0
CONNECTERROR = 0
QUERYCOUNTER = 0
QUERYERROR = 0
if config['site_checks'] != "NONE":
    printf("%s site_checks: %s\n", \
        datetime.datetime.fromtimestamp(time.time()), config['site_checks'])
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
        config['password'] = decrypted(config['password_enc'])
        if os.path.exists(config['out_file']):
            OUTF = open(config['out_file'], "a")
        else:
            OUTF = open(config['out_file'], "w")

        START = timer()
        if ARGS.verbosity:
            printf('%s connecting to %s\n',
                   datetime.datetime.fromtimestamp(time.time()),
                   dbc.connect_string(config))
        with dbc.connect(db, config) as conn:
            CONNECTCOUNTER += 1
            output(config['hostname'], ME[0]+"[connect,status]", 0)
            CURS = conn.cursor()
            connect_info = dbc.connection_info(conn)
            printf('%s connected db_url %s type %s db_role %s version %s\n'\
                   '%s user %s %s sid,serial %d,%d instance %s as %s\n',
                   datetime.datetime.fromtimestamp(time.time()), \
                   config['db_url'], connect_info['instance_type'], connect_info['db_role'], \
                   connect_info['dbversion'], \
                   datetime.datetime.fromtimestamp(time.time()), \
                   config['username'], connect_info['uname'], connect_info['sid'], \
                   connect_info['serial'], \
                   connect_info['iname'], \
                   config['role'])
            if  connect_info['db_role'] in ["PHYSICAL STANDBY", "SLAVE"]:
                CHECKSFILE = os.path.join(config['checksfile_prefix'], \
                                           config['db_type'], "standby" +
                                           "." + connect_info['dbversion'] +".cfg")
            else:
                CHECKSFILE = os.path.join(config['checksfile_prefix'], \
                                          config['db_type']  ,
                                          connect_info['db_role'].lower() + "." + \
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
                    output(config['hostname'], ME[0] + "[version]", VERSION)
                    output(config['hostname'], ME[0] + "[config,db_type]", config['db_type'])
                    output(config['hostname'], ME[0] + "[config,db_driver]", config['db_driver'])
                    output(config['hostname'], ME[0] + "[config,instance_type]", config['instance_type'])
                    output(config['hostname'], ME[0] + "[conn,db_role]", connect_info['db_role'])
                    output(config['hostname'], ME[0] + "[conn,instance_type]", connect_info['instance_type'])
                    output(config['hostname'], ME[0] + "[conn,dbversion]", connect_info['dbversion'])
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
                            for key, sqls  in sorted(x.items()):
                                if sqls and key != "minutes":
                                    if ARGS.verbosity:
                                        printf("%s %s section: %s key: %s\n",
                                           datetime.datetime.fromtimestamp(time.time()), ME[0],
                                               section, key)
                                    try:
                                        QUERYCOUNTER += 1
                                        sqltimeout = threading.Timer(config['sqltimeout'], \
                                                                     conn.commit)
                                        sqltimeout.start()
                                        START = timer()
                                        for statement in sqlparse.split(sqls):
                                            if ARGS.verbosity and ARGS.verbosity > 1:
                                                printf("%s %s section: %s key: %s sql: %s\n",
                                                   datetime.datetime.fromtimestamp(time.time()), ME[0],
                                                       section, key, statement)
                                            CURS.execute(statement)
                                        startf = timer()
                                        # output for the last query must include the
                                        # output for the preparing queries is ignored
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
                                        ecode, emsg = dbe.db_errorcode(config['db_driver'], dberr)

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
                                        if dbe.db_error_needs_new_session(config['db_driver'], ecode):
                                            raise
                            # end of a section ## time to run the checks again from this section
                            output(config['hostname'], ME[0] + "[query," + section + ",,ela]",
                                   timer() - SectionTimer)
                # release locks that might have been taken
                conn.rollback()
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
        ecode, emsg = dbe.db_errorcode(config['db_driver'], dberr)
        ELAPSED = timer() - START
        output(config['hostname'], ME[0] + "[connect,status]", ecode)
        if not dbe.db_error_needs_new_session(config['db_driver'], ecode):
            # from a killed session, crashed instance or similar
            CONNECTERROR += 1
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
        printf('%s: (%d.%d)connection error: [%s] %s for %s@%s\n', \
            datetime.datetime.fromtimestamp(time.time()), \
            SLEEPC, SLEEPER, ecode, emsg.strip().replace('\n', ' ').replace('\r', ' '), \
            config['username'], config['db_url'])
        time.sleep(SLEEPER)
    except (KeyboardInterrupt, SystemExit):
        OUTF.close()
        raise
