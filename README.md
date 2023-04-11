# SHELTRPointe
Node for the SHELTR network.

This software is under active development and changes should be expected.

# Running a SHELTRPointe node. 


### ghostd Requirements.

SHELTRPointe depends on a running instance of ghostd. The folling options must be set either in ghost.conf or as launch options.

```
addressindex=1
server=1
txindex=1

rpcuser=user
rpcpassword=password
rpcallowip=127.0.0.1
rpcport=51725
rpcbind=127.0.0.1

zmqpubrawtx=tcp://127.0.0.1:28332
zmqpubrawblock=tcp://127.0.0.1:28332
zmqpubhashtx=tcp://127.0.0.1:28332
zmqpubhashblock=tcp://127.0.0.1:28332
zmqpubsequence=tcp://127.0.0.1:28332
zmqpubhashwtx=tcp://127.0.0.1:28332

```

### Clone the repository and Change directory. 

`git clone https://github.com/bleach86/SHELTRPointe/`

`cd SHELTRPointe`

### Install dependices using pip.

If pip is not installed, you can install in the following way.

`sudo apt install python3-pip python3-dev`

Now install with pip

`pip3 install -r requirements.txt`

### Start optinons

SHELTRPointe is ran from start.sh. This script has several option arguments.

* --host
* --port
* --ssl-keyfile
* --ssl-certfile

Running `./start.sh` will start the server on localhost on port 52555.

Example with ssl

`./start.sh --host="0.0.0.0" --ssl-keyfile="/path/to/key.pem" --ssl-certfile="/path/to/cert.pem"`


