#!/usr/bin/venv/python

# imports
import socket
import hashlib
import re
import bufsock
import yaml

# load config file
with open("bwConfig.yml", 'r') as bwConfig:
    cfg = yaml.load(bwConfig)


hostname = cfg['bw_host']
port = cfg['oci_port']
end = """</BroadsoftDocument>"""
USER_ID = cfg['bw_userId']  # gather username for auth
PASSWORD = cfg['bw_password']  # gather password for auth

passdig = hashlib.sha1(PASSWORD.encode())



def send_to_bw(order, SESSION_ID):
    authXML = """<?xml version="1.0" encoding="ISO-8859-1"?>
    <BroadsoftDocument protocol="OCI" xmlns="C">
      <sessionId xmlns="">%(SESS)s</sessionId>
        <command xsi:type="AuthenticationRequest" xmlns="" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
          <userId>%(USER_ID)s</userId>
        </command>
      </BroadsoftDocument> """

    authVals = {'SESS': SESSION_ID, 'USER_ID': USER_ID}
    authy = authXML % authVals
    authreq = str.encode(authy)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((hostname, port))
    sock.send(authreq)

    while 1:
        bs = bufsock.bufsock(sock)
        version = bs.readto(end)
        # print version

        r = re.search('\<nonce>(\d*)\</nonce>', version.decode())
        nonce = str.encode((r.group(1) + ":"))
        bs.flush()

        # create that digest password
        auth_hash = hashlib.md5(nonce + str.encode(passdig.hexdigest()))
        AUTH_PW = auth_hash.hexdigest()

        loginXML = """<?xml version="1.0" encoding="ISO-8859-1"?>
        <BroadsoftDocument protocol="OCI" xmlns="C">
        <sessionId xmlns="">%(SESS)s</sessionId>
          <command xsi:type="LoginRequest14sp4" xmlns="" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <userId>%(USER_ID)s</userId>
            <signedPassword>%(AUTH_PW)s</signedPassword>
          </command>
        </BroadsoftDocument> """

        loginVals = {'SESS':SESSION_ID, 'USER_ID':USER_ID, 'AUTH_PW':AUTH_PW} #possibly there's a better way to send Values; not very D.R.Y right now
        loginreq = loginXML%loginVals

        bs.send(str.encode(loginreq))
        bs.flush()
        loginresp = bs.readto(end)
        bs.flush()

        #relax
        bs.send(str.encode(order))
        bs.flush()
        orderresp = bs.readto(end)
        return orderresp
        bs.flush()

        logoutXML = """<?xml version="1.0" encoding="ISO-8859-1"?>
        <BroadsoftDocument protocol="OCI" xmlns="C">
          <command xsi:type="LogoutRequest" xmlns="" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <userId>%(USER_ID)s</userId>
          </command>
        </BroadsoftDocument> """

        logoutVals = {'USER_ID':USER_ID}
        logoutreq = logoutXML%logoutVals

        bs.send(str.encode(logoutreq))
        print('sent logout command')
        bs.flush()

        break

    bs.close()
