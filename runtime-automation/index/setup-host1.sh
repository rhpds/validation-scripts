#!/bin/sh

set -x

touch "index-setup-host1.$(date +%T)"

rm -fr /tmp/hello-world.yml

cat << 'EOF' > /tmp/hello-world.yml
---
# This playbook prints a simple debug message
- name: Echo
  hosts: localhost
  connection: local

  tasks:
  - name: Print debug message
    debug:
      msg: Hello, world!

  - name: Wait for 5 seconds
    pause:
      seconds: 5

  - name: Print debug message after pause
    debug:
      msg: Hello, world again!
EOF

ansible-playbook /tmp/hello-world.yml > output.txt