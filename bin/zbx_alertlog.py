#!/usr/bin/env python
"""find all Oracle instances and their alertlog location"""
import collections
import json
# python >= 2.6.6
import os
import platform
import subprocess
from argparse import ArgumentParser

try:
    import psutil
except ImportError:
    print("needs psutil module")
    exit(1)


def get_sids_from_windows():
    """return ORACLE_SID ORACLE_HOME list from windows service defs"""
    sids = []

    for _p in psutil.win_service_iter():
        info = _p.as_dict()

        if 'OracleService' in info['name']:
            # print(info)
            # print(info['name'])
            # print(info['binpath'])
            oracle_sid = info['name'].strip('OracleService')
            oracle_home = os.path.dirname(
                os.path.dirname(info['binpath']))
            sids.append([oracle_sid, oracle_home])

    return sids


def get_sids_from_linux(oratab_file):
    """return ORACLE_SID and ORACLE_HOME list from *nix"""
    sids = []
    o_sids = []

    for _p in psutil.process_iter(attrs=['name', 'cmdline']):
        if _p.info['cmdline']:
            if _p.info['cmdline'][0][:4] in ['ora_', 'asm_', 'apx_']:

                _oracle_sid = _p.info['cmdline'][0].split('_')[2]

                if _oracle_sid not in o_sids:
                    print("new sid {0}".format(_oracle_sid))
                    o_sids.append(_oracle_sid)
    # print(o_sids)
    # now find the ORACLE_HOME for every ORACLE_SID found in oratab

    for sid in o_sids:
        with open(oratab_file, 'r') as _f:
            for line in _f:
                line = line.strip()
                osid = line.split(':')[0]

                if osid == sid:
                    # print(osid)
                    # print(line)
                    oracle_home = line.split(':')[1]
        sids.append([sid, oracle_home])

    return sids


def get_diag_info(sids):
    """get the log.xml location for every given sid"""
    c_path = os.environ['PATH']
    diag_query = """
    set head off
    set veri off
    def sep={0}
    select value||'&sep'||'log.xml' from v$diag_info where name = 'Diag Alert';
    exit
    """.format(os.path.sep)
    a_list = []
    for _sid, _oh in sids:
        print("sid:{0} oh:{1}".format(_sid, _oh))
        os.environ['ORACLE_HOME'] = _oh
        os.environ['ORACLE_SID'] = _sid
        os.environ['PATH'] = os.path.join(_oh, 'bin') +\
            os.pathsep + c_path
        _p = subprocess.Popen(['sqlplus', '-S', '/ as sysdba'],
                              stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
        (stdout, stderr) = _p.communicate(diag_query.encode('utf-8'))
        if stderr:
            print("Errors: {0}\n".format(stderr))
        stdout_lines = stdout.decode('utf-8').split('\n')
        alert_path = stdout_lines[1].strip()
        a_list.append([_sid, alert_path])

    return a_list


def check_log_files(sids):
    """ check existence and access"""

    for _sid, log_file in sids:
        # print("*{0}*".format(log_file))

        if not os.path.exists(log_file):
            # print("create \n{0}".format(log_file))
            open(log_file, 'a').close()
        # print("chmod")
        try:
            os.chmod(log_file, 0o744)
        except PermissionError:
            print("not allowed to chmod; run as owner")


def to_json(sids):
    """prepare to send to zabbix"""
    _l = []

    for sid, file in sids:
        _e = collections.OrderedDict()
        _e = {"{#INSTANCE_NAME}": sid, "{#ALERTLOG}": file}
        _l.append(_e)

    return '{\"data\":'+json.dumps(_l)+'}'


def main():
    """main entry point"""
    _me = os.path.splitext(os.path.basename(__file__))[0]
    _output = _me + ".lld"
    _parser = ArgumentParser()
    _parser.add_argument("-o", "--oratab", action="store",
                         default="/etc/oratab",
                         help="oratab file to use on *nix")
    _parser.add_argument("-s", "--servername", dest="servername", default="localhost",
                         help="zabbix server or proxy name")
    _parser.add_argument("-p", "--port", dest="port", default=10051, required=False,
                         help="zabbix server or proxy name")
    _parser.add_argument("-H", "--hostname", dest="hostname", required=True,
                         help="hostname to receive the discovery array")
    _parser.add_argument("-k", "--key", dest="key", required=True,
                         help="key for the discovery array")
    _args = _parser.parse_args()
    print(_args)
    print(platform.system())

    if platform.system() == "Windows":
        _sids = get_sids_from_windows()
    else:
        _sids = get_sids_from_linux(_args.oratab)

    # for _p in _sids:
        # print("sid {0} oh {1}\n".format(_p[0], _p[1]))
    _a_log_files = get_diag_info(_sids)

    # for sid, a_dir in _a_log_files:
    # print("{0:8s} {1}".format(sid, a_dir))
    check_log_files(_a_log_files)
    dump = to_json(_a_log_files)
    print(dump)

    _f = open(_output, "w")
    _f.write(_args.hostname + " " + _args.key + " " + dump)
    _f.close()
    _cmd = "zabbix_sender -z {} -p {} -i {} -r  -vv".format(
        _args.servername, _args.port, _output)
    os.system(_cmd)


if __name__ == '__main__':
    main()
