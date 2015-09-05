# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.require_version ">= 1.7.2"

Vagrant.configure(2) do |config|

  config.ssh.insert_key = true

  config.vm.box = "ubuntu/trusty64"
  config.vm.box_check_update = false
  config.vm.define "makerfaire_vm"

  config.vm.hostname = 'makerfaire.local'
  config.vm.network "private_network", ip: "192.168.51.51"
  config.vm.network "forwarded_port", guest: 80, host: 50051, auto_correct: true

  config.vm.provision :ansible do |ansible|
    ansible.playbook = ENV['NGINX_UWSGI_SUPERVISOR_DEPLOYER_PATH'] + "/provisioning/ansible/site.yml"
    ansible.extra_vars = { ansible_ssh_user: "vagrant" }
    ansible.extra_vars = {
      nginx: {
        vhosts_conf: [
          {
            src_path: ENV['NGINX_UWSGI_SUPERVISOR_DEPLOYER_PATH'] + '/provisioning/ansible/templates/app.nginx.conf.j2',
            target_name: 'hnlmakerfaire.conf'
          }
        ]
      },
      uwsgi: {
        apps_conf: [
          {
            src_path: ENV['NGINX_UWSGI_SUPERVISOR_DEPLOYER_PATH'] + '/provisioning/ansible/templates/app.uwsgi.ini.j2',
            target_name: 'hnlmakerfaire.ini'
          }
        ]
      },
      supervisor: {
        conf: {
          path: 'supervisord.conf.j2'
        },
        apps_conf: [
          {
            src_path: __dir__ + '/provisioning/ansible/templates/hnlmakerfaire.supervisor.conf.j2',
            target_name: 'hnlmakerfaire.conf'
          }
        ]
      },
      application_target_root_path: "/var/www/applications/hnlmakerfaire",
      application: {
        name: 'hnlmakerfaire',
        hostname: 'hnlmakerfaire.com',
        user: 'www-data',
        group: 'www-data',
        port: 50051,
        src: {
          path: __dir__ + '/hnlmakerfaire/',
          requirements_path: __dir__ + '/requirements.txt'
        },
        target: {
          app_path: "{{ application_target_root_path}}/app",
          logs_path: "{{ application_target_root_path}}/logs",
          venvs_path: "{{ application_target_root_path}}/venvs",
          static_path: "{{ application_target_root_path}}/current/hnlmakerfaire/apps/static"
        },
        dependencies: [
          { package: 'python2.7', version: '2.7.6-8' },
          { package: 'python-pip', version: '1.5.4-1ubuntu3' },
          { package: 'python-virtualenv', version: '1.11.4-1' },
          { package: 'python-dev', version: '2.7.5-5ubuntu3' },
        ]
      },
      deploy: {
        supervisor: {
          group: 'hnlmakerfaire:'
        }
      }
    }
    ansible.groups = {
      "web" => ["makerfaire_vm"]
    }
    ansible.limit = 'web'
  end

  config.vm.provider "virtualbox" do |vm|
    vm.name = "makerfaire_vm"
  end
end
