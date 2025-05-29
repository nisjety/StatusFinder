#!/bin/bash

# Wait for RabbitMQ to be up and running
until rabbitmqctl status; do
  echo "Waiting for RabbitMQ to start..."
  sleep 2
done

# Create the virtual host if it doesn't exist
rabbitmqctl list_vhosts | grep -q "discovery" || \
  rabbitmqctl add_vhost discovery

# Set permissions for the admin user on the discovery vhost
rabbitmqctl set_permissions -p discovery admin ".*" ".*" ".*"

echo "RabbitMQ initialization completed"
