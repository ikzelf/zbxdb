This tool provides montoring of remote SQL databases and does not need to be installed on the database
server[s]. A better place is on the zabbix server or on a zabbix proxy.

# what is a host?
A host in zabbix can be a computer but also a router, switch, SAN and in this case, a database cluster. A host
in zabbix is a thing that has a collection of items. For Oracle create a host for the physical database, for
SQLServer create a host for an Instance, for Postgres create a host for the cluster, for cockroach create a host for the cluster.
An Oracle database can have multiple Instances and multiple databases. They are collected in a single host.
A SQLServer instance has multiple databases and in an always on configuration can be active on several machines.
That instance is handled by a single host.
A Postgres cluster is very similar to a SQLServer instance.
A cockroach cluster can have many nodes. That cluster is handled by a single host.

# setup
To do that, create a simple OS user that has the ability to use cron, zabbix_sender and is able to connect
to the server or proxy port, as wel as a creating a connection to the remote database[s]. For example create user zbxdb.

logon as zbxdb
use pyenv to manage a local python version for zbxdb

- curl - L https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer | bash
(check that your .bashrc has the pyenv init code in it (logout and back in to check it's working))
- pyenv install 3.9.2
- git clone https://github.com/ikzelf/zbxdb.git
- pyenv virtualenv 3.9.2 zbxdb-3.9.2
- cd zbxdb
- pyenv local zbxdb-3.9.2
- pip install -r requirements.txt
- cd -

- cp -rp zbxdb/etc $HOME/
- cp -p zbxdb/logging.json.example  $HOME/etc/

in your etc directory are some sample monitoring configs. The naming convention for the configs is
zbxdb.{hostname_in_zabbix}.cfg
Replace the samples with your own configuration files.

Add these entries into .bash_profile of the home directoy of the user that will run zbxdb:
- export ZBXDB_HOME=$HOME
- export ZBXDB_OUT=$ZBXDB_HOME/zbxdb_out; #make sure this reflects the out_dir parameter in the monitoring cfg files.)
- export PATH=$PATH:$HOME/zbxdb/bin

source .bash_profile

Load the template(zbxdb_template_v3.xml or zbxdb_template_v4.xml) and link it to hostname in zabbix that
represents the database that you want to monitor. That hostname should be in the hostname parameter in your monitoring .cfg file of this database.

make sure that zabbix_sender is available
create the directory for log, collecting the metrics and workspace for zbxdb_sender
- mkdir $ZBXDB_OUT
- mkdir $ZBXDB_HOME/log
- mkdir $HOME/zbxdb_sender

add into the crontab:
<br >
`* * * * * . $HOME/.bash_profile;$HOME/zbxdb/bin/zbxdb_starter >log/zbxdb_starter.cron 2>&1`
<br >
`* * * * * . $HOME/.bash_profile;$HOME/zbxdb/bin/zbxdb_sender.py -c /etc/zabbix/zabbix_agentd.conf -z zbxdb_out >log/zbxdb_sender.cron 2>&1`

Now, zbxdb_starter will check $ZBXDB_HOME/etc/ for files starting with 'zbxdb.' and ending with '.cfg'
that are writeable. If such a file is found and the corresponding zbxdb.py process is not running, it
will start that process.

zbxdb_sender will check zbxdb_out/ and move the contents to $HOME/zxbdb_sender/in/. Next it will send
the files to zabbix and keep a few days of history in $HOME/zbxdb_sender/archive/

- If anything fails, first check the log/ directory.
- zbxdb.py can be run from the commandline to debug the cfg files.
- if you see data coming into zbxdb_out/ the collection could be OK(errors are reported on stdout)
- if zbxdb_sender/archive/ remains empty, zbxdb_sender is not picking up your metrics.  Check the log. You migh be missing the zabbix-sender utility.

**NOTE**
If database drivers require separate  libraries to be installed, regretfully they need to be installed separately. Some python drivers like psycopg2 have a binary version. Installing them makes life easier.

For postgres follow https://yum.postgresql.org/repopackages.php#pg12 and choose Repo required OS version
yum install postgresql12 postgresql12-devel

For Oracle install latest Oracle Instant Client
https://oracle.github.io/odpi/doc/installation.html#oracle-instant-client-rpm

Also check the prerequistes for pyenv to work
https://github.com/pyenv/pyenv/wiki#suggested-build-environment
