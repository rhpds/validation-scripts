import os
from os.path import join, dirname
from dotenv import load_dotenv

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

# Debug mode, more verbose logging + ansible job output returned via 'Get Job Status' API response
debug: bool = bool(os.getenv('DEBUG', False))

# Number of workers
max_workers: int = int(os.getenv('MAX_WORKERS', 2))

# Web server details
host: str = os.getenv('HOST', '127.0.0.1')
port: int = int(os.getenv('PORT', 8000))
log_level: str = os.getenv('LOG_LEVEL', 'info')
reload: bool = bool(os.getenv('RELOAD', False))
root_path: str = os.getenv('ROOT_PATH', '/')

# Path to Ansible playbooks and Artifacts store)
base_dir: str = os.getenv('BASE_DIR', '/app')
scripts_path: str = os.getenv('SCRIPTS_PATH', 'runtime-automation')
artifacts_path: str = os.getenv('ARTIFACTS_PATH', 'artifacts')
jobs_path: str = os.getenv('JOBS_PATH', 'jobs')

# Ansible connection details
ansible_user: str = os.getenv('ANSIBLE_USER', 'lab-user')
ansible_port: int = int(os.getenv('ANSIBLE_PORT', 22))
ansible_ssh_private_key_file: str | None = os.getenv('ANSIBLE_SSH_PRIVATE_KEY_FILE')
ansible_password: str | None = os.getenv('ANSIBLE_PASSWORD')

# Determine authentication method (SSH key takes precedence)
auth_method: str
credential: str

if ansible_ssh_private_key_file:
    auth_method = 'ssh_key'
    credential = ansible_ssh_private_key_file
    # Optional: Add check here if the key file exists os.path.exists(credential)
elif ansible_password:
    auth_method = 'password'
    credential = ansible_password
else:
    raise ValueError(
        "Ansible authentication not configured. "
        "Set either ANSIBLE_SSH_PRIVATE_KEY_FILE or ANSIBLE_PASSWORD environment variable."
    )
