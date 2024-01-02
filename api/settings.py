# TODO: Load settings from .env file or environment variables

# Number of workers
max_workers: int = 2

# Web server details
host: str = '127.0.0.1'
port: int = 8000
log_level: str = 'info'
reload: bool = False

# Path to Ansible playbooks and Artifacts store
# base_dir: str = os.path.dirname(os.path.abspath(__file__))
base_dir: str = '/home/kmalgich/redhat/src/validation-scripts'
scripts_path: str = 'runtime-automation'
artifacts_path: str = 'artifacts'
jobs_path: str = 'jobs'
