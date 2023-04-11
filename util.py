
# -*- coding: utf-8 -*-

# Copyright (c) 2018-2020 The Particl Core developers
# Distributed under the MIT software license, see the accompanying
# file LICENSE.txt or http://www.opensource.org/licenses/mit-license.php.

import os
import decimal
import subprocess
import json
import time
import traceback
import urllib
from xmlrpc.client import (
    Transport,
    Fault,
)


def jsonDecimal(obj):
    if isinstance(obj, decimal.Decimal):
        return str(obj)
    raise TypeError

class Jsonrpc():
    # __getattr__ complicates extending ServerProxy
    def __init__(self, uri, transport=None, encoding=None, verbose=False,
                 allow_none=False, use_datetime=False, use_builtin_types=False,
                 *, context=None):
        # establish a "logical" server connection

        # get the url
        parsed = urllib.parse.urlparse(uri)
        if parsed.scheme not in ("http", "https"):
            raise OSError("unsupported XML-RPC protocol")
        self.__host = parsed.netloc
        self.__handler = parsed.path
        if not self.__handler:
            self.__handler = "/RPC2"

        if transport is None:
            handler = Transport
            extra_kwargs = {}
            transport = handler(use_datetime=use_datetime,
                                use_builtin_types=use_builtin_types,
                                **extra_kwargs)
        self.__transport = transport

        self.__encoding = encoding or 'utf-8'
        self.__verbose = verbose
        self.__allow_none = allow_none

    def close(self):
        if self.__transport is not None:
            self.__transport.close()

    def json_request(self, method, params):
        try:
            connection = self.__transport.make_connection(self.__host)
            headers = self.__transport._extra_headers[:]

            request_body = {
                'method': method,
                'params': params,
                'id': 2
            }

            connection.putrequest("POST", self.__handler)
            headers.append(("Content-Type", "application/json"))
            headers.append(("User-Agent", 'jsonrpc'))
            self.__transport.send_headers(connection, headers)
            self.__transport.send_content(connection, json.dumps(request_body, default=jsonDecimal).encode('utf-8'))

            resp = connection.getresponse()
            return resp.read()

        except Fault:
            raise
        except Exception:
            # All unexpected errors leave connection in
            # a strange state, so we clear it.
            self.__transport.close()
            raise

        """
        #We got an error response.
        #Discard any response data and raise exception
        if resp.getheader("content-length", ""):
            resp.read()
        raise ProtocolError(
            self.__host + self.__handler,
            resp.status, resp.reason,
            dict(resp.getheaders())
            )
        """


def callrpc(port, method, params=[], wallet=None):
    #port = 51725

    try:
        url = f'http://user:password@127.0.0.1:{port}/'
        if wallet:
            url += 'wallet/' + wallet
        x = Jsonrpc(url)

        v = x.json_request(method, params)
        x.close()
        r = json.loads(v.decode('utf-8'))
    except Exception as e:
        traceback.print_exc()
        raise ValueError('RPC Server Error')

    if 'error' in r and r['error'] is not None:
        raise ValueError('RPC error ' + str(r['error']))

    return r['result']


def callrpc_cli(bindir, datadir, chain, cmd):
    command_cli = os.path.join(bindir, 'ghost-cli')

    args = command_cli + ('' if chain == 'mainnet' else ' -' + chain) + ' -datadir=' + datadir + ' ' + cmd
    p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    out = p.communicate()

    if len(out[1]) > 0:
        raise ValueError('RPC error ' + str(out[1]))

    r = out[0].decode('utf-8').strip()
    try:
        r = json.loads(r)
    except Exception:
        pass
    return r
