#!/bin/bash
PATH=/usr/local/bin:$PATH
ORATAB=/etc/oratab
ORAENV_ASK=NO
ps -ef|grep _pmon|grep -v grep|grep -v sed|awk '{print $8}'|sed "s/.*_pmon_//"|
while read ORACLE_SID
do
  LINE=`grep "^$ORACLE_SID:" $ORATAB`
  if [ $? -eq 0 ]
  then
    	ORACLE_HOME=`echo $LINE|cut -f2 -d":"`
.       oraenv >/dev/null 2>&1
  	sqlplus -s / as sysdba<<eof
set pages 0 lines 300 head off feed off
col dll form a200
select '{"{#INSTANCE_NAME}":"'||i.instance_name||'","{#ALERTLOG}":"'|| d.value||'/log.xml"}' dll 
from v\$instance i, v\$diag_info d
           where d.name = 'Diag Alert';
eof
  # else
    	# echo $ORACLE_SID unknown
  fi
done | awk 'BEGIN { printf ("{ \"data\":[\n"); comma=" "  }
            { printf ("%s%s\n", comma, $0); comma="," }
           END {printf ("]}\n") }' |tee /tmp/zbx_alertlog.log
