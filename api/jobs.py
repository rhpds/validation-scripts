
import sys
import logging
from ansible_runner import Runner, RunnerConfig
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import settings

this = sys.modules[__name__]

this.executor = None

logger = logging.getLogger('uvicorn')


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


def job(runner):
    '''
    Start Ansible Runner
    '''
    runner.run()  # TODO: handle errors

    logger.info('Job with ID: %s finished', runner.config.ident)


def create_job(module, stage):
    extravars = {
        'module_dir': module,
        'module_stage': stage,
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

    this.executor.submit(job, Runner(config=rc))

    logger.info('Job with ID: %s scheduled', rc.ident)
    return rc.ident


def get_job_status(job_id):
    status = 'unavailable'
    str_uid = str(job_id)
    status_file = (
        f'{settings.base_dir}/'
        f'{settings.artifacts_path}/'
        f'{str_uid}/status'
    )

    if Path(status_file).is_file():
        with open(file=status_file, mode='r', encoding='utf-8') as file:
            status = file.read().rstrip()

    return status
