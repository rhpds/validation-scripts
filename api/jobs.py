
import sys
import logging
import uuid
import json
from ansible_runner import Runner, RunnerConfig
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import settings

this = sys.modules[__name__]

this.executor = None

logger = logging.getLogger('uvicorn')


class JobInfo:
    def __init__(self, ansible_job_id, status):
        self.ansible_job_id = ansible_job_id
        self.status = status


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


def update_job_status(job_id, status):
    '''
    Update job status
    '''
    job_info_file = Path(
        f'{settings.base_dir}/'
        f'{settings.jobs_path}/'
        f'{job_id}/job_info.json'
    )

    job_info = json.loads(job_info_file.read_text())
    job_info['status'] = status
    job_info_file.write_text(json.dumps(job_info, indent=4))


def worker_func(runner, job_id):
    '''
    Start Ansible Runner
    '''
    update_job_status(job_id, "running")

    status, _ = runner.run()  # TODO: handle errors

    update_job_status(job_id, status)

    logger.info('Job with ID: %s finished', job_id)


def create_job(module, stage):
    '''
    Create and schedule new ansible job
    '''
    job_id = uuid.uuid4()

    extravars = {
        'module_dir': module,
        'module_stage': stage,
        'job_info_dir': (
            f'{settings.base_dir}/'
            f'{settings.jobs_path}/'
            f'{job_id}'
        )
    }

    rc = RunnerConfig(
        private_data_dir=f'{settings.base_dir}/{settings.scripts_path}',
        artifact_dir=f'{settings.base_dir}/{settings.artifacts_path}',
        extravars=extravars,
        playbook='main.yml',
        quiet=True,
    )

    # TODO: Handle ConfigurationError exception
    rc.prepare()

    job_info = JobInfo(rc.ident, 'scheduled')

    job_info_file = Path(
        f'{settings.base_dir}/'
        f'{settings.jobs_path}/'
        f'{job_id}/job_info.json'
    )
    job_info_file.parent.mkdir(parents=True, exist_ok=True)
    job_info_file.write_text(json.dumps(job_info, indent=4, default=vars))

    this.executor.submit(worker_func, Runner(config=rc), str(job_id))
    logger.info('Job with ID: %s scheduled', job_id)
    return job_id


def get_job_status(job_id):
    '''
    Get job status
    '''
    job_info_file = Path(
        f'{settings.base_dir}/'
        f'{settings.jobs_path}/'
        f'{str(job_id)}/job_info.json'
    )

    status = ''
    if job_info_file.exists(): 
        job_info = json.loads(job_info_file.read_text())
        status = job_info['status']

    return status


def get_job_output(job_id):
    '''
    Get job output
    '''
    job_output_file = Path(
        f'{settings.base_dir}/'
        f'{settings.jobs_path}/'
        f'{str(job_id)}/script.out'
    )

    job_output = ''
    if job_output_file.exists():
        job_output = job_output_file.read_text()

    return job_output
