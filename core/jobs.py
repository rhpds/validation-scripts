
import sys
import logging
import uuid
import json
from ansible_runner import Runner, RunnerConfig
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from pathlib import Path
import tempfile
import yaml
import os

# Import settings to access global config
from . import settings

this = sys.modules[__name__]

this.executor = None

logger = logging.getLogger('uvicorn')

jobs = {}


class JobInfo:
    def __init__(self, ansible_job_id, status):
        self.ansible_job_id = ansible_job_id
        self.status = status
        self.lock = Lock()

    def set_status(self, status):
        with self.lock:
            self.status = status

    def get_status(self):
        status = ''
        with self.lock:
            status = self.status

        return status

    def get_ansible_job_id(self):
        return self.ansible_job_id


def init():
    '''
    Initialize jobs scheduler
    '''
    this.executor = ThreadPoolExecutor(max_workers=settings.max_workers)
    logger.info('Created thread pool with %d workers', settings.max_workers)

    logger.info('Jobs directory: %s', settings.jobs_path)


def shutdown():
    '''
    Shutdown jobs scheduler
    '''

    # Shutdown ThreadPoolExecutor after application is finished
    # all active ansible_runners will be finished gracefully while non-active
    # will be canceled
    this.executor.shutdown(cancel_futures=True)
    logger.info('Shutdown thread pool')

def worker_func(runner, job_id):
    '''
    Start Ansible Runner
    '''
    if job_id in jobs:
        jobs[job_id].set_status('running')

    status, rc = runner.run()

    if job_id in jobs:
        jobs[job_id].set_status(status)

    job_info_file = Path(
         f'{settings.base_dir}/'
         f'{settings.jobs_path}/'
         f'{str(job_id)}/ansible_job.json'
    )
    job_info_file.parent.mkdir(parents=True, exist_ok=True)
    job_info_file.write_text(
        json.dumps(
            {
                'ansible_job_id': jobs[job_id].get_ansible_job_id(),
                'status': status,
                'return_code': rc,
                'stdout': runner.stdout.read(),
                'stderr': runner.stderr.read()
            },
            indent=4
        )
    )

    logger.info('Job with ID: %s finished', job_id)

def create_multi_script_job(module: str, stage: str, script_executions: list, custom_script_base_dir: str = None):
    '''
    Create and schedule a single new ansible job to run multiple scripts.
    If custom_script_base_dir is provided, it overrides the default settings.scripts_path.
    '''
    job_id = uuid.uuid4()

    # Extract unique hostnames and build inventory content
    hosts = {item['target_host'] for item in script_executions if 'target_host' in item}
    inventory_content = "[targets]\n"
    for hostname in hosts:
        # Build host line using global settings
        host_line = f"{hostname} ansible_user={settings.ansible_user} ansible_port={settings.ansible_port}"
        if settings.auth_method == 'password':
            # Ensure password is treated as a string literal in the inventory
            host_line += f" ansible_password='{settings.credential}'"
        elif settings.auth_method == 'ssh_key':
            host_line += f" ansible_ssh_private_key_file={settings.credential}"
        inventory_content += host_line + "\n"

    # Write inventory to a temporary file
    inventory_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".ini") as inv_file:
            inv_file.write(inventory_content)
            inventory_path = inv_file.name
            logger.debug(f"Temporary inventory created at: {inventory_path}")
    except Exception as e:
        logger.error(f"Failed to create temporary inventory file: {e}")
        # Clean up if file was partially created
        if inventory_path and os.path.exists(inventory_path):
             os.unlink(inventory_path)
        return None # Indicate failure
    
    # Determine the script base directory
    # If custom_script_base_dir is provided (from CLI), use that. Otherwise, use the default from settings.
    actual_script_base_dir = custom_script_base_dir if custom_script_base_dir else f'{settings.base_dir}/{settings.scripts_path}'

    # Define extravars for the new playbook
    extravars = {
        'module_dir': module,
        'module_stage': stage,
        'script_executions': script_executions, # Pass the list of scripts
        'script_base_dir': actual_script_base_dir,
        'job_info_dir': (
            f'{settings.base_dir}/'
            f'{settings.jobs_path}/'
            f'{job_id}'
        ),
    }

    rc = None
    try:
        rc = RunnerConfig(
            private_data_dir=f'{settings.base_dir}/{settings.scripts_path}',
            artifact_dir=f'{settings.base_dir}/{settings.artifacts_path}',
            inventory=inventory_path,
            extravars=extravars,
            playbook=f'{settings.base_dir}/{settings.ansible_path}/playbook_main.yml',
            quiet=True, # Keep quiet=True unless debugging needed
        )
        rc.prepare()
    except Exception as e: # Catch potential RunnerConfig errors
        logger.error(f"Error preparing RunnerConfig for job {job_id}: {e}")
        # Clean up the temporary inventory file
        if inventory_path and os.path.exists(inventory_path):
            os.unlink(inventory_path)
        return None # Indicate failure

    # Create JobInfo and schedule
    job_info = JobInfo(rc.ident, 'scheduled')
    jobs[job_id] = job_info # Store job info before scheduling

    # Create job info directory and file (similar to create_job)
    job_info_file = Path(
        f'{settings.base_dir}/'
        f'{settings.jobs_path}/'
        f'{job_id}/job_info.json'
    )
    job_info_file.parent.mkdir(parents=True, exist_ok=True)

    # Submit the worker function
    this.executor.submit(worker_func, Runner(config=rc), job_id)

    logger.info('Multi-script job with ID: %s scheduled', job_id)
    return job_id


def get_job_status(job_id):
    '''
    Retrieves the status of an Ansible Runner job.

    This function checks an in-memory dictionary (`jobs`) for the current status
    of a job, identified by its unique job ID. The status is initially set
    when the job is created and updated by the worker thread as the
    Ansible Runner progresses through its lifecycle.

    Args:
        job_id (uuid.UUID): The unique identifier for the job.
                            This typically comes from the API request.

    Returns:
        str: The current status of the job. Possible values include:
             - "scheduled": The job has been accepted and is waiting to be processed
                            by a worker thread. This is the initial state set when
                            `create_multi_script_job` successfully schedules the job.
             - "running": The job has been picked up by a worker thread and the
                          Ansible Runner process (`runner.run()`) has started.
                          This status is set by the `worker_func`.
             - "successful": The Ansible Runner process completed successfully (typically
                             implies a return code of 0). This is a final status.
             - "failed": The Ansible Runner process completed with a non-zero return code,
                         indicating one or more tasks in the playbook failed. This is a
                         final status.
             - "timeout": The job exceeded a timeout (if timeouts are configured in
                          Ansible Runner or the playbook). This is a final status.
             - "canceled": The job was canceled before it completed. This could happen
                           if the `ThreadPoolExecutor` is shut down with `cancel_futures=True`
                           while the job was still in a "scheduled" or "running" state
                           but hadn't finished. This is a final status.
             - "unreachable": While not directly set by your `JobInfo.set_status` explicitly
                              with this string, if an Ansible playbook run results in all hosts
                              being unreachable, the overall status might reflect this.
                              Ansible Runner's `status` can be 'failed' in such cases too.
                              It's good to be aware of Ansible's own terminology.
             - "": An empty string is returned if the `job_id` is not found in the
                   `jobs` dictionary. This indicates that either the job ID is invalid,
                   the job never existed, or (less likely with current implementation)
                   it was removed from tracking.

    Note:
        The specific set of status strings like "successful", "failed", "timeout",
        and "canceled" are determined by the `status` attribute returned by
        `ansible_runner.Runner.run()` and `ansible_runner.Runner.status`.
        Refer to the Ansible Runner documentation for the definitive list of
        these terminal statuses.
    '''
    status = ''

    if job_id in jobs:
        status = jobs[job_id].get_status()

    return status

def get_job_output(job_id):
    '''
    Get job output
    '''
    job_path = Path(
        f'{settings.base_dir}/'
        f'{settings.jobs_path}/'
        f'{str(job_id)}'
    )

    output = {}

    # Collect ansible_job.json
    job_output_file = job_path / 'ansible_job.json'
    if job_output_file.exists():
        output['ansible_job.json'] = job_output_file.read_text()

    # Collect .out files
    for file in job_path.glob('*.out'):
        output[file.name] = file.read_text()

    return output
