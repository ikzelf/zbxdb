This tool provides montoring of remote SQL databases and does not need to be installed on the database
server[s]. A better place is on the zabbix server or on a zabbix proxy.

To do that, create a simple user that has the ability to use cron, zabbix_sender and is able to connect
to the server or proxy port, as wel as a creating a connection to the remote database[s]. For example create user zbxdb.

logon as zbxdb
use pyenv to manage a local python version for zbxdb
curl -L https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer | bash

pyenv install 3.6.5

git clone https://github.com/ikzelf/zbxdb.git
pip install <zbxdb/requirements.txt

cp -rp zbxdb/etc $HOME/
in your etc directories are some sample monitoring configs. The naming convention for the configs is
zbxdb.{db name}.cfg
Replace the samples with your own configuration files.

Add this entries into .bash_profile of the home directoy of the user that will run zbxdb:
  export ZBXDB_HOME=$HOME
  export ZBXDB_OUT=$ZBXDB_HOME/zbxora_out  ## make sure this reflects the out_dir parameter in the
                                           ## monitoring cfg files.
  export PATH=$PATH:$HOME/zbxdb/bin

source .bash_profile

Load the template (zbxdb_template_v3.xml or zbxdb_template_v4.xml) and link it to hostname in zabbix that
represents the database that you want to monitor.

make sure that zabbix_sender is available
create the directory for log, collecting the metrics and workspace for zbxdb_sender
mkdir $ZBXDB_OUT
mkdir $ZBXDB_HOME/log
mkdir $HOME/zbxdb_sender

add into the crontab:
* * * * * $HOME/zbxdb/bin/zbxdb_starter > /dev/null 2>&1
* * * * * $HOME/zbxdb/bin/zbxdb_sender  > /dev/null 2>&1

Now, zbxdb_starter will check $ZBXDB_HOME/etc/ for files starting with 'zbxdb.' and ending with '.cfg'
that are writeable. If such a file is found and the corresponding zbxdb.py process is not running, it
will start that process.

zbxdb_sender will check $ZBXDB_OUT/ and move the contents to $HOME/zxbdb_sender/in/. Next it will send
the files to zabbix and keep a few days of history in $HOME/zbxdb_sender/archive/
