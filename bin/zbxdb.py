#!/usr/bin/env python3
"""
 free clonable from https://github.com/ikzelf/zbxdb/
 (@) ronald.rood@gmail.com follow @ik_zelf on twitter
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

VERSION = "2.06"


def setup_logging(
        default_path='etc/logging.json',
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
            try:
                logging.config.dictConfig(config)
            except ValueError as _e:
                print("Error during reading log configuration")
                print(config)
                print("Does the path for filename exist?")
                raise

            return path
    print("Falling back to default logging config")
    logging.basicConfig(level=default_level)

    return False


def set_logfile(_l, _file):
    """change filename of logfile handler
    """

    for _h in _l.root.handlers:
        if isinstance(_h, logging.FileHandler):
            _h.baseFilename = os.path.join(
                os.path.dirname(_h.baseFilename),
                os.path.basename(_file)
            )
            _l.info("Continue logging in %s", _h.baseFilename)
            _h.close()


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
        LOGGER.error("%s TypeError in sql %s from section %s\n",
                     _c['ME'],
                     _c['key'], _c['section']
                     )
        _c['OUTF'].write(_c['hostname'] + " query[" + _c['section']+","+_c['key'] + ",status] " +
                         str(timestamp) + " " + "TypeError" + "\n")
    _c['OUTF'].flush()


class MyConfigParser(configparser.RawConfigParser):  # pylint: disable=too-many-ancestors
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
              'cafile': "",
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


def load_driver(_c):
    """dynamically load the driver"""

    try:
        _db_driver = __import__(_c['db_driver'])
        LOGGER.info(_db_driver)
    except:
        LOGGER.critical("%s supported will be oracle(cx_Oracle), postgres(psycopg2), "
                        "mysql(mysql.connector), mssql(pymssql/_mssql), db2(ibm_db_dbi)\n",
                        _c['ME'])
        LOGGER.critical(
            "%s tested are oracle(cx_Oracle), postgres(psycopg2)\n", _c['ME'])
        LOGGER.critical(
            "Don't forget to install the drivers first ...\n", exc_info=True)
        raise

    LOGGER.info("%s driver %s loaded\n", ME, _c['db_driver'])

    return _db_driver


def load_driver_errors(_c):
    """dynamically load driver errors handler"""
    try:
        driver_errors = importlib.import_module(
            "drivererrors." + _c['db_driver'])
    except:
        LOGGER.critical("Failed to load driver error routines\n")
        LOGGER.critical("Looked in %s\n", sys.path, exc_info=True)
        raise

    LOGGER.info("%s driver drivererrors for %s loaded\n",
                ME, _c['db_driver'])

    return driver_errors


def load_db_connections(_c):
    """ dynamically load db connection tools"""
    try:
        db_connections = importlib.import_module(
            "dbconnections." + _c['db_type'])
    except:
        LOGGER.critical(
            "Failed to load dbconnections routines for %s\n", _c['db_type'])
        LOGGER.critical("Looked in %s\n", sys.path, exc_info=True)
        raise

    LOGGER.info("%s dbconnections for %s loaded\n",
                ME, _c['db_type'])

    return db_connections


def main():  # pylint: disable=too-many-statements,too-many-branches,too-many-locals
    """main routine"""

    if int(platform.python_version().split('.')[0]) < 3:
        LOGGER.fatal("%s needs at least python version 3, currently %s",
                     ME, platform.python_version())
        sys.exit(1)

    start_time = int(time.time())
    _parser = ArgumentParser()
    _parser.add_argument("-c", "--cfile", dest="configfile", default=ME+".cfg",
                         help="Configuration file", metavar="FILE", required=True)
    _parser.add_argument("-v", "--verbosity", action="count", default=0,
                         help="increase output verbosity overriding the default")
    _parser.add_argument("-p", "--parameter", action="store",
                         help="show parameter from configfile")
    _args = _parser.parse_args()

    set_logfile(LOGGER, _args.configfile+".log")

    _config = get_config(_args.configfile, ME)

    if _args.parameter:
        if _args.parameter == 'password':
            print('parameter {}: {}\n'.format(_args.parameter,
                                              decrypted(_config[_args.parameter+'_enc'])))
        else:
            print('parameter {}: {}\n'.format(
                _args.parameter, _config[_args.parameter]))
        sys.exit(0)

    if _args.verbosity:
        newLevel = logging.getLogger().getEffectiveLevel() - (_args.verbosity*10)

        if newLevel < 0:
            newLevel = 0
        LOGGER.warning("Changing loglevel from %d to %d", logging.getLogger().getEffectiveLevel(),
                       newLevel)
        logging.getLogger().setLevel(newLevel)
    LOGGER.debug("log level %d", logging.getLogger().getEffectiveLevel())
    LOGGER.warning("start python-%s %s-%s pid=%s Connecting ...\n",
                   platform.python_version(), ME, VERSION, os.getpid()
                   )

    if _config['password']:
        LOGGER.warning(
            "first encrypted the plaintext password and removed from config\n")
    # we need the password ....
    _config['password'] = decrypted(_config['password_enc'])

# add a few seconds extra to allow the driver timeout handling to do the it's job.
# for example, cx_oracle has a cancel routine that we call after a timeout. If
# there is a network problem, the cancel gets a ORA-12152: TNS:unable to send break message
# setting this defaulttimeout should speed this up
    socket.setdefaulttimeout(_config['sqltimeout']+3)

    LOGGER.warning("%s found db_type=%s, driver %s; checking for driver\n",
                   ME,
                   _config['db_type'], _config['db_driver'])

    if not os.path.exists(
            os.path.join(_config['checks_dir'], _config['db_type'])):
        raise ValueError("db_type "+_config['db_type'] +
                         " does not exist in the "+_config['checks_dir']+" directory")
    db_driver = load_driver(_config)
    driver_errors = load_driver_errors(_config)
    db_connections = load_db_connections(_config)
    LOGGER.info(db_connections)
    LOGGER.info(driver_errors)

    LOGGER.info("hostname in zabbix: %s", _config['hostname'])
    #  hide password, hoping username != password ;-)
    LOGGER.info("connect string    : %s\n",
                db_connections.connect_string(_config).replace(_config['password'],
                                                               '******'))
    LOGGER.info('using sql_timeout : %ds\n', _config['sqltimeout'])
    LOGGER.info("out_file          : %s\n", _config['out_file'])

    if _config['site_checks']:
        LOGGER.info("site_checks       : %s\n", _config['site_checks'])

    if LOG_CONF:
        sys_files = 4
    else:
        sys_files = 3
    check_files = [{'name': __file__, 'lmod': os.path.getmtime(__file__)},
                   {'name': db_connections.__file__,
                    'lmod': os.path.getmtime(db_connections.__file__)},
                   {'name': driver_errors.__file__,
                    'lmod': os.path.getmtime(driver_errors.__file__)},
                   {'name': LOG_CONF,
                    'lmod': os.path.getmtime(LOG_CONF)}
                   ]

    if LOG_CONF:
        check_files.append(
            {'name': LOG_CONF, 'lmod': os.path.getmtime(LOG_CONF)})

    for i in range(sys_files):
        to_outfile(_config,
                   "{}[checks,{},name]".format(ME, i), check_files[i]['name'])
        to_outfile(_config,
                   "{}[checks,{},lmod]".format(ME, i), int(check_files[i]['lmod']))

    conn_counter = 0
    conn_errors = 0
    query_counter = 0
    query_errors = 0

    sleep_c = 0
    sleep_s = 1
    prev_err = 0

    while True:
        try:
            for i in range(sys_files):
                if check_files[i]['lmod'] != os.stat(check_files[i]['name']).st_mtime:
                    LOGGER.warning("%s Changed, from %s to %s restarting ..\n",
                                   check_files[i]['name'],
                                   time.ctime(check_files[i]['lmod']),
                                   time.ctime(os.path.getmtime(check_files[i]['name'])))
                    os.execv(__file__, sys.argv)

            # reset list in case of a just new connection that reloads the config
            check_files = [{'name': __file__, 'lmod': os.path.getmtime(__file__)},
                           {'name': db_connections.__file__,
                            'lmod': os.path.getmtime(db_connections.__file__)},
                           {'name': driver_errors.__file__,
                            'lmod': os.path.getmtime(driver_errors.__file__)}]

            if LOG_CONF:
                check_files.append(
                    {'name': LOG_CONF, 'lmod': os.path.getmtime(LOG_CONF)})

            _config = get_config(_args.configfile, ME)
            _config['password'] = decrypted(_config['password_enc'])

            _start = timer()

            #  hide password, hoping username != password ;-)
            LOGGER.info('connecting to %s\n',
                        db_connections.connect_string(_config).replace(_config['password'],
                                                                       '******'))
            conn_has_cancel = False
            _conn = db_connections.connect(db_driver, _config)

            if "cancel" in dir(_conn):
                conn_has_cancel = True
            LOGGER.info(_conn)
            conn_counter += 1
            to_outfile(_config, ME+"[connect,status]", 0)
            _cursor = _conn.cursor()
            connect_info = db_connections.connection_info(_conn)
            LOGGER.info('connected db_url %s type %s db_role %s version %s\n'
                        '%s user %s %s sid,serial %d,%d instance %s as %s cancel:%s\n',
                        _config['db_url'], connect_info['instance_type'],
                        connect_info['db_role'],
                        connect_info['dbversion'],
                        datetime.datetime.fromtimestamp(time.time()),
                        _config['username'], connect_info['uname'],
                        connect_info['sid'],
                        connect_info['serial'],
                        connect_info['iname'],
                        _config['role'], conn_has_cancel)

            if connect_info['db_role'] in ["PHYSICAL STANDBY", "SLAVE"]:
                checks_file = os.path.join(_config['checks_dir'],
                                           _config['db_type'], "standby" +
                                           "." + connect_info['dbversion'] + ".cfg")
            else:
                checks_file = os.path.join(_config['checks_dir'],
                                           _config['db_type'],
                                           connect_info['db_role'].lower() + "." +
                                           connect_info['dbversion']+".cfg")

            _files = [checks_file]
            check_files.append({'name': checks_file, 'lmod': 0})

            if _config['site_checks']:
                for addition in _config['site_checks'].split(","):
                    addfile = os.path.join(_config['checks_dir'], _config['db_type'],
                                           addition + ".cfg")
                    check_files.append({'name': addfile, 'lmod': 0})
                    _files.extend([addfile])
            LOGGER.info('using checks from %s\n', _files)

            for checks_file in check_files:
                if not os.path.exists(checks_file['name']):
                    raise ValueError(
                        "Configfile " + checks_file['name'] + " does not exist")
            # all checkfiles exist

            sleep_c = 0
            sleep_s = 1
            prev_err = 0
            con_mins = 0
            open_time = int(time.time())

            while True:
                LOGGER.debug("%s while True\n", ME)

                if connect_info['db_role'] != db_connections.current_role(_conn, connect_info):
                    LOGGER.info("db_role changed from %s to %s",
                                connect_info['db_role'],
                                db_connections.current_role(_conn, connect_info))
                    # re connect to get the correct monitoring config again

                    break
                # keep this to compare for when to dump stats
                now_run = int(time.time())
                run_timer = timer()  # keep this to compare for when to dump stats
                # loading checks from the various checkfiles:
                need_to_load = "no"

                # pylint: disable=consider-using-enumerate

                for i in range(len(check_files)):  # at 0 - sys_files is the script itself
                    try:
                        current_lmod = os.path.getmtime(check_files[i]['name'])
                    except OSError as _e:
                        LOGGER.warning("%s: %s\n",
                                       check_files[i]['name'], _e.strerror)
                        # ignore the error, maybe temporary due to an update
                        current_lmod = check_files[i]['lmod']

                    if check_files[i]['lmod'] != current_lmod:
                        if i < sys_files:  # it is the script, a module or LOG_CONF
                                           # that changed
                            LOGGER.warning("%s changed, from %s to %s restarting ...\n",
                                           check_files[i]['name'],
                                           time.ctime(check_files[i]['lmod']),
                                           time.ctime(current_lmod))
                            os.execv(__file__, sys.argv)
                        else:
                            if check_files[i]['lmod'] == 0:
                                LOGGER.info("checks loading %s\n",
                                            check_files[i]['name'])
                                need_to_load = "yes"
                            else:
                                LOGGER.warning("checks changed, reloading %s\n",
                                               check_files[i]['name'])
                                need_to_load = "yes"

                if need_to_load == "yes":
                    to_outfile(_config, ME + "[version]", VERSION)
                    to_outfile(
                        _config, ME + "[config,db_type]", _config['db_type'])
                    to_outfile(
                        _config, ME + "[config,db_driver]", _config['db_driver'])
                    to_outfile(
                        _config, ME + "[config,instance_type]", _config['instance_type'])
                    to_outfile(_config, ME + "[conn,db_role]",
                               connect_info['db_role'])
                    to_outfile(
                        _config, ME + "[conn,instance_type]", connect_info['instance_type'])
                    to_outfile(_config, ME + "[conn,dbversion]",
                               connect_info['dbversion'])
                    to_outfile(
                        _config, ME + "[connect,instance_name]", connect_info['iname'])
                    # sometimes the instance_name query follows within a second
                    # missing event so give it some more time
                    time.sleep(3)
                    objects_list = []
                    sections_list = []
                    file_list = []
                    all_checks = []

                    for i in range(len(check_files)):
                        _e = collections.OrderedDict()
                        _e = {"{#CHECKS_FILE}": i}
                        file_list.append(_e)

                    files_json = '{\"data\":'+json.dumps(file_list)+'}'
                    to_outfile(_config, ME+".files.lld", files_json)

                    for i in range(sys_files, len(check_files)):
                        # #0 is executable that is also checked for updates
                        # #1 db_connections module
                        # #2 driver_errors module
                        # #3 LOG_CONF if it exists ...
                        # so, skip those and pick the real check_files
                        _checks = configparser.RawConfigParser()
                        try:
                            check_file = open(check_files[i]['name'], 'r')
                            to_outfile(_config, "{}[checks,{},name]".format(ME, i),
                                       check_files[i]['name'])
                            to_outfile(_config, "{}[checks,{},lmod]".format(ME, i),
                                       str(int(os.stat(check_files[i]['name']).st_mtime)))
                            try:
                                _checks.read_file(check_file)
                                check_file.close()
                                to_outfile(_config, ME + "[checks," + str(i) +
                                           ",status]", 0)
                            except configparser.Error:
                                to_outfile(_config, ME + "[checks," + str(i) +
                                           ",status]", 13)
                                LOGGER.critical("file %s has parsing errors ->(13)\n",
                                                check_files[i]['name'])
                        except IOError as io_error:
                            to_outfile(
                                _config, ME + "[checks," + str(i) + ",status]", 11)
                            LOGGER.critical("file %s IOError %s %s ->(11)\n",
                                            check_files[i]['name'],
                                            io_error.errno, io_error.strerror)

                        check_files[i]['lmod'] = os.stat(
                            check_files[i]['name']).st_mtime
                        all_checks.append(_checks)

                        for section in sorted(_checks.sections()):
                            sec_mins = int(_checks.get(section, "minutes"))

                            if sec_mins == 0:
                                LOGGER.info(
                                    "%s run at connect only\n", section)
                            else:
                                LOGGER.info("%s run every %d minutes\n",
                                            section, sec_mins)
                            # dump own discovery items of the queries per section
                            _e = collections.OrderedDict()
                            _e = {"{#SECTION}": section}
                            sections_list.append(_e)
                            _x = dict(_checks.items(section))

                            for key, sqls in sorted(_x.items()):
                                if sqls and key != "minutes":
                                    _d = collections.OrderedDict()
                                    _d = {"{#SECTION}": section, "{#KEY}": key}
                                    objects_list.append(_d)
                                    LOGGER.info("%s: %s\n",
                                                key,
                                                sqls[0: 60].
                                                replace('\n', ' ').replace('\r', ' '))
                    # checks are loaded now.
                    sections_json = '{\"data\":'+json.dumps(sections_list)+'}'
                    LOGGER.debug("lld key: %s json: %s\n",
                                 ME+".lld", sections_json)
                    to_outfile(_config, ME+".section.lld", sections_json)
                    rows_json = '{\"data\":'+json.dumps(objects_list)+'}'
                    LOGGER.debug("lld key: %s json: %s\n",
                                 ME+".lld", rows_json)
                    to_outfile(_config, ME + ".query.lld", rows_json)
                    # sqls can contain multiple statements per key. sqlparse to split them
                    # now. Otherwise use a lot of extra cycles when splitting at runtime
                    # all_sql { {section, key}: statements }
                    all_sql = {}

                    for _checks in all_checks:
                        for section in sorted(_checks.sections()):
                            _x = dict(_checks.items(section))

                            for key, sqls in sorted(_x.items()):
                                if sqls and key != "minutes":
                                    all_sql[(section, key)] = []

                                    for statement in sqlparse.split(sqls):
                                        all_sql[(section, key)].append(
                                            statement)

                # checks discovery is also printed
                #
                # assume we are still connected. If not, exception will tell real story
                to_outfile(_config, ME + "[connect,status]", 0)
                to_outfile(_config, ME + "[uptime]",
                           int(time.time() - start_time))
                to_outfile(_config, ME + "[opentime]",
                           int(time.time() - open_time))

                # the connect status is only real if executed a query ....

                for _checks in all_checks:
                    for section in sorted(_checks.sections()):
                        section_timer = timer()  # keep this to compare for when to dump stats
                        sec_mins = int(_checks.get(section, "minutes"))

                        if ((con_mins == 0 and sec_mins == 0) or
                                (sec_mins > 0 and con_mins % sec_mins == 0)):
                            # time to run the checks again from this section
                            _x = dict(_checks.items(section))
                            _cursor = _conn.cursor()

                            for key, sqls in sorted(_x.items()):
                                if sqls and key != "minutes":
                                    LOGGER.debug("%s section: %s key: %s\n",
                                                 ME, section, key)
                                    try:
                                        query_counter += 1

                                        if conn_has_cancel:
                                            # pymysql has no cancel but does have
                                            # timeout in connect
                                            sqltimeout = threading.Timer(
                                                _config['sqltimeout'],
                                                cancel_sql, [_conn, section, key])
                                            sqltimeout.start()
                                        _start = timer()

                                        for statement in all_sql[(section, key)]:

                                            LOGGER.debug("%s section: %s key: %s sql: %s\n",
                                                         ME, section, key, statement)
                                            _cursor.execute(statement)
                                        startf = timer()
                                        # output for the last query must include the
                                        # output for the preparing queries is ignored
                                        #        complete key and value
                                        rows = _cursor.fetchall()

                                        if conn_has_cancel:
                                            sqltimeout.cancel()

                                        if "discover" in section:
                                            objects_list = []

                                            for row in rows:
                                                _d = collections.OrderedDict()

                                                for col in range(len(_cursor.description)):
                                                    _d[_cursor.description[col]
                                                       [0]] = row[col]
                                                objects_list.append(_d)
                                            rows_json = '{\"data\":' + \
                                                json.dumps(objects_list)+'}'
                                            LOGGER.debug("DEBUG lld key: %s json: %s\n", key,
                                                         rows_json)
                                            to_outfile(_config, key, rows_json)
                                            to_outfile(_config, ME +
                                                       "[query," + section + "," +
                                                       key + ",status]", 0)
                                        else:
                                            if rows and len(rows[0]) == 2:
                                                _config['section'] = section
                                                _config['key'] = key

                                                for row in rows:
                                                    to_outfile(
                                                        _config, row[0], row[1])
                                                to_outfile(_config, ME +
                                                           "[query," + section + "," +
                                                           key + ",status]", 0)
                                            elif not rows:
                                                to_outfile(_config, ME + "[query," +
                                                           section + "," +
                                                           key + ",status]", 0)
                                            else:
                                                LOGGER.critical('key=%s.%s ZBXDB-%d: '
                                                                'SQL format error: %s\n',
                                                                section, key, 2,
                                                                "expect key,value pairs")
                                                to_outfile(_config, ME +
                                                           "[query," + section + "," +
                                                           key + ",status]", 2)
                                        _config['section'] = ""
                                        _config['key'] = ""
                                        fetchela = timer() - startf
                                        elapsed_s = timer() - _start
                                        to_outfile(_config, ME + "[query," +
                                                   section + "," +
                                                   key + ",ela]", elapsed_s)
                                        to_outfile(_config, ME + "[query," +
                                                   section + "," +
                                                   key + ",fetch]", fetchela)
                                    # except (db_driver.DatabaseError,
                                        # socket.timeout) as dberr:
                                    except Exception as dberr:
                                        if conn_has_cancel:
                                            sqltimeout.cancel()
                                        ecode, emsg = driver_errors.db_errorcode(
                                            db_driver, dberr)

                                        elapsed_s = timer() - _start
                                        query_errors += 1
                                        to_outfile(_config, ME + "[query," +
                                                   section + "," +
                                                   key + ",status]", ecode)
                                        to_outfile(_config, ME + "[query," +
                                                   section + "," +
                                                   key + ",ela]", elapsed_s)
                                        LOGGER.info('key=%s.%s ZBXDB-%s: '
                                                    'Db execution error: %s\n',
                                                    section, key, ecode, emsg.strip())

                                        if driver_errors.db_error_needs_new_session(db_driver,
                                                                                    ecode):
                                            raise

                                        LOGGER.debug("%s commit\n", ME)
                                        _conn.commit()

                                        LOGGER.debug("%s committed\n", ME)
                            # end of a section ## time to run the checks again from this section
                            to_outfile(_config, ME + "[query," + section + ",,ela]",
                                       timer() - section_timer)
                # release locks that might have been taken

                LOGGER.debug("%s commit 2\n", ME)

                _conn.commit()

                LOGGER.debug("%s committed.\n", ME)
                # dump metric for summed elapsed time of this run
                to_outfile(_config, ME + "[query,,,ela]",
                           timer() - run_timer)
                to_outfile(_config, ME + "[cpu,user]",
                           resource.getrusage(resource.RUSAGE_SELF).ru_utime)
                to_outfile(_config, ME + "[cpu,sys]",
                           resource.getrusage(resource.RUSAGE_SELF).ru_stime)
                to_outfile(_config, ME + "[mem,maxrss]",
                           resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
                # passed all sections

                if ((now_run - start_time) % 3600) == 0:
                    gc.collect()
                    # dump stats
                    LOGGER.info("connect %d times, %d fail; started %d queries, "
                                "%d fail memrss:%d user:%f sys:%f\n",
                                conn_counter, conn_errors, query_counter,
                                query_errors,
                                resource.getrusage(
                                    resource.RUSAGE_SELF).ru_maxrss,
                                resource.getrusage(
                                    resource.RUSAGE_SELF).ru_utime,
                                resource.getrusage(resource.RUSAGE_SELF).ru_stime)
                # try to keep activities on the same starting second:
                sleep_time = 60 - ((int(time.time()) - start_time) % 60)

                LOGGER.debug("Sleeping for %d seconds\n", sleep_time)
                time.sleep(sleep_time)
                con_mins = con_mins + 1  # not really mins since the checks could
                #                       have taken longer than 1 minute to complete
            # end while True
        # except (db_driver.DatabaseError, socket.timeout, ConnectionResetError) as dberr:
        except Exception as dberr:
            err_code, err_msg = driver_errors.db_errorcode(db_driver, dberr)
            elapsed_s = timer() - _start
            to_outfile(_config, ME + "[connect,status]", err_code)

            if not driver_errors.db_error_needs_new_session(db_driver, err_code):
                # from a killed session, crashed instance or similar
                conn_errors += 1

            if prev_err != err_code:
                sleep_c = 0
                sleep_s = 1
                prev_err = err_code
            sleep_c += 1

            if sleep_c >= 10:
                if sleep_s <= 301:
                    # don't sleep longer than 5 mins after connect failures
                    sleep_s += 10
                sleep_c = 0
            LOGGER.warning('(%d.%d)connection error: [%s] %s for %s@%s\n',
                           sleep_c, sleep_s, err_code,
                           err_msg.strip().replace('\n', ' ').replace('\r', ' '),
                           _config['username'], _config['db_url'])
            # set_trace()
            time.sleep(sleep_s)
        except (KeyboardInterrupt, SystemExit):
            exit(0)


ME = os.path.splitext(os.path.basename(__file__))[0]
LOG_CONF = setup_logging()
LOGGER = logging.getLogger(__name__)

if __name__ == '__main__':
    try:
        main()
    except Exception:  # pylint: disable=broad-except
        LOGGER.fatal("problem", exc_info=True)
