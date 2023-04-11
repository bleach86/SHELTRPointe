# SHELTRPointe
Node for the SHELTR network.

This software is under active development and changes should be expected.

# Running a SHELTRPointe node. 

### Clone the repository.

`git clone https://github.com/bleach86/SHELTRPointe/`

### Change directory.

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


