import paramiko
import time

import os
HOST = os.environ["SSH_HOST"]
USER = os.environ["SSH_USER"]
PASS = os.environ["SSH_PASS"]

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    stdout.channel.recv_exit_status()
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    return out, err

# Show all python processes
print("=== All python processes ===")
out, err = run("ps aux | grep python | grep -v grep")
print(out or "none")

# Kill all python
print("\n=== Killing all python processes ===")
out, err = run("ps aux | grep python | grep -v grep | awk '{print $1}' | xargs kill -9 2>/dev/null; echo done")
print(out, err)

time.sleep(2)

# Verify all killed
print("\n=== Remaining python processes ===")
out, err = run("ps aux | grep python | grep -v grep")
print(out or "ALL KILLED - OK!")

# Start the new bot
print("\n=== Starting sonnet_final.py ===")
out, err = run("cd /home/usr_ys1ijj/bot && nohup venv/bin/python sonnet_final.py >> bot.log 2>&1 &")
print("Start result:", out, err)

time.sleep(6)

# Check new process
print("\n=== Checking new process ===")
out, err = run("ps aux | grep sonnet | grep -v grep")
print(out or "NOT RUNNING!")

# Show log
print("\n=== Last bot.log ===")
out, err = run("tail -25 /home/usr_ys1ijj/bot/bot.log")
print(out)

client.close()
