#!/bin/bash
LOG=/var/log/zabbix/zbx_agent.log
{
date 
echo $0 $* 

RES=0 # running and OK
AGENTPROCS=`ps -fuoracle|grep agent_inst|grep -v grep|wc -l|awk '{print $1}'`
# oracle   191443      1  0 Jul18 ?        00:00:05 /u01/app/oracle/product/EMbase/core/12.1.0.5.0/perl/bin/perl /u01/app/oracle/product/EMbase/core/12.1.0.5.0/bin/emwd.pl agent /u01/app/oracle/product/EMbase/agent_inst/sysman/log/emagent.nohup

if [ $AGENTPROCS -eq 0 ]
then
	RES=2 # not running
else
   AGENT=`ps -fuoracle|grep agent_inst|grep -v grep|sed "s/  */ /"|awk -F" " '{print $9}'`
   AGENT_BIN=$(dirname $AGENT)
   sudo -u oracle $AGENT_BIN/emctl status agent | grep "Agent is Running and Ready"

   if [ $? -eq 0 ]
   then
      RES=0
   else 
      RES=1
   fi
fi
echo RES=$RES
date
}>>$LOG 2>&1
echo $RES
