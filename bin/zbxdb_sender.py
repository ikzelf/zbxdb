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
"""
import os
import shutil
import subprocess
import sys
import time
import zipfile

ZABBIX_SERVER = os.environ.get("ZABBIX_SERVER", "127.0.0.1")
ZABBIX_SERVER_PORT = os.environ.get("ZABBIX_SERVER_PORT", "10051")

ME = os.path.splitext(os.path.basename(__file__))[0]
HOME = os.path.expanduser("~")
NOW = time.strftime("%Y-%m-%d-%H%M")  # used for zipfile name
# used for logfile name leading to max 7 files
NOWD = time.strftime("%a")
# used to check for 1st run of the day (truncate)
NOWM = time.strftime("%H%M")
NOWDLOG = os.path.join(HOME, "log", ME+"."+NOWD+".log")

ZBXDB_OUT = None

if len(sys.argv) > 1:
    ZBXDB_OUT = sys.argv[1]

if ZBXDB_OUT is None:
    if "ZBXDB_OUT" in os.environ:
        ZBXDB_OUT = os.environ["ZBXDB_OUT"]

if ZBXDB_OUT is None:
    print("""{} specify ZBXDB_OUT in the environment or as first argument of {}
Usage {} [ZBXDB_OUT]
   to collect zbxdb.py outputs from that directory to send to zabbix
   ZBXDB_OUT should point to the out_dir directory in the zbxdb.py config[s]
   using {} directory in {} for work space
   using log directory in {} for logging
   sending to ZABBIX_SERVER {} on ZABBIX_SERVER_PORT {}
   """.format(ME, ME, ME, ME, HOME, HOME, ZABBIX_SERVER, ZABBIX_SERVER_PORT), file=sys.stderr)
    sys.exit(1)

if os.geteuid() == 0:
    print("Running as root, don't run zbxdb* scripts as root, for your own sake", file=sys.stderr)

if not os.path.isdir(ZBXDB_OUT):
    print("{} ZBXDB_OUT directory {} does not exist".format(
        ME, ZBXDB_OUT), file=sys.stderr)
    sys.exit(1)

if not os.access(ZBXDB_OUT, os.W_OK):
    print("{} ZBXDB_OUT directory {} not writeable".format(ME, ZBXDB_OUT),
          file=sys.stderr)
    sys.exit(1)

if NOWM == "0001":
    LOGF = open(NOWDLOG, 'w')
else:
    LOGF = open(NOWDLOG, 'a+')

BASE = os.path.join(HOME, ME)
TMPIN = os.path.join(BASE, "in")
ARCHIVE = os.path.join(BASE, "archive")

for d in [BASE, TMPIN, ARCHIVE]:
    if not os.path.isdir(d):
        os.mkdir(d)

LOCK = os.path.join(BASE, ME+".lock")
if os.path.exists(LOCK):
    print("{} previous run still running(or crashed(lock file: {}))"
          .format(NOW, LOCK), file=LOGF)
    sys.exit(2)

open(LOCK, 'a').close()
for f in os.listdir(ZBXDB_OUT):
    # existing files are overwritten
    shutil.move(os.path.join(ZBXDB_OUT, f), os.path.join(TMPIN, f))

for f in sorted(os.listdir(TMPIN)):
    print("{} processing {}".format(NOW, f), file=LOGF)
    # 1 file at a time. Since zabbix v4 the limit of what can be sent in one
    # run is reduced a lot. Concatenation will give problems.
    process = subprocess.Popen(["zabbix_sender -z {} -p {} -T -i {} -vv"
                                .format(
                                    ZABBIX_SERVER,
                                    ZABBIX_SERVER_PORT,
                                    os.path.join(TMPIN, f))],
                               shell=True,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               close_fds=True)
    output = process.stdout.read().decode()
    err = process.stderr.read().decode()
    exit_code = process.wait()
    print("{} {} zabbix_sender rc: {}".format(NOW, f, exit_code), file=LOGF)
    print("{} output {}: {}".format(NOW, f, output), file=LOGF)
    print("{} stderr {}: {}".format(NOW, f, err), file=LOGF)

    with zipfile.ZipFile(os.path.join(ARCHIVE, "zbx_{}.zip".format(NOW)),
                         "a", zipfile.ZIP_DEFLATED) as zipf:
        # zipfile contents will be yyyy-mm-dd_HHMM/{file}
        # so unzipping for debugging generates new directories
        zipf.write(os.path.join(TMPIN, f), os.path.join(NOW, f))
        os.remove(os.path.join(TMPIN, f))

# remove files older than 2 days from archive folder
for f in os.listdir(ARCHIVE):
    p = os.path.join(ARCHIVE, f)
    if os.stat(p).st_mtime < time.time() - (2 * 86400):
        os.remove(p)
os.remove(LOCK)
sys.exit(0)
