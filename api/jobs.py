
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


def worker_func(runner):
    '''
    Start Ansible Runner
    '''
    runner.run()  # TODO: handle errors

    logger.info('Job with ID: %s finished', runner.config.ident)


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

    this.executor.submit(worker_func, Runner(config=rc))

    job_info = JobInfo(rc.ident, 'scheduled')
    job_info_file = Path(
        f'{settings.base_dir}/'
        f'{settings.jobs_path}/'
        f'{job_id}/job_info.json'
    )
    job_info_file.parent.mkdir(parents=True, exist_ok=True)
    job_info_file.write_text(json.dumps(job_info, indent=4, default=vars))

    logger.info('Job with ID: %s scheduled', job_id)
    return job_id


def get_job_status(job_id):
    '''
    Get job status
    '''
    job_info = json.loads(
        Path(
            f'{settings.base_dir}/'
            f'{settings.jobs_path}/'
            f'{str(job_id)}/job_info.json'
        ).read_text()
    )

    status = 'unavailable'
    status_file = (
        f'{settings.base_dir}/'
        f'{settings.artifacts_path}/'
        f'{job_info["ansible_job_id"]}/status'
    )

    if Path(status_file).is_file():
        with open(file=status_file, mode='r', encoding='utf-8') as file:
            status = file.read().rstrip()

    return status
