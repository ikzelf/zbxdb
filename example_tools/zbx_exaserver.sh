#!/usr/bin/env bash
# show count of open problems count <> 0 => there is a problem; investigate
# output of show Open_Problems:
# example output #dm02db01: Connected. Use ^D to exit.
# example output #dm02db01: -> show /System/Open_Problems
# example output #dm02db01:
# example output #dm02db01: Open Problems (0)
# example output #dm02db01: Date/Time                 Subsystems          Component
# example output #dm02db01: ------------------------  ------------------  ------------
# example output #dm02db01:
# example output #dm02db01: -> Session closed
# example output #dm02db01: Disconnected
# example output #dm02db02: Connected. Use ^D to exit.
# example output #dm02db02: -> show /System/Open_Problems
# example output #dm02db02:
# example output #dm02db02: Open Problems (0)
# example output #dm02db02: Date/Time                 Subsystems          Component
# example output #dm02db02: ------------------------  ------------------  ------------
# example output #dm02db02:
# example output #dm02db02: -> Session closed
# example output #dm02db02: Disconnected
# example output #dm02cel01: Connected. Use ^D to exit.
# example output #dm02cel01: -> show /System/Open_Problems
# example output #dm02cel01:
# example output #dm02cel01: Open Problems (0)
# example output #dm02cel01: Date/Time                 Subsystems          Component
# example output #dm02cel01: ------------------------  ------------------  ------------
# example output #dm02cel01:
# example output #dm02cel01: -> Session closed
# example output #dm02cel01: Disconnected
# example output #dm02cel02: Connected. Use ^D to exit.
# example output #dm02cel02: -> show /System/Open_Problems
# example output #dm02cel02:
# example output #dm02cel02: Open Problems (0)
# example output #dm02cel02: Date/Time                 Subsystems          Component
# example output #dm02cel02: ------------------------  ------------------  ------------
# example output #dm02cel02:
# example output #dm02cel02: -> Session closed
# example output #dm02cel02: Disconnected
# example output #dm02cel03: Connected. Use ^D to exit.
# example output #dm02cel03: -> show /System/Open_Problems
# example output #dm02cel03:
# example output #dm02cel03: Open Problems (0)
# example output #dm02cel03: Date/Time                 Subsystems          Component
# example output #dm02cel03: ------------------------  ------------------  ------------
# example output #dm02cel03:
# example output #dm02cel03: -> Session closed
# example output #dm02cel03: Disconnected
LOG=/var/log/zabbix/zbx_exaserver.log
date >>$LOG
echo $0 $* >>$LOG
sudo -u root /usr/local/bin/dcli -g /opt/oracle.SupportTools/onecommand/all_group -l root ipmitool 'sunoem cli "show /System/Open_Problems"'|tee -a $LOG|
      grep -i "open problems" | awk '{print $NF}' | sed "s/(//" | sed "s/)//" |
      awk 'BEGIN{problems=0} {problems += $1} END{print problems}'
date >>$LOG
