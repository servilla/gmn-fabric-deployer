# gmn-fabric-deployer

Deploys a DataONE Generic Member Node instance using Python Fabric onto an 
Ubuntu 16.04 server.

Disclaimer: this script is experimental - use at your own risk - mileage may 
vary.

# Overview

1. Create new Ubuntu 16.04 server instance with sudo-enable user account, 
which will be the target of the GMN installation.
2. Install local dependencies to execute Fabric (see below for Ubuntu 
specific dependencies; Mac OS or Windows may be different).
3. Create a local Python virtual environment.
4. Install Fabric into the virtual environment.
5. Clone this git repo into a local directory.
6. Use Fabric to deploy GMN.

# Installing Fabric

Fabric is a Python-based tool for interacting with both local and remote 
servers, primarily through the SSH protocol. This is not, however, a tutorial
 on Fabric - for that, go to the Fabric documentation: docs.fabfile.org.
  
Ubuntu 16.04 dependencies:

 - virtualenv
 - build-essential
 - python-dev
 - libssl-dev
 
(install using `apt install virtualenv build-essential python-dev libssl-dev`)
 
To install Fabric:
 
```
cd <work_directory>
virtualenv --python=python2.7 venv
source ./venv/bin/activate
pip install fabric
```
 
# Deploying the Generic Member Node
 
Fabric operates against a standard Python module called `fabfile.py` to 
interact with either a local host or remote host(s). The `fabfile.py` module 
uses both the Fabric API and internal logic to execute commands that will be
performed on target host(s).
  
Perform a target host system update and reboot:
```
fab do_patch -H gmn-test
```


Installing GMN to a host named "gmn-test", including the use of a local CA 
and self-signed client certificates:
```
fab deploy_gmn -H gmn-test  
```