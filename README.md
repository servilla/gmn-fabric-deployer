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
 on Fabric - for that, go to the Fabric documentation: http://docs.fabfile.org.

There are a number of dependencies that should/must be resolved before 
installing Fabric. For Ubuntu 16.04, these dependencies are:

 - virtualenv (optional, but highly recommended)
 - build-essential
 - python-dev
 - libssl-dev
 
To install these dependencies on Ubuntu 16.04: 
```
apt install virtualenv build-essential python-dev libssl-dev
``` 
To install Fabric:
 
```
cd <working_directory>
virtualenv --python=python2.7 venv
source ./venv/bin/activate
pip install fabric
```
 
# Deploying the Generic Member Node
 
Fabric operates against a standard Python module called `fabfile.py` to 
interact with either a local host or remote host(s). The `fabfile.py` module 
uses both the Fabric API and internal logic to execute commands that will be
performed on target host(s).
  
The default GMN deployment utilizes self-signed certificates for both the
DataONE member node client and the local SSL server. For example, installing
GMN to a host named "gmn-test", including the use of a local CA and self-signed
client certificates:
```
fab deploy_gmn -H gmn-test
```

Options (type, default value):
- `do_os_patch`: Patch and reboot target server (boolean, False)
- `enable_ufw`: Enable UFW firewall with rules (boolean, True)
- `test_env`: Configure for DataONE test environment (boolean, True)
- `gmn_venv`: Specify GMN Python virtual environment (string, gmn_venv)
- `client_cert`: DataONE MN client certificate (string, None)
- `client_key`: DataONE MN client key (string, None)



Examples:

Disabling the UFW firewall:
```
fab deploy_gmn:enable_ufw=False -H gmn-test
```

Creating a different GMN python virtual environment:
```
fab deploy_gmn:gmn_venv=gmn_venv24 -H gmn-test
```

Using a DataONE issued member node client certificate:
```
fab deploy_gmn:client_cert=<path_to_client_cert>,client_key=<path_to_client_key> -H gmn-test
```

To install a new GMN virtual environment (e.g., `gmn_venv24`) next to an existing GMN deployment:
```markdown
fab add_gmn_package:d1_path=<d1_path>,gmn_venv=gmn_venv24,gmn_path=<gmn_path> -H gmn-test
```


# Detailed deployment sequence

There are total of 15 steps involved in the full deployment of GMN, which are
 loosely based on the GMN instructions found at: 
http://dataone-python.readthedocs.io/en/latest/gmn/index.html. Not all 
commands mirror exactly those found in the GMN instructions, and there are 
some additional or modified steps (i.e., add the sudoers configuration). If 
you prefer to exert more control over deploying GMN, you may execute each of 
these commands individually in the order listed.

The steps include:
- `add_gmn_user` - Add the GMN user
- `add_gmn_sudo` - Add a sudoers configuration for the GMN user
- `add_dist_tool_chain` - Add Ubuntu requirements
- `add_pip` - Add Python 'pip' and update
- `add_gmn_package` - Add the GMN package (and dependencies)
- `add_apache2` - Add Apache2 and configuration
- `add_postgres` - Add PostgreSQL
- `add_cron` - Add the GMN crontab entries
- Optional steps:
    - `add_local_ca` - Add a local Certificate Authority
    - `add_client_cert` - Create local self-signed client certificate
    - `add_trust_local_ca` - Add the local CA to the configuration
    - `install_non_trusted_client` Add the self-signed client certificate to the configuration
    - `install_non_trusted_server` - Add the self-signed "snake oil" server certificate to the configuration
    - `install_trusted_client` - Add a DataONE issued member node certificate
    - `install_dataone_chainfile` - Add the DataONE CA chainfile
- `do_final_config` - Perform the final GMN configuration
