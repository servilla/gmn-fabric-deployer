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

quiet = False

def do_patch():
	sudo('apt-get update', quiet=True)
	sudo('apt-get --yes dist-upgrade', quiet=True)
	sudo('apt-get --yes autoremove', quiet=True)
	sudo('shutdown -r now', quiet=True)

def add_user():
	sudo('adduser --ingroup www-data --gecos "GMN" gmn', quiet=quiet)

def add_gmn_sudo():
	put('./01_gmn', '/etc/sudoers.d/01_gmn', use_sudo=True)
	sudo('chown root:root /etc/sudoers.d/01_gmn', quiet=quiet)
	sudo('chmod 644 /etc/sudoers.d/01_gmn', quiet=quiet)

def add_dist_tool_chain():
	tool_chain = 'build-essential python-dev libssl-dev libxml2-dev ' \
				 'libxslt1-dev libffi-dev postgresql-server-dev-9.5 ' \
				 'openssl curl'

	sudo('apt install --yes ' + tool_chain, quiet=quiet)

def add_pip():
	sudo('apt install --yes python-pip', quiet=quiet)
	sudo('pip install --upgrade pip', quiet=quiet)
	sudo('apt remove --yes python-pip', quiet=quiet)

def add_gmn():
	sudo('pip install --upgrade virtualenv', quiet=quiet)
	sudo('mkdir -p /var/local/dataone/gmn_venv', quiet=quiet)
	sudo('mkdir -p /var/local/dataone/gmn_object_store', quiet=quiet)
	sudo('chown gmn:www-data /var/local/dataone/gmn_venv', quiet=quiet)
	with settings(sudo_user='gmn'):
		sudo('virtualenv /var/local/dataone/gmn_venv', quiet=quiet)
		sudo('/var/local/dataone/gmn_venv/bin/pip install --upgrade --no-cache-dir dataone.gmn setuptools==34.3.3')
		sudo('sed -i "$ a PATH=/var/local/dataone/gmn_venv/bin/:\$\"PATH\"" /home/gmn/.bashrc', quiet=quiet)

def add_apache2():
	sudo('apt install --yes apache2 libapache2-mod-wsgi', quiet=quiet)
	sudo('a2enmod --quiet wsgi ssl rewrite', quiet=quiet)
	sudo('cp /var/local/dataone/gmn_venv/lib/python2.7/site-packages/gmn/deployment/gmn2-ssl.conf /etc/apache2/sites-available/', quiet=quiet)
	sudo('cp /var/local/dataone/gmn_venv/lib/python2.7/site-packages/gmn/deployment/forward_http_to_https.conf /etc/apache2/conf-available', quiet=quiet)
	sudo('a2enconf --quiet forward_http_to_https', quiet=quiet)
	sudo('sudo a2ensite --quiet gmn2-ssl', quiet=quiet)

def add_postgres():
	sudo('apt install --yes postgresql', quiet=quiet)
	sudo('passwd -d postgres', quiet=quiet)
	with settings(sudo_user='postgres'):
		sudo('passwd', quiet=quiet)
		sudo('createuser gmn', quiet=quiet)
		sudo('createdb -E UTF8 gmn2', quiet=quiet)

def add_cron():
	put('./gmn_cron', '/var/spool/cron/crontabs/gmn', use_sudo=True)
	sudo('chown gmn:crontab /var/spool/cron/crontabs/gmn', quiet=quiet)
	sudo('chmod 600 /var/spool/cron/crontabs/gmn', quiet=quiet)

def add_local_ca():
	sudo('mkdir -p /var/local/dataone/certs/local_ca/certs', quiet=quiet)
	sudo('mkdir -p /var/local/dataone/certs/local_ca/newcerts', quiet=quiet)
	sudo('mkdir -p /var/local/dataone/certs/local_ca/private', quiet=quiet)
	with cd('/var/local/dataone/certs/local_ca'):
		sudo('cp /var/local/dataone/gmn_venv/lib/python2.7/site-packages/gmn/deployment/openssl.cnf .', quiet=quiet)
		sudo('touch index.txt', quiet=quiet)
		sudo('openssl req -config ./openssl.cnf -new -newkey rsa:2048 -keyout private/ca_key.pem -out ca_csr.pem', quiet=quiet)
		sudo('openssl ca -config ./openssl.cnf -create_serial -keyfile private/ca_key.pem -selfsign -extensions v3_ca_has_san -out ca_cert.pem -infiles ca_csr.pem', quiet=quiet)
		sudo('rm ca_csr.pem')

def add_client_cert():
	with cd('/var/local/dataone/certs/local_ca'):
		sudo('openssl req -config ./openssl.cnf -new -newkey rsa:2048 -nodes -keyout private/client_key.pem -out client_csr.pem', quiet=quiet)
		sudo('openssl rsa -in private/client_key.pem -out private/client_key_nopassword.pem', quiet=quiet)
		sudo('openssl rsa -in private/client_key_nopassword.pem -pubout -out client_public_key.pem', quiet=quiet)
		sudo('openssl ca -config ./openssl.cnf -in client_csr.pem -out client_cert.pem', quiet=quiet)
		sudo('rm client_csr.pem', quiet=quiet)

def add_trust_local_ca():
	with cd('/var/local/dataone/certs/local_ca'):
		sudo('mkdir -p ../ca', quiet=quiet)
		sudo('cp ca_cert.pem ../ca/local_ca.pem', quiet=quiet)
		sudo('c_rehash ../ca', quiet=quiet)

def install_non_trusted_client():
	with cd('/var/local/dataone/certs/local_ca'):
		sudo('mkdir -p ../client', quiet=quiet)
		sudo('cp client_cert.pem private/client_key_nopassword.pem ../client', quiet=quiet)

def install_non_trusted_server():
	sudo('apt install --yes ssl-cert', quiet=quiet)
	sudo('mkdir -p /var/local/dataone/certs/server', quiet=quiet)
	sudo('cp /etc/ssl/certs/ssl-cert-snakeoil.pem /var/local/dataone/certs/server/server_cert.pem', quiet=quiet)
	sudo('cp /etc/ssl/private/ssl-cert-snakeoil.key /var/local/dataone/certs/server/server_key_nopassword.pem', quiet=quiet)

def make_ssl_cert():
	# Only run if the server name or IP address changes.
	# Then, copy the new versions to the GMN standard locations as described above.
	sudo('make-ssl-cert generate-default-snakeoil --force-overwrite', quiet=quiet)

def do_basic_config():
	with cd('/var/local/dataone/gmn_venv/lib/python2.7/site-packages/gmn'):
		sudo('cp settings_site_template.py settings_site.py', quiet=quiet)
		sudo('sed -i "0,/MySecretKey/s//`sudo openssl rand -hex 32`/" settings_site.py', quiet=quiet)

def do_final_config():
	sudo('chown -R gmn:www-data /var/local/dataone/', quiet=quiet)
	sudo('chmod -R g+w /var/local/dataone', quiet=quiet)
	with settings(sudo_user='gmn'):
		sudo('/var/local/dataone/gmn_venv/bin/python /var/local/dataone/gmn_venv/lib/python2.7/site-packages/gmn/manage.py migrate --run-syncdb', quiet=quiet)
	sudo('echo "Etc/UTC" > /etc/timezone', quiet=quiet)
	sudo('rm /etc/localtime', quiet=quiet) # Necessary due to Debian/Ubuntu bug
	sudo('dpkg-reconfigure -f noninteractive tzdata', quiet=quiet)
	sudo('ufw allow 443', quiet=quiet)
	sudo('service apache2 restart', quiet=quiet)

def deploy_gmn():
	add_user()
	add_gmn_sudo()
	add_dist_tool_chain()
	add_pip()
	add_gmn()
	add_apache2()
	add_postgres()
	add_cron()
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