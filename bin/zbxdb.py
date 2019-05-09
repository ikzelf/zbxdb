#!/usr/bin/env python3
"""
 free clonable from https://github.com/ikzelf/zbxdb/
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
import base64
import collections
import configparser
import datetime
import gc
import importlib
import json
import logging.config
import os
import platform
import resource
import socket
import sys
import threading
import time
from argparse import ArgumentParser
# from pdb import set_trace
from timeit import default_timer as timer

import sqlparse

VERSION = "1.20"


def setup_logging(
        default_path='logging.json',
        default_level=logging.INFO,
        env_key='LOG_CFG'
):
    """Setup logging configuration

    """
    path = default_path
    value = os.getenv(env_key, None)

    if value:
        path = value

    if os.path.exists(path):
        with open(path, 'rt') as _f:
            config = json.load(_f)
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=default_level)


def to_outfile(_c, ikey, values):
    """uniform way to generate the output for items"""
    timestamp = int(time.time())

    if os.path.exists(_c['out_file']):
        if not _c['OUTF']:
            _c['OUTF'] = open(_c['out_file'], "a")
    else:
        _c['OUTF'] = open(_c['out_file'], "w")
    try:
        _c['OUTF'].write(_c['hostname'] + ' "' + ikey + '" ' +
                         str(timestamp) + ' ' + str(values) + '\n')
    except TypeError:
        LOGGER.info("%s TypeError in sql %s from section %s\n",
                    _c['ME'],
                    _c['key'], _c['section']
                    )
        _c['OUTF'].write(_c['hostname'] + " query[" + _c['section']+","+_c['key'] + ",status] " +
                         str(timestamp) + " " + "TypeError" + "\n")
    _c['OUTF'].flush()


class MyConfigParser(configparser.RawConfigParser):
    """strip comments"""

    def __init__(self):
        configparser.RawConfigParser.__init__(
            self, inline_comment_prefixes=('#', ';'))


def encrypted(plain):
    """encrypt plaintext password"""

    return base64.b64encode(bytes(plain, 'utf-8'))


def decrypted(pw_enc):
    """return decrypted password"""

    return base64.b64decode(pw_enc).decode("utf-8", "ignore")


def get_config_par(_c, _parameter, _me):
    """get a parameter value
    """
    try:
        _v = os.path.expandvars(_c.get(_me, _parameter))
    except configparser.NoOptionError:
        _v = ""

    return _v


def get_config(filename, _me):
    """read the specified configuration file"""
    config = {'db_url': "", 'db_type': "", 'db_driver': "", 'instance_type': "rdbms",
              'server': "", 'db_name': "", 'instance_name': "", 'server_port': "",
              'username': "scott", 'password': "", 'role': "normal", 'omode': 0,
              'out_dir': "", 'out_file': "", 'hostname': "", 'checks_dir': "",
              'site_checks': "", 'password_enc': "", 'OUTF': 0, 'ME': _me,
              'section': "", 'key': "",
              'sqltimeout': 60.0}
    _config = MyConfigParser()

    if not os.path.exists(filename):
        raise ValueError("Configfile " + filename + " does not exist")

    _inif = open(filename, 'r')
    _config.read_file(_inif)

    for _i in config:
        _v = get_config_par(_config, _i, _me)

        if _v:
            config[_i] = _v

    enc = config['password_enc']
    config['password_enc'] = bytearray(enc, 'utf-8')

    config['out_file'] = os.path.join(config['out_dir'],
                                      str(os.path.splitext(os.path.basename(filename))[0]) +
                                      ".zbx")

    if config['site_checks'] == "NONE":
        config['site_checks'] = ""
    _f = config['sqltimeout']
    config['sqltimeout'] = float(_f)

    _inif.close()

    if config['password'] != "":
        enc = encrypted(config['password'])
        _inif = open(filename, 'w')
        _config.set(_me, 'password', '')
        _config.set(_me, 'password_enc', enc.decode())
        _config.write(_inif)
        _inif.close()

    return config


def cancel_sql(_c, _s, _k):
    '''Cancel long running SQL
    '''
    LOGGER.warning("%s cancel_sql %s %s\n", ME, _s, _k)
    _c.cancel()
    LOGGER.warning("%s canceled   %s %s\n", ME, _s, _k)
    # raise zbx_exception("sql_timeout")


ME = os.path.splitext(os.path.basename(__file__))[0]
setup_logging()
LOGGER = logging.getLogger(__name__)

if int(platform.python_version().split('.')[0]) < 3:
    LOGGER.critical("%s needs at least python version 3, currently %s",
                    ME, platform.python_version())
    sys.exit(1)

STARTTIME = int(time.time())
PARSER = ArgumentParser()
PARSER.add_argument("-c", "--cfile", dest="configfile", default=ME+".cfg",
                    help="Configuration file", metavar="FILE", required=True)
PARSER.add_argument("-v", "--verbosity", action="count",
                    help="increase output verbosity")
PARSER.add_argument("-p", "--parameter", action="store",
                    help="show parameter from configfile")
ARGS = PARSER.parse_args()

CONFIG = get_config(ARGS.configfile, ME)

if ARGS.parameter:
    if ARGS.parameter == 'password':
        print('parameter {}: {}\n'.format(ARGS.parameter,
                                          decrypted(CONFIG[ARGS.parameter+'_enc'])))
    else:
        print('parameter {}: {}\n'.format(
            ARGS.parameter, CONFIG[ARGS.parameter]))
    sys.exit(0)


LOGGER.warning("start python-%s %s-%s pid=%s Connecting ...\n",
               platform.python_version(), ME, VERSION, os.getpid()
               )

if CONFIG['password']:
    LOGGER.warning(
        "first encrypted the plaintext password and removed from config\n")

# add a few seconds extra to allow the driver timeout handling to do the it's job.
# for example, cx_oracle has a cancel routine that we call after a timeout. If
# there is a network problem, the cancel gets a ORA-12152: TNS:unable to send break message
# setting this defaulttimeout should speed this up
socket.setdefaulttimeout(CONFIG['sqltimeout']+3)

LOGGER.warning("%s found db_type=%s, driver %s; checking for driver\n",
               ME,
               CONFIG['db_type'], CONFIG['db_driver'])
try:
    DBDR = __import__(CONFIG['db_driver'])
    LOGGER.info(DBDR)
except:
    LOGGER.critical("%s supported will be oracle(cx_Oracle), postgres(psycopg2), \
           mysql(mysql.connector), mssql(pymssql/_mssql), db2(ibm_db_dbi)\n", ME)
    LOGGER.critical(
        "%s tested are oracle(cx_Oracle), postgres(psycopg2)\n", ME)
    LOGGER.critical(
        "Don't forget to install the drivers first ...\n", exc_info=True)
    raise

LOGGER.info("%s driver %s loaded\n",
            ME, CONFIG['db_driver'])
try:
    DBE = importlib.import_module("drivererrors." + CONFIG['db_driver'])
except:
    LOGGER.critical("Failed to load driver error routines\n")
    LOGGER.critical("Looked in %s\n", sys.path, exc_info=True)
    raise

LOGGER.info("%s driver drivererrors for %s loaded\n",
            ME, CONFIG['db_driver'])
try:
    DBC = importlib.import_module("dbconnections." + CONFIG['db_type'])
except:
    LOGGER.critical(
        "Failed to load dbconnections routines for %s\n", CONFIG['db_type'])
    LOGGER.critical("Looked in %s\n", sys.path, exc_info=True)
    raise

LOGGER.info("%s dbconnections for %s loaded\n",
            ME, CONFIG['db_type'])
LOGGER.info(DBC)
LOGGER.info(DBE)

LOGGER.info("hostname in zabbix: %s", CONFIG['hostname'])
LOGGER.info("connect string    : %s\n", DBC.connect_string(CONFIG))
LOGGER.info('using sql_timeout : %ds\n', CONFIG['sqltimeout'])
LOGGER.info("out_file          : %s\n", CONFIG['out_file'])

if CONFIG['site_checks']:
    LOGGER.info("site_checks       : %s\n", CONFIG['site_checks'])

CHECKFILES = [{'name': __file__, 'lmod': os.path.getmtime(__file__)},
              {'name': DBC.__file__, 'lmod': os.path.getmtime(DBC.__file__)},
              {'name': DBE.__file__, 'lmod': os.path.getmtime(DBE.__file__)}
              ]
to_outfile(CONFIG, ME + "[checks,0,lmod]", int(CHECKFILES[0]['lmod']))
to_outfile(CONFIG, ME + "[checks,1,lmod]", int(CHECKFILES[1]['lmod']))
to_outfile(CONFIG, ME + "[checks,2,lmod]", int(CHECKFILES[2]['lmod']))
CHECKSCHANGED = [0]

CONNECTCOUNTER = 0
CONNECTERROR = 0
QUERYCOUNTER = 0
QUERYERROR = 0

SLEEPC = 0
SLEEPER = 1
PERROR = 0

while True:
    try:
        for i in range(0, 2):
            if CHECKFILES[i]['lmod'] != os.stat(CHECKFILES[i]['name']).st_mtime:
                LOGGER.warning("%s Changed, from %s to %s restarting ..\n",
                               CHECKFILES[i]['name'],
                               time.ctime(CHECKFILES[i]['lmod']),
                               time.ctime(os.path.getmtime(CHECKFILES[i]['name'])))
                os.execv(__file__, sys.argv)

        # reset list in case of a just new connection that reloads the config
        CHECKFILES = [{'name': __file__, 'lmod': os.path.getmtime(__file__)},
                      {'name': DBC.__file__,
                       'lmod': os.path.getmtime(DBC.__file__)},
                      {'name': DBE.__file__,
                       'lmod': os.path.getmtime(DBE.__file__)}
                      ]
        CONFIG = get_config(ARGS.configfile, ME)
        CONFIG['password'] = decrypted(CONFIG['password_enc'])

        START = timer()

        if ARGS.verbosity:
            LOGGER.info('connecting to %s\n',
                        DBC.connect_string(CONFIG))
        # with dbc.connect(dbdr, config) as conn:
        # pymysql returns a cursor from __enter__() :-(
        CONN_HAS_CANCEL = False
        CONN = DBC.connect(DBDR, CONFIG)

        if "cancel" in dir(CONN):
            CONN_HAS_CANCEL = True
        LOGGER.info(CONN)
        CONNECTCOUNTER += 1
        to_outfile(CONFIG, ME+"[connect,status]", 0)
        CURS = CONN.cursor()
        CONNECT_INFO = DBC.connection_info(CONN)
        LOGGER.warning('connected db_url %s type %s db_role %s version %s\n'
                       '%s user %s %s sid,serial %d,%d instance %s as %s cancel:%s\n',
                       CONFIG['db_url'], CONNECT_INFO['instance_type'], CONNECT_INFO['db_role'],
                       CONNECT_INFO['dbversion'],
                       datetime.datetime.fromtimestamp(time.time()),
                       CONFIG['username'], CONNECT_INFO['uname'], CONNECT_INFO['sid'],
                       CONNECT_INFO['serial'],
                       CONNECT_INFO['iname'],
                       CONFIG['role'], CONN_HAS_CANCEL)

        if CONNECT_INFO['db_role'] in ["PHYSICAL STANDBY", "SLAVE"]:
            CHECKSFILE = os.path.join(CONFIG['checks_dir'],
                                      CONFIG['db_type'], "standby" +
                                      "." + CONNECT_INFO['dbversion'] + ".cfg")
        else:
            CHECKSFILE = os.path.join(CONFIG['checks_dir'],
                                      CONFIG['db_type'],
                                      CONNECT_INFO['db_role'].lower() + "." +
                                      CONNECT_INFO['dbversion']+".cfg")

        FILES = [CHECKSFILE]
        CHECKFILES.append({'name': CHECKSFILE, 'lmod': 0})

        if CONFIG['site_checks']:
            for addition in CONFIG['site_checks'].split(","):
                addfile = os.path.join(CONFIG['checks_dir'], CONFIG['db_type'],
                                       addition + ".cfg")
                CHECKFILES.append({'name': addfile, 'lmod': 0})
                FILES.extend([addfile])
        LOGGER.info('using checks from %s\n', FILES)

        for CHECKSFILE in CHECKFILES:
            if not os.path.exists(CHECKSFILE['name']):
                raise ValueError(
                    "Configfile " + CHECKSFILE['name'] + " does not exist")
        # all checkfiles exist

        SLEEPC = 0
        SLEEPER = 1
        PERROR = 0
        CONMINS = 0
        OPENTIME = int(time.time())

        while True:
            LOGGER.debug("%s while True\n", ME)
            # keep this to compare for when to dump stats
            NOWRUN = int(time.time())
            RUNTIMER = timer()  # keep this to compare for when to dump stats
            # loading checks from the various checkfiles:
            NEEDTOLOAD = "no"

            for i in range(len(CHECKFILES)):  # at index 0 is the script itself
                try:
                    current_lmod = os.path.getmtime(CHECKFILES[i]['name'])
                except OSError as _e:
                    LOGGER.warning("%s: %s\n",
                                   CHECKFILES[i]['name'], _e.strerror)
                    # ignore the error, maybe temporary due to an update
                    current_lmod = CHECKFILES[i]['lmod']

                if CHECKFILES[i]['lmod'] != current_lmod:
                    if i < 3:  # this is the script or module itself that changed
                        LOGGER.warning("%s changed, from %s to %s restarting ...\n",
                                       CHECKFILES[i]['name'],
                                       time.ctime(CHECKFILES[i]['lmod']),
                                       time.ctime(current_lmod))
                        os.execv(__file__, sys.argv)
                    else:
                        if CHECKFILES[i]['lmod'] == 0:
                            LOGGER.warning("checks loading %s\n",
                                           CHECKFILES[i]['name'])
                            NEEDTOLOAD = "yes"
                        else:
                            LOGGER.warning("checks changed, reloading %s\n",
                                           CHECKFILES[i]['name'])
                            NEEDTOLOAD = "yes"

            if NEEDTOLOAD == "yes":
                to_outfile(CONFIG, ME + "[version]", VERSION)
                to_outfile(CONFIG, ME + "[config,db_type]", CONFIG['db_type'])
                to_outfile(
                    CONFIG, ME + "[config,db_driver]", CONFIG['db_driver'])
                to_outfile(
                    CONFIG, ME + "[config,instance_type]", CONFIG['instance_type'])
                to_outfile(CONFIG, ME + "[conn,db_role]",
                           CONNECT_INFO['db_role'])
                to_outfile(
                    CONFIG, ME + "[conn,instance_type]", CONNECT_INFO['instance_type'])
                to_outfile(CONFIG, ME + "[conn,dbversion]",
                           CONNECT_INFO['dbversion'])
                to_outfile(
                    CONFIG, ME + "[connect,instance_name]", CONNECT_INFO['iname'])
                # sometimes the instance_name query follows within a second
                # missing event so give it some more time
                time.sleep(3)
                OBJECTS_LIST = []
                SECTIONS_LIST = []
                FILES_LIST = []
                ALL_CHECKS = []

                for i in range(len(CHECKFILES)):
                    E = collections.OrderedDict()
                    E = {"{#CHECKS_FILE}": i}
                    FILES_LIST.append(E)

                FILES_JSON = '{\"data\":'+json.dumps(FILES_LIST)+'}'
                to_outfile(CONFIG, ME+".files.lld", FILES_JSON)

                for i in range(3, len(CHECKFILES)):
                    # #0 is executable that is also checked for updates
                    # #1 DBC module
                    # #2 DBE module
                    CHECKS = configparser.RawConfigParser()
                    try:
                        CHECKSF = open(CHECKFILES[i]['name'], 'r')
                        to_outfile(CONFIG, ME + "[checks," + str(i) +
                                   ",name]", CHECKFILES[i]['name'])
                        to_outfile(CONFIG, ME + "[checks," + str(i) +
                                   ",lmod]",
                                   str(int(os.stat(CHECKFILES[i]['name']).st_mtime)))
                        try:
                            CHECKS.read_file(CHECKSF)
                            CHECKSF.close()
                            to_outfile(CONFIG, ME + "[checks," + str(i) +
                                       ",status]", 0)
                        except configparser.Error:
                            to_outfile(CONFIG, ME + "[checks," + str(i) +
                                       ",status]", 13)
                            LOGGER.critical("file %s has parsing errors ->(13)\n",
                                            CHECKFILES[i]['name'])
                    except IOError as io_error:
                        to_outfile(
                            CONFIG, ME + "[checks," + str(i) + ",status]", 11)
                        LOGGER.critical("file %s IOError %s %s ->(11)\n",
                                        CHECKFILES[i]['name'],
                                        io_error.errno, io_error.strerror)

                    CHECKFILES[i]['lmod'] = os.stat(
                        CHECKFILES[i]['name']).st_mtime
                    ALL_CHECKS.append(CHECKS)

                    for section in sorted(CHECKS.sections()):
                        secMins = int(CHECKS.get(section, "minutes"))

                        if secMins == 0:
                            LOGGER.info("%s run at connect only\n", section)
                        else:
                            LOGGER.info("%s run every %d minutes\n",
                                        section, secMins)
                        # dump own discovery items of the queries per section
                        E = collections.OrderedDict()
                        E = {"{#SECTION}": section}
                        SECTIONS_LIST.append(E)
                        x = dict(CHECKS.items(section))

                        for key, sqls in sorted(x.items()):
                            if sqls and key != "minutes":
                                d = collections.OrderedDict()
                                d = {"{#SECTION}": section, "{#KEY}": key}
                                OBJECTS_LIST.append(d)
                                LOGGER.warning("%s: %s\n",
                                               key,
                                               sqls[0: 60].replace('\n', ' ').replace('\r', ' '))
                # checks are loaded now.
                SECTIONS_JSON = '{\"data\":'+json.dumps(SECTIONS_LIST)+'}'
                LOGGER.debug("lld key: %s json: %s\n", ME+".lld", ROWS_JSON)
                to_outfile(CONFIG, ME+".section.lld", SECTIONS_JSON)
                ROWS_JSON = '{\"data\":'+json.dumps(OBJECTS_LIST)+'}'
                LOGGER.debug("lld key: %s json: %s\n", ME+".lld", ROWS_JSON)
                to_outfile(CONFIG, ME + ".query.lld", ROWS_JSON)
                # sqls can contain multiple statements per key. sqlparse to split them
                # now. Otherwise use a lot of extra cycles when splitting at runtime
                # all_sql { {section, key}: statements }
                ALL_SQL = {}

                for CHECKS in ALL_CHECKS:
                    for section in sorted(CHECKS.sections()):
                        x = dict(CHECKS.items(section))

                        for key, sqls in sorted(x.items()):
                            if sqls and key != "minutes":
                                ALL_SQL[(section, key)] = []

                                for statement in sqlparse.split(sqls):
                                    ALL_SQL[(section, key)].append(statement)

            # checks discovery is also printed
            #
            # assume we are still connected. If not, exception will tell real story
            to_outfile(CONFIG, ME + "[connect,status]", 0)
            to_outfile(CONFIG, ME + "[uptime]", int(time.time() - STARTTIME))
            to_outfile(CONFIG, ME + "[opentime]", int(time.time() - OPENTIME))

            # the connect status is only real if executed a query ....

            for CHECKS in ALL_CHECKS:
                for section in sorted(CHECKS.sections()):
                    SectionTimer = timer()  # keep this to compare for when to dump stats
                    secMins = int(CHECKS.get(section, "minutes"))

                    if ((CONMINS == 0 and secMins == 0) or
                            (secMins > 0 and CONMINS % secMins == 0)):
                        # time to run the checks again from this section
                        x = dict(CHECKS.items(section))
                        CURS = CONN.cursor()

                        for key, sqls in sorted(x.items()):
                            if sqls and key != "minutes":
                                LOGGER.debug("%s section: %s key: %s\n",
                                             ME, section, key)
                                try:
                                    QUERYCOUNTER += 1

                                    if CONN_HAS_CANCEL:
                                        # pymysql has no cancel but does have timeout in connect
                                        sqltimeout = threading.Timer(
                                            CONFIG['sqltimeout'],
                                            cancel_sql, [CONN, section, key])
                                        sqltimeout.start()
                                    START = timer()

                                    for statement in ALL_SQL[(section, key)]:
                                        lstatement = statement

                                        LOGGER.debug("%s section: %s key: %s sql: %s\n",
                                                     ME, section, key, statement)
                                        CURS.execute(statement)
                                    startf = timer()
                                    # output for the last query must include the
                                    # output for the preparing queries is ignored
                                    #        complete key and value
                                    rows = CURS.fetchall()

                                    if CONN_HAS_CANCEL:
                                        sqltimeout.cancel()

                                    if "discover" in section:
                                        OBJECTS_LIST = []

                                        for row in rows:
                                            d = collections.OrderedDict()

                                            for col in range(0, len(CURS.description)):
                                                d[CURS.description[col]
                                                  [0]] = row[col]
                                            OBJECTS_LIST.append(d)
                                        ROWS_JSON = '{\"data\":' + \
                                            json.dumps(OBJECTS_LIST)+'}'
                                        LOGGER.debug("DEBUG lld key: %s json: %s\n", key,
                                                     ROWS_JSON)
                                        to_outfile(CONFIG, key, ROWS_JSON)
                                        to_outfile(CONFIG, ME +
                                                   "[query," + section + "," +
                                                   key + ",status]", 0)
                                    else:
                                        if rows and len(rows[0]) == 2:
                                            CONFIG['section'] = section
                                            CONFIG['key'] = key

                                            for row in rows:
                                                to_outfile(
                                                    CONFIG, row[0], row[1])
                                            to_outfile(CONFIG, ME +
                                                       "[query," + section + "," +
                                                       key + ",status]", 0)
                                        elif not rows:
                                            to_outfile(CONFIG, ME + "[query," +
                                                       section + "," +
                                                       key + ",status]", 0)
                                        else:
                                            LOGGER.critical('key=%s.%s ZBXDB-%d: ' +
                                                            'SQL format error: %s\n',
                                                            section, key, 2, "expect key,value pairs")
                                            to_outfile(CONFIG, ME +
                                                       "[query," + section + "," +
                                                       key + ",status]", 2)
                                    CONFIG['section'] = ""
                                    CONFIG['key'] = ""
                                    fetchela = timer() - startf
                                    ELAPSED = timer() - START
                                    to_outfile(CONFIG, ME + "[query," +
                                               section + "," +
                                               key + ",ela]", ELAPSED)
                                    to_outfile(CONFIG, ME + "[query," +
                                               section + "," +
                                               key + ",fetch]", fetchela)
                                # , zbx_exception) as dberr:
                                except (DBDR.DatabaseError) as dberr:
                                    if CONN_HAS_CANCEL:
                                        sqltimeout.cancel()
                                    ecode, emsg = DBE.db_errorcode(DBDR, dberr)

                                    ELAPSED = timer() - START
                                    QUERYERROR += 1
                                    to_outfile(CONFIG, ME + "[query," +
                                               section + "," +
                                               key + ",status]", ecode)
                                    to_outfile(CONFIG, ME + "[query," +
                                               section + "," +
                                               key + ",ela]", ELAPSED)
                                    LOGGER.warning('key=%s.%s ZBXDB-%s: Db execution error: %s\n',
                                                   section, key, ecode, emsg.strip())

                                    if DBE.db_error_needs_new_session(DBDR,
                                                                      ecode):
                                        raise

                                    LOGGER.debug("%s commit\n", ME)
                                    CONN.commit()

                                    LOGGER.debug("%s committed\n", ME)
                        # end of a section ## time to run the checks again from this section
                        to_outfile(CONFIG, ME + "[query," + section + ",,ela]",
                                   timer() - SectionTimer)
            # release locks that might have been taken

            LOGGER.debug("%s %s commit 2\n", ME)

            CONN.commit()

            LOGGER.debug("%s rolledback\n", ME)
            # dump metric for summed elapsed time of this run
            to_outfile(CONFIG, ME + "[query,,,ela]",
                       timer() - RUNTIMER)
            to_outfile(CONFIG, ME + "[cpu,user]",
                       resource.getrusage(resource.RUSAGE_SELF).ru_utime)
            to_outfile(CONFIG, ME + "[cpu,sys]",
                       resource.getrusage(resource.RUSAGE_SELF).ru_stime)
            to_outfile(CONFIG, ME + "[mem,maxrss]",
                       resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
            # passed all sections

            if ((NOWRUN - STARTTIME) % 3600) == 0:
                gc.collect()
                # dump stats
                LOGGER.warning("connect %d times, %d fail; started %d queries, \
                               %d fail memrss:%d user:%f sys:%f\n",
                               CONNECTCOUNTER, CONNECTERROR, QUERYCOUNTER, QUERYERROR,
                               resource.getrusage(
                                   resource.RUSAGE_SELF).ru_maxrss,
                               resource.getrusage(
                                   resource.RUSAGE_SELF).ru_utime,
                               resource.getrusage(resource.RUSAGE_SELF).ru_stime)
            # try to keep activities on the same starting second:
            SLEEPTIME = 60 - ((int(time.time()) - STARTTIME) % 60)

            LOGGER.debug("Sleeping for %d seconds\n", SLEEPTIME)
            time.sleep(SLEEPTIME)
            CONMINS = CONMINS + 1  # not really mins since the checks could
            #                       have taken longer than 1 minute to complete
    except (DBDR.DatabaseError, socket.timeout, ConnectionResetError) as dberr:
        ECODE, EMSG = DBE.db_errorcode(DBDR, dberr)
        ELAPSED = timer() - START
        to_outfile(CONFIG, ME + "[connect,status]", ECODE)

        if not DBE.db_error_needs_new_session(DBDR, ECODE):
            # from a killed session, crashed instance or similar
            CONNECTERROR += 1

        if PERROR != ECODE:
            SLEEPC = 0
            SLEEPER = 1
            PERROR = ECODE
        SLEEPC += 1

        if SLEEPC >= 10:
            if SLEEPER <= 301:
                # don't sleep longer than 5 mins after connect failures
                SLEEPER += 10
            SLEEPC = 0
        LOGGER.warning('(%d.%d)connection error: [%s] %s for %s@%s\n',
                       SLEEPC, SLEEPER, ECODE, EMSG.strip().replace('\n', ' ').replace('\r', ' '),
                       CONFIG['username'], CONFIG['db_url'])
        # set_trace()
        time.sleep(SLEEPER)
    except (KeyboardInterrupt, SystemExit):
        exit(0)
