#!/usr/bin/env python3
"""
collect output files of the various zbxdb.py processes,
send them to zabbix and archive a few days worth of them in compressed
zipfiles per run
if defined uses ZBXDB_OUT environment variable to access the zbxdb.py output
file, else try's the first argument as ZBXDB_OUT
Should work on *ux as wel as *dows (not tested on *dows)
Since db monitoring should be done from a zabbix proxy or server, the server is
hard defaulted as 127.0.0.1 10051 but can be overridden in the environment
To enable sending to multiple servers added the plural form of ZABBIX_SERVER
and ZABBIX_SERVER_PORT as comma separated lists
"""
import json
import logging.config
import os
import shutil
import subprocess
import sys
import time
import zipfile

def setup_logging(
        default_path='etc/logging_sender.json',
        default_level=logging.INFO,
        env_key='LOG_CFG_SENDER'
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

LOG_CONF = setup_logging()
LOGGER = logging.getLogger(__name__)
ZABBIX_SERVER = os.environ.get("ZABBIX_SERVER", "127.0.0.1")
ZABBIX_SERVERS = os.environ.get("ZABBIX_SERVERS", ZABBIX_SERVER)
ZABBIX_SERVER_PORT = os.environ.get("ZABBIX_SERVER_PORT", "10051")
ZABBIX_SERVER_PORTS = os.environ.get("ZABBIX_SERVER_PORTS", ZABBIX_SERVER_PORT)

s = ZABBIX_SERVERS.split(",")
p = ZABBIX_SERVER_PORTS.split(",")

LOGGER.warning("ZABBIX_SERVERS {} ZABBIX_SERVER_PORTS {}".format(ZABBIX_SERVERS,
                                                        ZABBIX_SERVER_PORTS))

if len(s) > len(p):
    for i in range(len(p), len(s)):
        p.append(p[0])

if len(p) > len(s):
    for i in range(len(s), len(p)):
        s.append(s[0])

ME = os.path.splitext(os.path.basename(__file__))[0]
HOME = os.path.expanduser("~")
NOW = time.strftime("%Y-%m-%d-%H%M")  # used for zipfile name
# used for logfile name leading to max 7 files
NOWD = time.strftime("%a")
# used to check for 1st run of the day (truncate)
NOWM = time.strftime("%H%M")
NOWDLOG = os.path.join(HOME, "log", ME+"."+NOWD+".log")
LOGGER.warning("Logging in %s", LOGGER.root.handlers[1].baseFilename)
# asuming only 1 handler .... could be cleaner, I know.

ZBXDB_OUT = None

if len(sys.argv) > 1:
    ZBXDB_OUT = sys.argv[1]

if ZBXDB_OUT is None:
    if "ZBXDB_OUT" in os.environ:
        ZBXDB_OUT = os.environ["ZBXDB_OUT"]

if ZBXDB_OUT is None:
    LOGGER.fatal("""{} specify ZBXDB_OUT in the environment or as first argument of {}
Usage {} [ZBXDB_OUT]
   to collect zbxdb.py outputs from that directory to send to zabbix
   ZBXDB_OUT should point to the out_dir directory in the zbxdb.py config[s]
   using {} directory in {} for work space
   sending to ZABBIX_SERVER {} on ZABBIX_SERVER_PORT {}
   """.format(ME, ME, ME, ME, HOME, HOME, ZABBIX_SERVERS, ZABBIX_SERVER_PORTS))
    sys.exit(1)

if os.geteuid() == 0:
    LOGGER.fatal("Running as root, don't run zbxdb* scripts as root, for your own sake")
    sys.exit(13)

if not os.path.isdir(ZBXDB_OUT):
    LOGGER.fatal("{} ZBXDB_OUT directory {} does not exist".format(
        ME, ZBXDB_OUT))
    sys.exit(1)

if not os.access(ZBXDB_OUT, os.W_OK):
    LOGGER.fatal("{} ZBXDB_OUT directory {} not writeable".format(ME, ZBXDB_OUT))
    sys.exit(1)

if not shutil.which('zabbix_sender'):
    LOGGER.fatal("{} needs zabbix_sender in PATH".format(ME))
    sys.exit(1)

BASE = os.path.join(HOME, ME)
TMPIN = os.path.join(BASE, "in")
ARCHIVE = os.path.join(BASE, "archive")

for d in [BASE, TMPIN, ARCHIVE]:
    if not os.path.isdir(d):
        os.mkdir(d)

LOCK = os.path.join(BASE, ME+".lock")
if os.path.exists(LOCK):
    LOGGER.warning("{} previous run still running(or crashed(lock file: {}))"
          .format(NOW, LOCK))
    sys.exit(2)

open(LOCK, 'a').close()
l = [f for f in os.listdir(ZBXDB_OUT) if os.path.isfile(os.path.join(ZBXDB_OUT,f))]
for f in l:
    # existing files are overwritten
    LOGGER.debug("Move '{}' to {}".format(os.path.join(ZBXDB_OUT, f), os.path.join(TMPIN, f)))
    shutil.move(os.path.join(ZBXDB_OUT, f), os.path.join(TMPIN, f))

for f in sorted(os.listdir(TMPIN)):
    LOGGER.warning("{} processing {}".format(NOW, f))
    # 1 file at a time. Since zabbix v4 the limit of what can be sent in one
    # run is reduced a lot. Concatenation will give problems.
    for server, port in zip(s, p):
        process = subprocess.Popen(["zabbix_sender -z {} -p {} -T -i {} -vv"
                                    .format(
                                        server,
                                        port,
                                        os.path.join(TMPIN, f))],
                                   shell=True,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   close_fds=True)
        output = process.stdout.read().decode()
        err = process.stderr.read().decode()
        exit_code = process.wait()
        LOGGER.debug("{} {} zabbix_sender {}:{} rc: {}".format(
            NOW, f, server, port, exit_code))
        LOGGER.debug("{} output {}: {}".format(NOW, f, output))
        LOGGER.debug("{} stderr {}: {}".format(NOW, f, err))

    ziparch = os.path.join(ARCHIVE, "zbx_{}.zip".format(NOW))
    LOGGER.info("Archiving to {}".format(ziparch))
    with zipfile.ZipFile(ziparch,
                         "a", zipfile.ZIP_DEFLATED) as zipf:
        # zipfile contents will be yyyy-mm-dd_HHMM/{file}
        # so unzipping for debugging generates new directories
        zipf.write(os.path.join(TMPIN, f), os.path.join(NOW, f))
        os.remove(os.path.join(TMPIN, f))

# remove files older than 2 days from archive folder
for f in os.listdir(ARCHIVE):
    p = os.path.join(ARCHIVE, f)
    if os.stat(p).st_mtime < time.time() - (2 * 86400):
        LOGGER.info("removing archive {}".format(p))
        os.remove(p)
os.remove(LOCK)
LOGGER.warning("removed lock {}".format(LOCK))
sys.exit(0)
