#!/usr/bin/env python3
"""Generate a bcrypt hash for a password.

Usage: python hash_password.py
"""
import getpass
import bcrypt

password = getpass.getpass("Enter password to hash: ")
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
print(f"\nBcrypt hash:\n{hashed}")
