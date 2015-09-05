# Honolulu Makerfaire Raffle

**Note**: This started as a copy and paste of https://github.com/RobSpectre/Twilio-Hackpack-for-Heroku-and-Flask/ (production branch)

# Dependencies

  * Python 2.7.9

# Installation

`pip install -r requirements.txt`

# Running the App

## Locally

`python app.py`

## Remotely

  - `sudo kill -15 <supervisor processs here>`
  - `source /var/www/hnlmakerfaire/current/bootstrap.sh && sudo -E supervisord -c /etc/supervisord.conf`

## Vagrant

The skeleton has been integrated with
[ansible-nginx-uwsgi-supervisor-deployer](http://github.com/ryankanno/ansible-nginx-uwsgi-supervisor-deployer).  
To test out the installation in Vagrant, you'll ideally want to clone the following projects into the same parent directory:

* [ansible-nginx-uwsgi-supervisor-deployer](http://github.com/ryankanno/ansible-nginx-uwsgi-supervisor-deployer)
* [ansible-nginx-uwsgi-supervisor](http://github.com/ryankanno/ansible-nginx-uwsgi-supervisor)
* [ansible-roles](http://github.com/ryankanno/ansible-roles)

After checking those three projects out, you'll need to do two things:

* Create an ansible.cfg ([example](http://github.com/ryankanno/flask-skeleton/tree/master/ansible.cfg.example)) with the roles_path pointed to the parent directory from above
* `export NGINX_UWSGI_SUPERVISOR_DEPLOYER_PATH=<path_to_where_you_checked_out_ansible-nginx-uwsgi-supervisor-deployer>`

To provision the machines, you'll want to make sure the Vagrantfile contains
the following line:

`ansible.playbook = ENV['NGINX_UWSGI_SUPERVISOR_DEPLOYER_PATH'] + "/provisioning/ansible/site.yml"`

then run the following command:

* `vagrant up`

To deploy new changes to honolulu-makerfaire-raffle, you'll want to run the following command:

* `vagrant provision`

# User flows

## User texts raffle number

  - Text xxx-xxx-xxxx your 5-digit raffle ticket
  - System saves your phone number and ticket to a sqlite database
  - System looks up the number against a datastore that has all the winning raffle
    numbers.
  - If number matches winning raffle number:
    - Text user: winning_copy
  - If number does not match winning raffle number:
    - Text user: not_winning_copy

## Admin adds a winning raffle number

  - Real life drawing has occurred, raffle number has been selected.
  - Admin enters raffle ticket into the admin site.
  - After admin has saved number, system triggers an event to search all saved
    numbers for the ticket number.
  - If a number matches an existing saved number, play yoda voice indicating
    the user has won and should report to the front desk.

