#!/usr/bin/env python
"""call request listener sid list from all listeners given in config file
   to generate discovery array for oradb.lld
   config file csv format is:
   'site;[cluster];alert_group;protocol;[user];[password];[password_enc];machine[,]...'
   site         - somesite
   cluster      - in case of RAC
   alert_group
   protocol     - ssh or psr
   user         - optional for ssh
   password     - plain text form of psr password (removed during encryption)
   password_enc - encrypted form of psr password
   machine[s]   - list of cluster members or single machine name

   run lsnrctl status on all machines and form the oradb.lld array
   """

# should work with python 2.7 and 3
from __future__ import print_function

import base64
import csv
import json
import os
import platform
import pwd
import shutil
import subprocess
import sys
from argparse import ArgumentParser
from tempfile import NamedTemporaryFile

from pypsrp.client import Client
from pypsrp.shell import Process, SignalCode, WinRS
from pypsrp.wsman import WSMan


def encrypted(plain):
    """encrypt plaintext password"""

    return base64.b64encode(bytes(plain, 'utf-8'))


def decrypted(pw_enc):
    """return decrypted password"""

    return base64.b64decode(pw_enc).decode("utf-8", "ignore")


def get_config(filename, _me):
    """read the specified configuration file"""
    user = pwd.getpwuid(os.geteuid())
    home = user.pw_dir

    if os.path.isabs(filename) or os.path.isfile(filename):
        c_file = filename
    else:
        c_file = os.path.join(home, filename)

    if not os.path.exists(c_file):
        raise ValueError("Configfile " + c_file + " does not exist")

    encryptedF = 0
    tempfile = NamedTemporaryFile(mode='w', delete=False)
    with open(c_file, 'r') as _inif, tempfile:
        reader = csv.DictReader(_inif, delimiter=';')
        writer = csv.DictWriter(tempfile, delimiter=';',
                                fieldnames=reader.fieldnames)

        writer.writeheader()

        for row in reader:

            if row['site'] and row['site'][0] not in ["#", ""]:
                if row['password']:
                    # print("encrypting pwd for {} on {}".format(row['user'], row['members']))
                    row['password_enc'] = encrypted(row['password']).decode()
                    row['password'] = ''
                    # print("decrypted {}".format(decrypted(row['password_enc'])))
                    encryptedF += 1

            writer.writerow(row)

    if encryptedF:
        shutil.move(tempfile.name, c_file)
    else:
        os.remove(tempfile.name)

    config = []
    with open(c_file, 'r') as _inif:
        reader = csv.DictReader(_inif, delimiter=';')

        for row in reader:

            if row['site'] and row['site'][0] not in ["#", ""]:
                if row['password_enc']:
                    # print("decrypting pwd for {} on {}".format(row['user'], row['members']))
                    row['password'] = decrypted(row['password_enc'])
                config.append(row)

    return config


def get_ssh(config):
    commands = """
tns=`ps -ef|grep tnslsnr|grep -v grep|awk '{print $8}'|sort|uniq|tail -1`
echo tns=$tns
dir=$(dirname $tns)
echo "dir=$dir"
export ORACLE_HOME=$(dirname $dir)
$ORACLE_HOME/bin/lsnrctl status
    """
    errors = 0
    results = []
    for member in config['members'].split(','):
        ssh = subprocess.Popen(["ssh", "-q", member],
                               stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        std_data, std_err = ssh.communicate(commands.encode())
        res = std_data.decode()
        err = std_err.decode()
        if err:
            print("get_ssh: {} -> err: {}".format(config, err), file=sys.stderr)
            errors += 1
        results.append(res)
    return errors, config, results


def get_psr(config):

    errors = 0
    results = []
    try:
        ssl = config['protocol'].split('/')[1]
    except Exception as e:
        ssl = ""
    for member in config['members'].split(','):
        res = ""
        try:
            if ssl:
                client = Client(member, ssl=True, auth="ntlm",
                                cert_validation=False,
                                connection_timeout=3,
                                username=config['user'], password=config['password'])
            else:
                client = Client(member, ssl=False, auth="ntlm",
                                cert_validation=False,
                                connection_timeout=3,
                                username=config['user'], password=config['password'])

            stdout, stderr, _rc = client.execute_cmd(REMCMD)
            if "decode" in dir(stdout):
                res = stdout.decode()
                err = stderr.decode()
            else:
                res = stdout
                err = stderr
            if err:
                print("get_psr: {} -> err: {}".format(config, err), file=sys.stderr)
                errors += 1
        except Exception as e:
            print("get_psr: Connect to {} failed: {}".format(member, e.args[0]),
                  file=sys.stderr)
            errors += 1

        results.append(res)

    return errors, config, results


def get_winRS(config):

    errors = 0
    results = []
    try:
        ssl = config['protocol'].split('/')[1]
    except Exception as e:
        ssl = ""
    for member in config['members'].split(','):
        res = ""
        try:
            if ssl:
                client = WSMan(member, ssl=True, auth="ntlm",
                               cert_validation=False,
                               connection_timeout=3,
                               username=config['user'], password=config['password'])
            else:
                client = WSMan(member, ssl=False, auth="ntlm",
                               cert_validation=False,
                               connection_timeout=3,
                               username=config['user'], password=config['password'])

            with WinRS(client) as shell:
                process = Process(shell, REMCMD)
                print(process)
                stdout, stderr, _rc = process.invoke()
            if "decode" in dir(stdout):
                res = stdout.decode()
                err = stderr.decode()
            else:
                res = stdout
                err = stderr
            if err:
                print("get_winRS: {} -> err: {}".format(config, err),
                      file=sys.stderr)
                errors += 1
        except Exception as e:
            print("get_winRS: Connect to {} failed: {}".format(member, e.args[0]),
                  file=sys.stderr)
            errors += 1

        results.append(res)

    return errors, config, results


def main():
    """the entry point"""
    _me = os.path.splitext(os.path.basename(__file__))[0]
    _output = _me + ".lld"

    _parser = ArgumentParser()
    _parser.add_argument("-c", "--cfile", dest="configfile", default=_me+".cfg",
                         help="Configuration file", metavar="FILE", required=False)
    _parser.add_argument("-v", "--verbosity", action="count", default=0,
                         help="increase output verbosity")
    _parser.add_argument("-l", "--lld_key", action="store", default="oradb.lld",
                         help="key to use for zabbix_host lld")
    _parser.add_argument("-z", "--zabbix_host", action="store",
                         help="zabbix hostname that has the oradb.lld rule")
    _parser.add_argument("-s", "--server", action="store",
                         help="zabbix server or proxy name")
    _parser.add_argument("-p", "--port", action="store", default="10050",
                         help="port of zabbix server of proxy to send to")
    _args = _parser.parse_args()

    config = get_config(_args.configfile, _me)

    if _args.verbosity:
        print(config)
        print(_args)

    lsnrstats = []

    errors = 0

    for row in config:
        if row['protocol'] == "ssh":
            lsnrstats.append(get_ssh(row))
        elif row['protocol'] in ['psr', 'psr/ssl']:
            lsnrstats.append(get_psr(row))
        elif row['protocol'] in ['winRS', 'winRS/ssl']:
            lsnrstats.append(get_winRS(row))
        else:
            print("unknown/implemented protocol {} supported (ssh,psr[/ssl],winRS[/ssl])".format(row['protocol']),
                  file=sys.stderr)
            errors += 1

    if _args.verbosity > 1:
        print(lsnrstats)

    databases = []

    for member in lsnrstats:
        print("errors member {}: {}".format(member[1]['members'], member[0]))
        errors += member[0]

        if _args.verbosity > 1:
            print("member config {}".format(member[1]))
        instances = []

        for lines in member[1]:
            for line in lines.split('\n'):
                if "Instance" in line:
                    if "READY" in line:
                        if _args.verbosity > 2:
                            print("line: {}".format(line))
                        instance = line.split('"')[2]

                        if _args.verbosity > 2:
                            print(instance)
                        instances.append(instance)
        sorti = sorted(list(set(instances)))

        if member[1]['cluster']:
            if _args.verbosity > 1:
                print("cluster {} {}".format(member[1]['cluster'], sorti))
            dbs = set([i.rstrip('0123456789') for i in sorti])

        else:
            if _args.verbosity > 1:
                print("node {} {}".format(member[1]['members'], sorti))
            dbs = sorti

        dbs = [i.lstrip('-+') for i in dbs]

        for db in dbs:
            _e = {"{#DB_NAME}": member[1]['site']+"_"+db}

            if member[1]['cluster']:
                _e.update(
                    {"{#GROUP}": member[1]['site']+"_"+member[1]['cluster']})
            else:
                _e.update({"{#GROUP}": member[1]['site']})

            if member[0]['alert_group']:
                _e.update({"{#ALERT}": member[1]['alert_group']})
            databases.append(_e)

    if _args.verbosity > 1:
        print(databases)

    OUTPUT = _me + ".lld"

    if errors == 0:
        if _args.zabbix_host:
            array = str(_args.zabbix_host) + ' ' + _args.lld_key + \
                ' ' + '{\"data\":' + json.dumps(databases) + '}'
            F = open(OUTPUT, "w")
            F.write(array)
            F.close()
            CMD = "zabbix_sender -z {} -p {} -i {} -r  -vv".format(
                _args.server, _args.port, OUTPUT)
            os.system(CMD)
        else:
            print('{\"data\":' + json.dumps(databases) + '}')
    else:
        print("{} had errors ({}), bailing out".format(
            _me, errors), file=sys.stderr)
        print('{\"data\":' + json.dumps(databases) + '}', file=sys.stderr)

    sys.exit(errors)


if __name__ == "__main__":
    remcmd = "lsnrctl status"

    if int(platform.python_version().split('.')[0]) < 3:
        REMCMD = remcmd.decode()
    else:
        REMCMD = remcmd
    main()
