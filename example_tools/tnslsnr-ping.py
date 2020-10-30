#!/usr/bin/env python
""" a quick and simple tnsping implementation
    returns tnsping time in ms
    or
    -1 at failure"""
import re
import socket
import struct
import sys
from argparse import ArgumentParser
from timeit import default_timer as timer


def ParseNestedParen(string, level):
    """
    Generate strings contained in nested (), indexing i = level
    """

    if len(re.findall(r"\(", string)) == len(re.findall(r"\)", string)):
        LeftRightIndex = [x for x in zip(
            [Left.start()+1 for Left in re.finditer(r'\(', string)],
            reversed([Right.start() for Right in re.finditer(r'\)', string)]))]

    elif len(re.findall(r"\(", string)) > len(re.findall(r"\)", string)):
        return ParseNestedParen(string + ')', level)

    elif len(re.findall(r"\(", string)) < len(re.findall(r"\)", string)):
        return ParseNestedParen('(' + string, level)

    else:
        return 'fail'

    return [string[LeftRightIndex[level][0]:LeftRightIndex[level][1]]]


def vsnnumToVersion(vsnnum):
    """format version human readable"""
    version = ""

    if vsnnum == "":
        version = 'unknown'
    else:
        hexVsnnum = str(hex(int(vsnnum)))[2:9]
        hexVersionList = struct.unpack('cc2sc2s', hexVsnnum.encode('utf-8'))

        for v in hexVersionList:
            version += str(int(v, 16)) + '.'

    return version


def getVersion(cmd):
    """send get verson cmd"""
    # cmdl = len(cmd).to_bytes(2, byteorder='big')
    # pckl = (len(cmd)+len(TNSPacket)).to_bytes(2, byteorder='big')
    cmdl = struct.pack('>H',len(cmd))
    pckl = struct.pack('>H',len(cmd)+len(TNSPacket))
    TNSPacket[0] = pckl[0]
    TNSPacket[1] = pckl[1]
    TNSPacket[24] = cmdl[0]
    TNSPacket[25] = cmdl[1]

    try:
        #with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        _start = timer()
        s.connect((HOST, PORT))
        scmd = TNSPacket + cmd.encode('utf-8')
        s.sendall(scmd)
        data = s.recv(1024)
        ela = round((timer() - _start)*1000)
        if "VSNNUM" in str(data):
            rectxt = (ParseNestedParen(str(data), 0))
            print(rectxt)
            vsnnum = re.findall(r'(?<=VSNNUM=).+?(?=\))',
                     str(rectxt), flags=re.IGNORECASE)
            err = re.findall(r'(?<=ERR=).+?(?=\))',
                     str(rectxt), flags=re.IGNORECASE)
            version = vsnnumToVersion(vsnnum[0])
        else:
            version = "unknown"
            vsnnum = [str(data)[:20]]
            err = ["131313"]
            ela = 0

        return vsnnum[0], err[0], version, ela
    except:
        # print(sys.exc_info())
        return 0, "12541", "notfound", 0


PARSER = ArgumentParser()
PARSER.add_argument("-s", "--server", action="store",
                    help="dsnname/ip of server", required=True)
PARSER.add_argument("-p", "--port", action="store", default="1521",
                    help="portnr of the listener")
ARGS = PARSER.parse_args()


HOST = ARGS.server
PORT = int(ARGS.port)
TNSPacket = bytearray(
    b"\x00\x46\x00\x00\x01\x00\x00\x00\x01\x37\x01\x2C\x00\x00\x08\x00")
TNSPacket += bytearray(b"\x7F\xFF\x86\x0E\x00\x00\x01\x00\x00\x0C\x00\x3A\x00\x00\x07\xF8")
TNSPacket += bytearray(b"\x0C\x0C\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0A\x4C\x00\x00")
TNSPacket += bytearray(b"\x00\x03\x00\x00\x00\x00\x00\x00\x00\x00")

versioncmd = "(CONNECT_DATA=(COMMAND=version))"
# print(ARGS)

vsnnum, err, version, ela = getVersion(versioncmd)

# if err != "12541":
# 12541: No listener so there was a listener
# print("vsnnum {} err {} version {}, ela {}".format(vsnnum, err, version, ela))


if err == "0":
    print(ela)
    sys.exit(0)
else:
    if err == "1169":
        print("TNS-{}: The listener has not recognized the password".format(err))
    elif err == "1189":
        print(ela)
        # print("TNS-{}: The listener could not authenticate the user".format(err))
        # print("set LOCAL_OS_AUTHENTICATION_LISTENER=off  in the listener.ora  on {}".format(ARGS.server))
    elif err == "12541":
        print("TNS-{}:no listener on {} port {}".format(err, ARGS.server, ARGS.port))
        sys.exit(1)
    elif err == "131313":
        print("process on {} port {} is not responding as an TNS listener ({})".format(
             ARGS.server, ARGS.port, vsnnum.strip()))
        sys.exit(2)
    else:
        print("error: {}".format(err))
        sys.exit(3)
