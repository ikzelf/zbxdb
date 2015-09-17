#!/usr/bin/env python
"""options: -c/--cfile configFile
                     configFile contains config for 1 database and
                                a reference to the checks"""
"""NOTE: a section whose name contains 'discover' is considered to be handled
           as a special case for LLD -> json arrays
"""
# changes: rrood 0.01:20150915 STARTTIME with a copy of zbxora-0.44
VERSION = "0.01"
import json
import collections
import datetime
import time
import sys
import os
import ConfigParser
import resource
import gc
import subprocess
from optparse import OptionParser
from timeit import default_timer as timer

def printf(format, *args):
    """just a simple c-style printf function"""
    sys.stdout.write(format % args)
    sys.stdout.flush()

def output(host, key, values):
    """uniform way to generate the output"""
    timestamp = int(time.time())
    OUTF.write(host + " " + key + " " + str(timestamp) + " " + str(values)+ "\n")
    OUTF.flush()

ME = os.path.splitext(os.path.basename(__file__))
PARSER = OptionParser()
PARSER.add_option("-c", "--cfile", dest="configfile", default=ME[0]+".cfg",
                  help="Configuration file", metavar="FILE")
(OPTIONS, ARGS) = PARSER.parse_args()

CONFIG = ConfigParser.RawConfigParser()
if not os.path.exists(OPTIONS.configfile):
    raise ValueError("Configfile " + OPTIONS.configfile + " does not exist")

INIF = open(OPTIONS.configfile, 'r')
CONFIG.readfp(INIF)
DB_URL = CONFIG.get(ME[0], "db_url")
DB_TYPE = CONFIG.get(ME[0], "db_type")
DB_DRIVER = CONFIG.get(ME[0], "db_driver")
USERNAME = CONFIG.get(ME[0], "username")
PASSWORD = CONFIG.get(ME[0], "password")
ROLE = CONFIG.get(ME[0], "role")
OUT_DIR = os.path.expandvars(CONFIG.get(ME[0], "out_dir"))
OUT_FILE = os.path.join(OUT_DIR, str(os.path.splitext(os.path.basename(OPTIONS.configfile))[0]) + ".zbx")
HOSTNAME = CONFIG.get(ME[0], "hostname")
CHECKSFILE_PREFIX = CONFIG.get(ME[0], "checks_dir")
SITE_CHECKS = CONFIG.get(ME[0], "site_checks")
TO_ZABBIX_METHOD = CONFIG.get(ME[0], "to_zabbix_method")
TO_ZABBIX_ARGS = os.path.expandvars(CONFIG.get(ME[0], "to_zabbix_args")) + " " + OUT_FILE
INIF.close()

printf("%s %s found db_type=%s, driver %s; checking for driver\n",
    datetime.datetime.fromtimestamp(time.time()), ME[0], DB_TYPE, DB_DRIVER)
try:
  db= __import__(DB_DRIVER)
except:
  printf("%s supported are oracle(cx_Oracle), postgres(psycopg2), mysql(mysql.connector), mssql(pymssql), db2(ibm_db_dbi)\n", ME[0])
  printf("Don't forget to install the drivers first ...\n")
  raise

printf("%s %s driver loaded\n", 
    datetime.datetime.fromtimestamp(time.time()), ME[0])
CHECKSCHANGED = [ 0 ]

CONNECTCOUNTER = 0
CONNECTERROR = 0
QUERYCOUNTER = 0
QUERYERROR = 0
STARTTIME = int(time.time())
printf("%s start %s-%s pid=%s Connecting...\n", \
    datetime.datetime.fromtimestamp(time.time()), \
    ME[0], VERSION, os.getpid())
if SITE_CHECKS != "NONE":
    printf("%s site_checks: %s\n", \
        datetime.datetime.fromtimestamp(time.time()), SITE_CHECKS)
printf("%s to_zabbix_method: %s %s\n", \
    datetime.datetime.fromtimestamp(time.time()), TO_ZABBIX_METHOD, TO_ZABBIX_ARGS)
printf("%s out_file:%s\n", \
    datetime.datetime.fromtimestamp(time.time()), OUT_FILE)
SLEEPC = 0
SLEEPER = 1
PERROR = 0
while True:
    try:
        CONFIG = ConfigParser.RawConfigParser()
        INIF = open(OPTIONS.configfile, 'r')
        CONFIG.readfp(INIF)
        DB_URL = CONFIG.get(ME[0], "db_url")
        USERNAME = CONFIG.get(ME[0], "username")
        PASSWORD = CONFIG.get(ME[0], "password")
        ROLE = CONFIG.get(ME[0], "role")
        OUT_DIR = os.path.expandvars(CONFIG.get(ME[0], "out_dir"))
        OUT_FILE = os.path.join(OUT_DIR, str(os.path.splitext(os.path.basename(OPTIONS.configfile))[0]) + ".zbx")
        HOSTNAME = CONFIG.get(ME[0], "hostname")
        CHECKSFILE_PREFIX = CONFIG.get(ME[0], "checks_dir")
        SITE_CHECKS = CONFIG.get(ME[0], "site_checks")
        TO_ZABBIX_METHOD = CONFIG.get(ME[0], "to_zabbix_method")
        TO_ZABBIX_ARGS = os.path.expandvars(CONFIG.get(ME[0], "to_zabbix_args")) + " " + OUT_FILE
        if os.path.exists(OUT_FILE):
            OUTF = open(OUT_FILE, "a")
        else:
            OUTF = open(OUT_FILE, "w")

        OMODE = 0
        if ROLE.upper() == "SYSASM":
            OMODE = db.SYSASM
        if ROLE.upper() == "SYSDBA":
            OMODE = db.SYSDBA

        if SLEEPC == 0:
            printf('%s connecting db_url:%s, type:%s, user:%s as %s\n',
                    datetime.datetime.fromtimestamp(time.time()), \
                    DB_URL, DB_TYPE, USERNAME, ROLE)
        if DB_TYPE == "oracle":
            CS = USERNAME + "/" + PASSWORD + "@" + DB_URL + " as " + ROLE.upper()
        elif DB_TYPE == "postgres":
          CS = "postgresql://" + USERNAME + ":" + PASSWORD + "@" + DB_URL

        # print CS

        START = timer()
        with db.connect( CS ) as conn:
            CONNECTCOUNTER += 1
            output(HOSTNAME, ME[0]+"[connect,status]", 0)
            CURS = conn.cursor()
            try:
                if DB_TYPE == "oracle":
                    CURS.execute("""select substr(i.version,0,instr(i.version,'.')-1),
                      s.sid, s.serial#, p.value instance_type, i.instance_name
                      , s.username
                      from v$instance i, v$session s, v$parameter p 
                      where s.sid = (select sid from v$mystat where rownum = 1)
                      and p.name = 'instance_type'""" )
                elif DB_TYPE == "postgres":
                    CURS.execute("select substring(version from '[0-9]+') from version()")

                DATA = CURS.fetchone()
                DBVERSION = DATA[0]

                if DB_TYPE == "oracle":
                    MYSID = DATA[1]
                    MYSERIAL = DATA[2]
                    ITYPE = DATA[3]
                    INAME = DATA[4]
                    UNAME = DATA[5]
                else:
                    MYSID = 0
                    MYSERIAL = 0
                    ITYPE = "rdbms"
                    INAME = ""
                    UNAME = ""

            except db.DatabaseError as oerr:
                ERROR, = oerr.args
                if ERROR.code == 904:
                    DBVERSION = "pre9"
                else:
                    DBVERSION = "unk"
            if DB_TYPE == "oracle" and ITYPE == "RDBMS":
                CURS.execute("""select database_role from v$database""" )
                DATA = CURS.fetchone()
                DBROL = DATA[0]
            elif DB_TYPE == "oracle":
                DBROL = "asm"
            else:
                DBROL = "primary"
            CURS.close()

            printf('%s connected db_url %s type %s db_role %s version %s\n%s user %s %s sid,serial %d,%d instance %s as %s\n',
                    datetime.datetime.fromtimestamp(time.time()), \
                    DB_URL, ITYPE, DBROL, DBVERSION, \
                    datetime.datetime.fromtimestamp(time.time()), \
                    USERNAME, UNAME, MYSID, MYSERIAL, \
                    INAME, \
                    ROLE)
            if  DBROL == "PHYSICAL STANDBY":
                CHECKSFILE = os.patch.join(CHECKSFILE_PREFIX, DB_TYPE, "standby" + "." + DBVERSION+".cfg")
            else:
                CHECKSFILE = os.path.join(CHECKSFILE_PREFIX, DB_TYPE  , DBROL + "." + DBVERSION+".cfg")

            files= [ CHECKSFILE ]
            CHECKFILES = [ [ CHECKSFILE, 0]  ]
            if SITE_CHECKS != "NONE":
                for addition in SITE_CHECKS.split(","):
                    addfile= os.path.join(CHECKSFILE_PREFIX, DB_TYPE,  addition + ".cfg")
                    CHECKFILES.extend( [ [ addfile, 0] ] )
                    files.extend( [ addfile ] )
            printf('%s using checks from %s\n',
                    datetime.datetime.fromtimestamp(time.time()), files)

            for CHECKSFILE in CHECKFILES:
              if not os.path.exists(CHECKSFILE[0]):
                  raise ValueError("Configfile " + CHECKSFILE[0]+ " does not exist")
            ## all checkfiles exist

            SLEEPC = 0
            SLEEPER = 1
            PERROR = 0
            CONMINS = 0
            while True:
                NOWRUN = int(time.time()) # keep this to compare for when to dump stats
                RUNTIMER = timer() # keep this to compare for when to dump stats
                if os.path.exists(OUT_FILE):
                    OUTF = open(OUT_FILE, "a")
                else:
                    OUTF = open(OUT_FILE, "w")
                output(HOSTNAME, ME[0] + "[version]", VERSION)
                # loading checks from the various checkfiles:
                needToLoad = "no"
                for i in range(len(CHECKFILES)):
                    z=CHECKFILES[i]
                    CHECKSFILE = z[0]
                    CHECKSCHANGED = z[1]
                    if CHECKSCHANGED != os.stat(CHECKSFILE).st_mtime:
                        if CHECKSCHANGED == 0:
                            printf("%s checks loading %s\n", \
                                datetime.datetime.fromtimestamp(time.time()), CHECKSFILE)
                            needToLoad = "yes"
                        else:
                            printf("%s checks changed, reloading %s\n", \
                                datetime.datetime.fromtimestamp(time.time()), CHECKSFILE)
                            needToLoad = "yes"
                    
                if needToLoad == "yes":
                    OBJECTS_LIST = []
                    SECTIONS_LIST = []
                    for i in range(len(CHECKFILES)):
                        z=CHECKFILES[i]
                        CHECKSFILE = z[0]
                        CHECKSF = open(CHECKSFILE, 'r')
                        CHECKS = ConfigParser.RawConfigParser()
                        CHECKS.readfp(CHECKSF)
                        CHECKSF.close()
                        z[1]= os.stat(CHECKSFILE).st_mtime
                        CHECKFILES[i] = z
                        for section in sorted(CHECKS.sections()):
                            printf("%s\t%s run every %d minutes\n", \
                                datetime.datetime.fromtimestamp(time.time()), section, \
                                int(CHECKS.get(section, "minutes")))
                            # dump own discovery items of the queries per section
                            E = collections.OrderedDict()
                            E = {"{#SECTION}": section}
                            SECTIONS_LIST.append(E)
                            x = dict(CHECKS.items(section))
                            for key, sql  in sorted(x.iteritems()):
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
                    output(HOSTNAME, ME[0]+".section.lld", SECTIONS_JSON)
                    ROWS_JSON = '{\"data\":'+json.dumps(OBJECTS_LIST)+'}'
                    # printf ("DEBUG lld key: %s json: %s\n", ME[0]+".lld", ROWS_JSON)
                    output(HOSTNAME, ME[0] + ".query.lld", ROWS_JSON)
                # checks discovery is also printed
                #
                # assume we are still connected. If not, exception will tell real story
                output(HOSTNAME, ME[0] + "[connect,status]", 0)
                # the connect status is only real if executed a query ....
                for section in sorted(CHECKS.sections()):
                    SectionTimer = timer() # keep this to compare for when to dump stats
                    if CONMINS % int(CHECKS.get(section, "minutes")) == 0:
                        ## time to run the checks again from this section
                        x = dict(CHECKS.items(section))
                        CURS = conn.cursor()
                        for key, sql  in sorted(x.iteritems()):
                            if sql and key != "minutes":
                                # printf ("%s DEBUG Running %s.%s\n", \
                                    # datetime.datetime.fromtimestamp(time.time()), section, key)
                                try:
                                    QUERYCOUNTER += 1
                                    START = timer()
                                    CURS.execute(sql)
                                    startf = timer()
                                    # output for the query must include the complete key and value
                                    #
                                    rows = CURS.fetchall()
                                    if "discover" in section:
                                        OBJECTS_LIST = []
                                        for row in rows:
                                            d = collections.OrderedDict()
                                            for col in range(0, len(CURS.description)):
                                                d[CURS.description[col][0]] = row[col]
                                            OBJECTS_LIST.append(d)
                                        ROWS_JSON = '{\"data\":'+json.dumps(OBJECTS_LIST)+'}'
                                        # printf ("DEBUG lld key: %s json: %s\n", key, ROWS_JSON)
                                        output(HOSTNAME, key, ROWS_JSON)
                                        output(HOSTNAME, ME[0] + "[query," + section + "," + \
                                            key + ",status]", 0)
                                    else:
                                      if  len(rows) > 0 and len(rows[0]) == 2:
                                            for row in rows:
                                                # printf("DEBUG zabbix_host:%s zabbix_key:%s " + \
                                                    # "value:%s\n", HOSTNAME, row[0], row[1])
                                                output(HOSTNAME, row[0], row[1])
                                            output(HOSTNAME, ME[0] + "[query," + section + "," + \
                                                key + ",status]", 0)
                                      elif len(rows) == 0:
                                            output(HOSTNAME, ME[0] + "[query," + section + "," + \
                                                 key + ",status]", 0)
                                      else:
                                            printf('%s key=%s.%s zbxORA-%d: SQL format error: %s\n', \
                                                  datetime.datetime.fromtimestamp(time.time()), \
                                                  section, key, 2, "expect key,value pairs")
                                            output(HOSTNAME, ME[0] + "[query," + section + "," + \
                                                 key + ",status]", 2)
                                    fetchela = timer() - startf
                                    ELAPSED = timer() - START
                                    output(HOSTNAME, ME[0] + "[query," + section + "," + \
                                        key + ",ela]", ELAPSED)
                                    output(HOSTNAME, ME[0] + "[query," + section + "," + \
                                        key + ",fetch]", fetchela)
                                except db.DatabaseError, err:
                                    if DB_DRIVER == "psycopg2":
                                        errno= int(''.join(c for c in err.pgcode if c.isdigit()))
                                        ermsg= err.pgerror
                                    else:
                                        errno= err.code
                                        ermsg= err.message
                                        
                                    ELAPSED = timer() - START
                                    QUERYERROR += 1
                                    output(HOSTNAME, ME[0] + "[query," + section + "," + \
                                        key + ",status]", errno)
                                    printf('%s key=%s.%s ZBX-%d: Database execution error: %s\n', \
                                        datetime.datetime.fromtimestamp(time.time()), \
                                        section, key, errno, ermsg.strip().replace('\n',' ').replace('\r',' ') )
                                    if errno in(28, 1012, 3113, 3114, 3135):
                                        raise
                        # end of a section
                        output(HOSTNAME, ME[0] + "[query," + section + ",,ela]", \
                            timer() - SectionTimer)
                # dump metric for summed elapsed time of this run
                output(HOSTNAME, ME[0] + "[query,,,ela]", timer() - RUNTIMER)
                output(HOSTNAME, ME[0] + "[cpu,user]",  resource.getrusage(resource.RUSAGE_SELF).ru_utime)
                output(HOSTNAME, ME[0] + "[cpu,sys]",  resource.getrusage(resource.RUSAGE_SELF).ru_stime)
                output(HOSTNAME, ME[0] + "[mem,maxrss]",  resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
                # passed all sections
                if ((NOWRUN - STARTTIME) % 3600) == 0:
                    gc.collect()
                    # dump stats
                    printf("%s connect %d times, %d fail; started %d queries, " + \
                        "%d fail memrss:%d user:%f sys:%f\n", \
                        datetime.datetime.fromtimestamp(time.time()), \
                        CONNECTCOUNTER, CONNECTERROR, QUERYCOUNTER, QUERYERROR, \
                        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, \
                        resource.getrusage(resource.RUSAGE_SELF).ru_utime, \
                        resource.getrusage(resource.RUSAGE_SELF).ru_stime)
                # now pass data to zabbix, if possible
                if TO_ZABBIX_METHOD == "zabbix_sender":
                    STOUT = open(OUT_FILE + ".log", "w")
                    RESULT = subprocess.call(TO_ZABBIX_ARGS.split(), \
                        shell=False, stdout=STOUT, stderr=STOUT)
                    if RESULT not in(0, 2):
                        printf("%s zabbix_sender failed: %d\n", \
                            datetime.datetime.fromtimestamp(time.time()), RESULT)
                    else:
                        OUTF.close()
                        # create a datafile / day
                        if datetime.datetime.now().strftime("%H:%M") < "00:10":
                            TOMORROW = datetime.datetime.now() + datetime.timedelta(days=1)
                            Z = open(OUT_FILE + "." + TOMORROW.strftime("%a"), 'w')
                            Z.close()

                        with open(OUT_FILE + "." + datetime.datetime.now().strftime("%a"), \
                            'a') as outfile:
                            with open(OUT_FILE, "r") as infile:
                                outfile.write(infile.read())
                        OUTF = open(OUT_FILE, "w")

                    STOUT.close()

                OUTF.close()
                # try to keep activities on the same starting second:
                SLEEPTIME = 60 - ((int(time.time()) - STARTTIME) % 60)
                # printf ("%s DEBUG Sleeping for %d seconds\n", \
                    # datetime.datetime.fromtimestamp(time.time()), SLEEPTIME)
                for i in range(SLEEPTIME):
                    time.sleep(1)
                CONMINS = CONMINS + 1 # not really mins since the checks could
                #                       have taken longer than 1 minute to complete
    except db.DatabaseError, err:
        if DB_DRIVER == "psycopg2":
            if err.pgcode is None:
                errno= 13
                ermsg= str(err)
            else:
                errno= int(''.join(c for c in err.pgcode if c.isdigit()))
                ermsg= err.pgerror
        else:
            x, = err.args
            errno= x.code
            ermsg= x.message
        ELAPSED = timer() - START
        if errno not in (1012, 3114):
            # from a killed session or similar
            CONNECTERROR += 1
        output(HOSTNAME, ME[0] + "[connect,status]", errno)
        if errno == 15000:
            printf('%s: connection error: %s for %s@%s %s\n', \
                datetime.datetime.fromtimestamp(time.time()), \
                ermsg.strip().replace('\n', ' ').replace('\r', ' '), \
                USERNAME, DB_URL, ROLE)
            printf('%s: asm requires sysdba role instead of %s\n', \
            datetime.datetime.fromtimestamp(time.time()), ROLE )
            raise
        if PERROR != errno:
            SLEEPC = 0
            SLEEPER = 1
            PERROR = errno
        INIF.close()
        SLEEPC += 1
        if SLEEPC >= 10:
            if SLEEPER <= 301:
                # don't sleep longer than 5 mins after connect failures
                SLEEPER += 10
            SLEEPC = 0
        printf('%s: (%d.%d)connection error: %s for %s@%s\n', \
            datetime.datetime.fromtimestamp(time.time()), \
            SLEEPC, SLEEPER, ermsg.strip().replace('\n', ' ').replace('\r', ' '), \
            USERNAME, DB_URL)
        time.sleep(SLEEPER)
    except (KeyboardInterrupt, SystemExit):
        OUTF.close()
        raise

OUTF.close()
