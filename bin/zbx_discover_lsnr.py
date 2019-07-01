#!/usr/bin/env python3
"""read list containing all required listener, convert to json lld array
   and send to zabbix"""
import json
import os

# input file (no header)
# DNSNAME:PORT
# name1:1521
# name2:1521
#
# output:
# {"data":[{"{#DNSNAME}": "name1", "{#PORT}": "1521"}, {"{#DNSNAME}": "name2", "{#PORT}": "1521"}]}
ME = os.path.splitext(os.path.basename(__file__))[0]
CONFIG = ME + ".cfg"
OUTPUT = ME + ".lld"

L = []
with open(CONFIG, 'rt') as _f:
    for line in _f:
        c = line.rstrip()
        dns, port = c.split(':')
        _e = {"{#DNSNAME}": dns, "{#PORT}": port}
        L.append(_e)

LLD = '{\"data\":' + json.dumps(L) + '}'

F = open(OUTPUT, "w")
F.write(LLD)
F.close()
