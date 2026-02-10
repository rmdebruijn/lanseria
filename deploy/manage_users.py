#!/usr/bin/env python3
"""CLI tool to manage users in config/users.yaml.

Usage:
    python manage_users.py list
    python manage_users.py add <username> <email> <first_name> <last_name> <role>
    python manage_users.py remove <username>
"""
import sys
import yaml
import bcrypt
import getpass
from pathlib import Path

USERS_FILE = Path(__file__).parent.parent / "config" / "users.yaml"

def load():
    with open(USERS_FILE) as f:
        return yaml.load(f, Loader=yaml.SafeLoader)

def save(config):
    with open(USERS_FILE, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)

def list_users():
    config = load()
    users = config['credentials']['usernames']
    print(f"{'Username':<20} {'Email':<35} {'Roles'}")
    print("-" * 75)
    for name, data in users.items():
        roles = ', '.join(data.get('roles', []))
        print(f"{name:<20} {data.get('email', ''):<35} {roles}")

def add_user(username, email, first_name, last_name, role):
    config = load()
    if username in config['credentials']['usernames']:
        print(f"Error: user '{username}' already exists")
        sys.exit(1)
    password = getpass.getpass(f"Enter password for {username}: ")
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    config['credentials']['usernames'][username] = {
        'email': email,
        'first_name': first_name,
        'last_name': last_name,
        'password': hashed,
        'roles': [role],
    }
    save(config)
    print(f"User '{username}' added with role '{role}'")

def remove_user(username):
    config = load()
    if username not in config['credentials']['usernames']:
        print(f"Error: user '{username}' not found")
        sys.exit(1)
    del config['credentials']['usernames'][username]
    save(config)
    print(f"User '{username}' removed")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == 'list':
        list_users()
    elif cmd == 'add':
        if len(sys.argv) != 7:
            print("Usage: manage_users.py add <username> <email> <first_name> <last_name> <role>")
            sys.exit(1)
        add_user(*sys.argv[2:7])
    elif cmd == 'remove':
        if len(sys.argv) != 3:
            print("Usage: manage_users.py remove <username>")
            sys.exit(1)
        remove_user(sys.argv[2])
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)
