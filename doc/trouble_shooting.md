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
