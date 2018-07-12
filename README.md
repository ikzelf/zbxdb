# zbxdb
Zabbix Database monitoring plugin; started as a copy from zbxora-1.98

Written in python, tested with python 3.6
Using drivers available for python
purpose is monitoring any database in an efficient way.
Using zabbix_sender to upload data from crontab

Tested with 
- Oracle 11,12 RAC and single instance databases
- Oracle primary and standby databases
- Oracle asm instances
- Oracle plugin databases
- postgres 9
- mssql 11 (2012)

Adding more db support
----------------------
Very simple: give the dbtype a name and select a driver name for it. Ad the {dbtype}.py to the
dbconnections/ module that should handle the database connection. Add the {driver}.py to the
drivererrors/ module  that should handle exceptions and give a uniform format to zbxdb.py.
Add the {dbtype}/ directory to the etc/zbxdb_checks/ directory and write the sql tests files for it.
Currently Oracle has the most complete set. The idea is that the script detects which role the database
has (primary/slave/standby) and loads the {role}.{mainversion}.cfg file where the sqls are written.

The sql's should return key/value pairs. In the template everything is written from an Oracle starters
point and similar queries are defined for mssql and postgres, both using the same template, item
prototypes and triggers.

usage zbxdb.py -c configfile
resulting in log to stdout and datafile in specified out_dir/{configfile}.zbx

sample config:
- `bin/zbxdb.py`
- `bin/zbxdb_sender`
- `bin/zbxdb_starter`

database config files:
- `etc/zbxdb.fsdb02.cfg`

template for database config file: (copy to zbxdb.{configname}.cfg)
- `etc/zbxdb_config_template.cfg`

default checks files:
- `etc/checks/mssql/primary.11.cfg`
- `etc/checks/oracle/asm.11.cfg`
- `etc/checks/oracle/primary.11.cfg`
- `etc/checks/oracle/primary.12.cfg`
- `etc/checks/oracle/standby.11.cfg`
- `etc/checks/postgres/primary.9.cfg`
- `etc/checks/postgres/slave.9.cfg`

site checks files - examples:
- `etc/checks/oracle/ebs.cfg`
- `etc/checks/oracle/sap.cfg`


mssql config file: zbxdb.mymssqldb.cfg
--------------------------------------
```
[zbxdb]
db_url: //localhost:1466/master
db_type: mssql
db_driver: pytds
username: cistats
password: knowoneknows
server: mysqlserverhost
port:  1466
instance_type: rdbms
role: normal
# for ASM instance role should be SYSDBA
out_dir: $HOME/zbxdb_out
hostname: testhost
checks_dir: etc/zbxdb_checks
site_checks: sap,ebs
```
oracle config file: zbxdb.odb.cfg
--------------------------------------
```
[zbxdb]
db_url: //localhost:15214/fsdb02
db_type: oracle
db_driver: cx_Oracle
username: cistats
password: knowoneknows
instance_type: rdbms
role: normal
# for ASM instance role should be SYSDBA
out_dir: $HOME/zbxdb_out
hostname: testhost
checks_dir: etc/zbxdb_checks
site_checks: sap,ebs
```

postgres config file: zbxdb.pgdb.cfg
--------------------------------------
```
[zbxdb]
db_url: localhost:5432
username: cistats
password: knowoneknows
db_type: postgres
db_driver: psycopg2 
instance_type: rdbms
role: normal
out_dir: $HOME/zbxora_out
hostname: testhost
checks_dir: etc/zbxdb_checks
site_checks: NONE
```

Assuming bin/ is in PATH:
When using this configfile ( zbxdb.py -c etc/zbxdb.odb.cfg )
zbxdb.py will read the configfile
and try to connect to the database using db_url
If all parameters are correct zbxdb will keep looping forever.
Using the site_checks as shown, zbxdb tries to find them in {checks_dir}/{db_type}/sap.cfs
and in {checks_dir}/{db_type}/ebs.cfg (just specify a comma separated list for this)
Outputfile containing the metrics is created in out_dir/zbxdb.odb.zbx

After having connected to the sepcified service, zbxdb finds out the instance_type and version,
after which the database_role is determined, if applicable.
Using these parameters the correct {zbxdb_dir}/{db_type}/X.Y.cfg file is chosen.

After having read the checks_files, a lld array containing the queries is written before
monitoring starts. When monitoring starts, first the *discovery* section is executed.
This is to discover the instances, tablespaces, diskgroups, or whatever you want
to monitor.

zbxdb also keeps track of the used queries.
zbxdb executes queries and expects them to return a valid zabbix_key and values.
The zabbix_key that the queries return should be known in zabbix in your zabbix_host
(or be discovered by a preceding lld query in a *discover* section)

If a database goes down, zbxdb will try to reconnect until killed.
When a new connection is tried, zbxdb reads the config file, just in case
there was a change.
If a checks file in use is changed, zbxdb re-reads the file and logs about this.

zbxdb's time is mostly spent sleeping. It wakes-up every minute and checks if a
section has to be executed or not. Every section contains a minutes:X parameter that 
specifies how big the monitor interval should be for that section. The interval is 
specified in minutes. If at a certain moment multiple sections are to be executed,
they are executed all after each other. If for some reason the checks take longer than a
minute, an interval is skipped.

The idea for site_checks is to have application specific checks in them. The regular checks
should be application independent and be generic for that type and version of database.
For RAC databases, just connect using 1 instance
For pluggable database, just connect to a global account to monitor all plugins

# zbxdb_starter:
this is an aide to [re]start zbxdb in an orderly way. Put it in the crontab, every minute.
It will check the etc directory (note the lack of a leading '/') and start the configuration
files named etc/zbxdb.{your_config}.cfg, each given their own logfile. Notice the sleep in the start
sequence. This is done to make sure not all concurrently running zbxdb sessions awake at
the same moment. Now their awakenings is separated by a second. This makes that if running
10 monitors, they are executing their checks one after an other.
Schedule this in the crontab, every minute.
Make sure that ZBXDB_HOME is defined in your .bash_profile and also add the location of zbxdb.py to
your PATH. In my case: PATH=$HOME/zbxdb/bin:$PATH

# zbxdb_sender:
this is used to really send the data to zabbix. Could be zabbix server, could be zabbix proxy, only
depending on the location of your monitoring host. It collects the files from the out_dir and
sends them in one session. Doing so makes the process pretty efficient, at the cost of a small delay.
Schedule this in the crontab, every minute.

TODO: make zbxdb.py open a pipe to zabbix_sender and use that all the time instead of opening
a new session every minute.

# multi database support
It looks like the various drivers have their own way of reporting errors in their exception handling.
This makes it a bit hard to make the code generic because exactly the exception handling is one of the most important tasks of this
application. Tested are:
- Oracle with cx_Oracle
- postgres with psycopg2
- mssql with pytds

Others are in the pipeline, like:
- cockroachDB with psycopg2
- mysql with mysql.connector
- db2 with ibm_db_dbi

Just try your database and see what happens.
You have to make sure that your driver is installed on your system.

# Warning:
Use the code at your own risk. It is tested and seems to be functional. Use an account with the
least required privileges, both on OS as on database leven.

**Don't use a dba type account for this. Read only access is good enough**

**Don't use a root account for this. Any OS user will do, if it can use zabbix-sender**
Using high privileged accounts is not needed.

database user creation:
```
create user cistats identified by knowoneknows;
grant create session, select any dictionary, oem_monitor to cistats;
```

In Oracle 12 - when using pluggable database:
```
create user c##cistats identified by knowoneknows;
alter user c##cistats set container_data all = container = current;
grant create session, select any dictionary, oem_monitor, dv_monitor to c##cistats;
```

# extra warning:
I have written this in python but not in a pythonic style.
A little cleanup to convert this to clean python code - and preserving efficiency - is welcome.
