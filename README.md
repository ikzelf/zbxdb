# zbxdb
Zabbix Database monitoring plugin; started as a copy from zbxora-1.98

Written in python, tested with **python 3.6**
Using drivers available for python
purpose is monitoring any database in an efficient way.
Using zabbix_sender to upload data from crontab
By popular demand: password fields are encrypted to password_enc fields during startup when a password
value is detected.

Tested with

- Oracle 11,12 RAC and single instance databases
- Oracle primary and standby databases
- Oracle asm instances
- Oracle plugin/multitenant databases
- postgres 9
- postgres 10
- SQL Server 2012(11)
- SQL Server 2016(13)
- mysql 5
- mysql 8
- cockroachDB 2

zbxdb is very cluster aware and will monitor the full cluster using a single connection to a single instance and monitor all databases served by that instance.

Create a separate host for every Oracle database in zabbix.
Create a separate host for every mssql instance in zabbix.

# Adding more db support
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

# database config files examples

- [cockroachDB](etc/zbxdb.crdb.cfg)
- [SQLServer](etc/zbxdb.ms.cfg)
- [mysql](etc/zbxdb.mysql.cfg)
- [Oracle](etc/zbxdb.odb.cfg)
- [postgres](etc/zbxdb.pgdb.cfg)


# default checks files

They consist of sections. Every section  has a parameter minutes that specifies after how many minutes the queries will have to be run again.

section with 'discover' in their name have a special meaning, the return json arrays to zabbix for the low level discovery. The other sections just contain queries returning key/value pairs.

- [cockroach v2](etc/zbxdb_checks/cockroach/primary.2.cfg)
- [SQL Server 2012](etc/zbxdb_checks/mssql/primary.11.cfg)
- [SQL Server 2016](etc/zbxdb_checks/mssql/primary.13.cfg)
- [Oracle 11g ASM](etc/zbxdb_checks/oracle/asm.11.cfg)
- [Oracle 12c ASM](etc/zbxdb_checks/oracle/asm.12.cfg)
- [Oracle 11g](etc/zbxdb_checks/oracle/primary.11.cfg)
- [Oracle 12c](etc/zbxdb_checks/oracle/primary.12.cfg)
- [Oracle 11g standby](etc/zbxdb_checks/oracle/standby.11.cfg)
- [Oracle 12c standby](etc/zbxdb_checks/oracle/standby.12.cfg)
- [postgres v9](etc/zbxdb_checks/postgres/primary.9.cfg)
- [postgres v9 slave](etc/zbxdb_checks/postgres/slave.9.cfg)
- [mysql v5](etc/zbxdb_checks/mysql/primary.5.cfg)
- [mysql v8](etc/zbxdb_checks/mysql/primary.8.cfg)

Do you find a version of a database that is not -yet- in the list, start with a copy of the highest previous version and include the version number in the name as above. The checks really are nothing more that queries that return key/value  pairs to be sent to zabbix. You need to be sure that

- your `db_driver` is listed in bin/drivererrors/
- your `db_type` is listed in bin/dbconnections/
- your `db_type` is listed as directory in `checks_dir`/
- your `db_type` has a checks file for your version db in `checks_dir/primary.{version}.cfg`

drivererrors and dbconnections are loaded dynamically, based on the `db_driver` and `db_type` parameters.

# site checks files - examples

- [Oracle ebs](etc/zbxdb_checks/oracle/ebs.cfg)
- [SAP on Oracle](etc/zbxdb_checks/oracle/sap.cfg)

# working of zbxdb.py
Assuming bin/ is in PATH:
When using this configfile ( zbxdb.py -c etc/zbxdb.odb.cfg )
zbxdb.py will read the configfile
and try to connect to the database using db_url
If all parameters are correct zbxdb will keep looping forever.
Using the site_checks as shown, zbxdb tries to find them in `checks_dir`/`db_type`/sap.cfg
and in `checks_dir`/`db_type`/ebs.cfg (just specify a comma separated list for this)
Outputfile containing the metrics is created in out_dir/zbxdb.odb.zbx

After having connected to the specified service, zbxdb finds out the instance_type and version,
after which the database_role is determined, if applicable.
Using these parameters the correct `checks_dir`/`db_type`/{role}.{version}.cfg file is chosen. For a regular database this translates to 'primary.{version}.cfg'

After having read the checks_files, a lld array containing the queries is written before
monitoring starts. When monitoring starts, first the *discovery* section is executed.
This is to discover the instances, tablespaces, diskgroups, or whatever you want to monitor.

zbxdb also keeps track of the used queries.
zbxdb executes queries and expects them to return a valid zabbix_key and values. The zabbix_key that the queries return should be known in zabbix in your zabbix_host (or be discovered by a preceding lld query in a *discover* section)

If a database goes down, zbxdb will try to reconnect until killed. When a new connection is tried, zbxdb reads the config file, just in case there was a change. If a checks file in use is changed, zbxdb re-reads the file and logs about this.

zbxdb's time is mostly spent sleeping. It wakes-up every minute and checks if a
section has to be executed or not. Every section contains a minutes:X parameter that 
specifies how big the monitor interval should be for that section. The interval is 
specified in minutes. If at a certain moment multiple sections are to be executed,
they are executed all after each other. If for some reason the checks take longer than a
minute, an interval is skipped.

The idea for site_checks is to have application specific checks in them. The regular checks
should be application independent and be generic for that type and version of database.
For RAC databases, just connect using 1 instance
For pluggable database, just connect to a common user to monitor all plugin databases.
# Enclosed tools:
## zbxdb_starter
this is an aide to [re]start zbxdb in an orderly way. Put it in the crontab, every minute.
It will check the etc directory (note the lack of a leading '/') and start the configuration
files named etc/zbxdb.{your_config}.cfg, each given their own logfile. Notice the sleep in the start
sequence. This is done to make sure not all concurrently running zbxdb sessions awake at
the same moment. Now their awakenings is separated by a second. This makes that if running
10 monitors, they are executing their checks one after an other.
**Schedule this in the crontab, every minute.**
Make sure that ZBXDB_HOME is defined in your .bash_profile and also add the location of zbxdb.py to
your PATH. In my case: PATH=$HOME/zbxdb/bin:$PATH
## zbxdb_stop
Just to stop all currently running zbxdb.py scripts for the user.

## zbxdb_sender
this is used to really send the data to zabbix. Could be zabbix server, could be zabbix proxy, only
depending on the location of your monitoring host. It collects the files from the out_dir and
sends them in one session. Doing so makes the process pretty efficient, at the cost of a small delay.
**Schedule this in the crontab, every minute.**

TODO: make zbxdb.py open a pipe to zabbix_sender and use that all the time instead of opening
a new session every minute.
## zbx_discover_oradbs
bash script that performs the Oracle database discovery. Place in in the crontab, for a few times a day, or run in manually on moments that you know a new database has been created, or removed.
## zbx_alertlog.sh
A bash script that runs as an user command, by the agent, that connects to all instances on the host and discovers all log.xml files for alert monitoring

# modules
## drivererrors
Drivererrors has 2 entries:

- `db_errorcode(driver, excep)`
- `db_error_needs_new_session(driver, code)`

### `db_errorcode`
returns the errorcode and text it got from excep.
### `db_error_needs_new_session`
returns True if with the given code it is useless to try to continue the current session. I oracle, for example 3113 is  a good reason to forget the session and to try to connect again. Every driver has
## dbconnections
dbconnections has 3 entries:

- `connection_info(con)`
- `connect_string(config)`
- `connect(db, c)`

### connection_info
Has to fill info about the connected database like

- dbversion
- sid
- serial
- instance_type
- iname
- uname
- db_role

### connect_string
returns the connect string needed to connect to the database.
### connect
performs the actual connect  to the database using  the configuration parameters.

# auto database discovery for Oracle
prepare a host with a discovery rule 'oradb.lld' of type zabbix_trapper.
Give the discovery rule a host prototye "{#DB_NAME}" and add it to groups you need, but also to group prototypes "{#GROUP}" and "{#ALERT}".
The alert group is optional but is meant to be for ... alerting.
Add the zbxdb template to the host prototype.
Set the inventory to automatic.

zbx_discover_oradbs is the -bash- script that does the discovery. It needs host equivalence for all machines that you want to be discovered. zbx_discover_oradbs visits all hosts and uses lsnrctl to find all instances. It uses the common conventions regarding instance and database naming.  It works for single database and for RAC databases.

the configuration file:
```
## site_prefix (clustername|"") host[s]
prefix cluster01 clu01node01 clu01node02
prefix cluster02 clu02node01 clu02node02
prefix "" singlehost1
## for alerting based on a group:
alert_pattern=(cluster01_|PB$)
#pattern matches hostnames that contain cluster01_ or end on PB
alert_group=your_generated_alert_group
```

the usage:
zbx_discover_oradb hostname_with_the_oradb.lld_key [zabbix_(server|proxy)]

Since zbxdb template contains a nodata trigger for every database, expect that after a few minutes a missing data alert is raised, if you did not also start zbxdb.py for the newly discovered database[s].

a file is created that contains the discovery json array that is sent to zabbix.
a file is created in the /tmp/ directory of every  host that is visited for the discovery. It is the remote discovery script.

sample output file:
```
testhost oradb.lld 1548959488 rotra_srv-yum-001 oradb.lld 1551257701 { "data":[
 {"{#DB_NAME}":"prefix_cluster01_CTEST1P","{#GROUP}":"prefix_cluster01","{#ALERT}":"your_generated_alert_group"}
,{"{#DB_NAME}":"prefix_cluster01_DBFS1P","{#GROUP}":"prefix_cluster01","{#ALERT}":"your_generated_alert_group"}
,{"{#DB_NAME}":"prefix_cluster01_RONR","{#GROUP}":"prefix_cluster01","{#ALERT}":"your_generated_alert_group"}
,{"{#DB_NAME}":"prefix_cluster01_TRANS","{#GROUP}":"prefix_cluster01","{#ALERT}":"your_generated_alert_group"}
,{"{#DB_NAME}":"prefix_cluster02_CTEST1PB","{#GROUP}":"prefix_cluster02","{#ALERT}":"your_generated_alert_group"}
,{"{#DB_NAME}":"prefix_cluster02_CTEST2A","{#GROUP}":"prefix_cluster02"}
,{"{#DB_NAME}":"prefix_cluster02_PTVLO","{#GROUP}":"prefix_cluster02"}
,{"{#DB_NAME}":"prefix_cluster02_TRANS","{#GROUP}":"rprefix_cluster02"}
,{"{#DB_NAME}":"prefix_CC12","{#GROUP}":"prefix"}
]}
```
Just in case you already have added lot's of databases manually, you can put them in an ignore list so you won't get lot's of errors during the processing of the discovery data in zabbix.
Just put the generated hostnames that you want to ignore in $HOME/etc/zbx_discover_oradbs.ignore, next to the cfg file.

zabbix is not very flexible regarding group prototypes. The group names that are generated are not allowed to pre-exist (v4) Sorry for that, we have to deal with that.

# Warning:
Use the code at your own risk. It is tested and seems to be functional. Use an account with the
least required privileges, both on OS as on database level. Especially Oracle has good options to limit the required privileges. On others you still might need special privileges to access the system's tables/views.  Sadly enough, for some databases you still need a database super user type of account to be able to access the needed tables/views.

**Don't use a dba type account for this. Read only access is good enough**

**Don't use a root account for this. Any OS user will do, if it can use zabbix-sender**
Using high privileged accounts is not needed in Oracle.

# database user creation:
## Oracle classic
```
create user cistats identified by knowoneknows;
grant create session, select any dictionary, oem_monitor to cistats;
```
## Oracle multitenant
In Oracle 12 or later - when using pluggable database, in the root container, create a common user:
```
create user c##cistats identified by knowoneknows;
alter user c##cistats set container_data all container = current;
grant create session, select any dictionary, oem_monitor, dv_monitor to c##cistats;
```
## SQLserver
```
create login and user to monitor with low privs in all databases (including model)
USE [master]
GO
CREATE LOGIN [CISTATS] WITH PASSWORD=N'knowoneknows', DEFAULT_DATABASE=[master], CHECK_EXPIRATION=OFF, CHECK_POLICY=OFF
GO
GRANT VIEW SERVER STATE TO [CISTATS]
GO
USE [msdb]
GO
EXEC master.dbo.sp_MsForEachDB 'USE [?]; CREATE USER [CISTATS] FOR LOGIN [CISTATS];'
GO
use msdb
EXEC sp_addrolemember N'SQLAgentReaderRole', N'CISTATS';
EXEC sp_addrolemember N'SQLAgentUserRole', N'CISTATS';
GO
GRANT SELECT on sysjobs to [CISTATS];
GRANT SELECT on sysjobhistory to [CISTATS];
grant select on sysjobactivity to [CISTATS];
```
## postgreSQL
```
v9:
create user cistats with superuser encrypted password 'knowoneknows';

v10 and later:
create user cistats with encrypted password 'knowoneknows';
GRANT pg_read_all_settings TO cistats;
GRANT pg_monitor to cistats;
```
