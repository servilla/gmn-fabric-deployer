#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: fabfile

:Synopsis:

    eval `ssh-agent`
    ssh-add $HOME/.ssh/<priv_key>

    or

    Fabric script to deploy a DataONE Generic Member Node
    $ fab <command> -I -i /home/<user>/.ssh/id_rsa -H <host>

:Author:
    servilla
  
:Created:
    04/24/17
"""
from __future__ import print_function

from fabric.operations import *
from fabric.context_managers import *
from fabric.utils import puts

quiet = False
use_local_CA = True

def do_patch():
    puts('Doing Ubuntu system patch...')
    sudo('apt-get update', quiet=quiet)
    sudo('apt-get --yes dist-upgrade', quiet=quiet)
    sudo('apt-get --yes autoremove', quiet=quiet)
    sudo('shutdown -r now', quiet=quiet)

def add_gmn_user():
    puts('Adding user GMN...')
    sudo('adduser --ingroup www-data --gecos "GMN" gmn', quiet=False)

def add_gmn_sudo():
    puts('Adding sudo to user GMN...')
    put('./01_gmn', '/etc/sudoers.d/01_gmn', use_sudo=True)
    sudo('chown root:root /etc/sudoers.d/01_gmn', quiet=quiet)
    sudo('chmod 644 /etc/sudoers.d/01_gmn', quiet=quiet)

def add_dist_tool_chain():
    puts('Adding operating system tools...')
    tool_chain = 'build-essential python-dev libssl-dev libxml2-dev ' \
                 'libxslt1-dev libffi-dev postgresql-server-dev-9.5 ' \
                 'openssl curl'

    sudo('apt install --yes ' + tool_chain, quiet=quiet)

def add_pip():
    puts('Adding pypi version of pip...')
    sudo('apt install --yes python-pip', quiet=quiet)
    sudo('pip install --upgrade pip', quiet=quiet)
    sudo('apt remove --yes python-pip', quiet=quiet)

def add_gmn_package():
    puts('Installing GMN...')
    sudo('pip install --upgrade virtualenv', quiet=quiet)
    sudo('mkdir -p /var/local/dataone/gmn_venv', quiet=quiet)
    sudo('mkdir -p /var/local/dataone/gmn_object_store', quiet=quiet)
    sudo('chown gmn:www-data /var/local/dataone/gmn_venv', quiet=quiet)
    with settings(sudo_user='gmn'):
        sudo('virtualenv /var/local/dataone/gmn_venv', quiet=quiet)
        sudo('/var/local/dataone/gmn_venv/bin/pip install --upgrade --no-cache-dir dataone.gmn setuptools==34.3.3')
        sudo('sed -i "$ a PATH=/var/local/dataone/gmn_venv/bin/:\$\"PATH\"" /home/gmn/.bashrc', quiet=quiet)

def add_apache2():
    puts('Adding apache2...')
    sudo('apt install --yes apache2 libapache2-mod-wsgi', quiet=quiet)
    sudo('a2enmod --quiet wsgi ssl rewrite', quiet=quiet)
    sudo('cp /var/local/dataone/gmn_venv/lib/python2.7/site-packages/gmn/deployment/gmn2-ssl.conf /etc/apache2/sites-available/', quiet=quiet)
    sudo('cp /var/local/dataone/gmn_venv/lib/python2.7/site-packages/gmn/deployment/forward_http_to_https.conf /etc/apache2/conf-available', quiet=quiet)
    sudo('a2enconf --quiet forward_http_to_https', quiet=quiet)
    sudo('sudo a2ensite --quiet gmn2-ssl', quiet=quiet)

def add_postgres():
    puts('Adding postgresql...')
    sudo('apt install --yes postgresql', quiet=quiet)
    sudo('passwd -d postgres', quiet=quiet)
    with settings(sudo_user='postgres'):
        sudo('passwd', quiet=False)
        sudo('createuser gmn', quiet=quiet)
        sudo('createdb -E UTF8 gmn2', quiet=quiet)

def add_cron():
    puts('Adding GMN cron entry...')
    put('./gmn_cron', '/var/spool/cron/crontabs/gmn', use_sudo=True)
    sudo('chown gmn:crontab /var/spool/cron/crontabs/gmn', quiet=quiet)
    sudo('chmod 600 /var/spool/cron/crontabs/gmn', quiet=quiet)

def add_local_ca():
    puts('Making local CA...')
    sudo('mkdir -p /var/local/dataone/certs/local_ca/certs', quiet=quiet)
    sudo('mkdir -p /var/local/dataone/certs/local_ca/newcerts', quiet=quiet)
    sudo('mkdir -p /var/local/dataone/certs/local_ca/private', quiet=quiet)
    with cd('/var/local/dataone/certs/local_ca'):
        sudo('cp /var/local/dataone/gmn_venv/lib/python2.7/site-packages/gmn/deployment/openssl.cnf .', quiet=quiet)
        sudo('touch index.txt', quiet=quiet)
        sudo('openssl req -config ./openssl.cnf -new -newkey rsa:2048 -keyout private/ca_key.pem -out ca_csr.pem', quiet=False)
        sudo('openssl ca -config ./openssl.cnf -create_serial -keyfile private/ca_key.pem -selfsign -extensions v3_ca_has_san -out ca_cert.pem -infiles ca_csr.pem', quiet=False)
        sudo('rm ca_csr.pem')

def add_client_cert():
    puts('Making self-signed client certificate...')
    with cd('/var/local/dataone/certs/local_ca'):
        sudo('openssl req -config ./openssl.cnf -new -newkey rsa:2048 -nodes -keyout private/client_key.pem -out client_csr.pem', quiet=False)
        sudo('openssl rsa -in private/client_key.pem -out private/client_key_nopassword.pem', quiet=False)
        sudo('openssl rsa -in private/client_key_nopassword.pem -pubout -out client_public_key.pem', quiet=False)
        sudo('openssl ca -config ./openssl.cnf -in client_csr.pem -out client_cert.pem', quiet=False)
        sudo('rm client_csr.pem', quiet=quiet)

def add_trust_local_ca():
    puts('Installing local CA to GMN...')
    with cd('/var/local/dataone/certs/local_ca'):
        sudo('mkdir -p ../ca', quiet=quiet)
        sudo('cp ca_cert.pem ../ca/local_ca.pem', quiet=quiet)
        sudo('c_rehash ../ca', quiet=quiet)

def install_non_trusted_client():
    puts('Installing self-signed client certificate...')
    with cd('/var/local/dataone/certs/local_ca'):
        sudo('mkdir -p ../client', quiet=quiet)
        sudo('cp client_cert.pem private/client_key_nopassword.pem ../client', quiet=quiet)

def install_non_trusted_server():
    puts('Installing self-signed server certificated...')
    sudo('apt install --yes ssl-cert', quiet=quiet)
    sudo('mkdir -p /var/local/dataone/certs/server', quiet=quiet)
    sudo('cp /etc/ssl/certs/ssl-cert-snakeoil.pem /var/local/dataone/certs/server/server_cert.pem', quiet=quiet)
    sudo('cp /etc/ssl/private/ssl-cert-snakeoil.key /var/local/dataone/certs/server/server_key_nopassword.pem', quiet=quiet)

def make_ssl_cert():
    # Only run if the server name or IP address changes.
    # Then, copy the new versions to the GMN standard locations as described above.
    sudo('make-ssl-cert generate-default-snakeoil --force-overwrite', quiet=quiet)

def do_basic_config():
    puts('Performing basic configuration...')
    with cd('/var/local/dataone/gmn_venv/lib/python2.7/site-packages/gmn'):
        sudo('cp settings_site_template.py settings_site.py', quiet=quiet)
        sudo('sed -i "0,/MySecretKey/s//`sudo openssl rand -hex 32`/" settings_site.py', quiet=quiet)

def do_final_config():
    puts('Performing final configuration...')
    sudo('chown -R gmn:www-data /var/local/dataone/', quiet=quiet)
    sudo('chmod -R g+w /var/local/dataone', quiet=quiet)
    puts('Creating gmn2 database...')
    with settings(sudo_user='gmn'):
        sudo('/var/local/dataone/gmn_venv/bin/python /var/local/dataone/gmn_venv/lib/python2.7/site-packages/gmn/manage.py migrate --run-syncdb', quiet=quiet)
    puts('Changing TZ to UTC...')
    sudo('echo "Etc/UTC" > /etc/timezone', quiet=quiet)
    sudo('rm /etc/localtime', quiet=quiet) # Necessary due to Debian/Ubuntu bug
    sudo('dpkg-reconfigure -f noninteractive tzdata', quiet=quiet)
    puts('Openning HTTPS through UFW...')
    sudo('ufw allow 443', quiet=quiet)
    puts('Restarting apache2...')
    sudo('service apache2 restart', quiet=quiet)

def deploy_gmn():
    add_gmn_user()
    add_gmn_sudo()
    add_dist_tool_chain()
    add_pip()
    add_gmn_package()
    add_apache2()
    add_postgres()
    add_cron()
    if use_local_CA:
        add_local_ca()
        add_client_cert()
        add_trust_local_ca()
        install_non_trusted_client()
        install_non_trusted_server()
    do_basic_config()
    do_final_config()

def main():
    return 0

if __name__ == "__main__":
    main()