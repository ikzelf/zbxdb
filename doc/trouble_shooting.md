Depending on what is going wrong, one of the next steps might help.
If you find an other problem and find a check/fix, please share.

First of all, check the python installation, the installation should be in $HOME/.pyenv
type python and check that it comes from $HOME/.pyenv and not from /usr/bin/
If python is coming from /usr/bin, the pyenv init code is not executed when you logged on. If it is in
.bashrc, also add it in .bash_profile.

All tools can be started from the commandline. The try to provide you with some
guidance about what is happening and what could be wrong. This is also in the
log file[s]. If not enough info is shown, use the -v flag to increase
verbosity. Default zbxdb.py dumps some info in the start and when connected it
reduces output to failing queries and an hourly status update.

It can and will happen that zbxdb_sender logs errors in the logfile. They are mostly the error code from zabbix_sender and most of the times have a value of 1 or 2. 0 means no errors.
1) total failure
2) some items or hosts are not found in zabbix.

What if you see data collected in zbxdb_out/ and in zbxdb_sender/archive/ but data is not arriving in zabbix?
Check the hostname in your configuration file. This should exactly match the one you entered in the zabbix GUI and is case sensitive.

There are a lot of queries. They generate key value pairs and need corresponding items in zabbix to store their data. Sometimes I receive new queries, most of the times without the template modifications. This should not be hard to fix. If you see metrics that are queried but not in the template, feel free to add them to the template and share using a pull request.

Sharing each others work makes us all better.
