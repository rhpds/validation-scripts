'''
Validation Scripts API
'''
import os
import logging
from uuid import UUID
from http import HTTPStatus
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from pydantic_settings import BaseSettings, SettingsConfigDict
from ansible_runner import Runner, RunnerConfig


class Settings(BaseSettings):
    '''
    Build configuration settings using environment variables
    or .env file
    '''
    # Number of workers
    max_workers: int = 2

    # Web server details
    host: str = '127.0.0.1'
    port: int = 8000
    log_level: str = 'info'
    reload: bool = False

    # Path to Ansible playbooks and Artifacts store
    base_dir: str = os.path.dirname(os.path.abspath(__file__))
    scripts_path: str = 'scripts'
    artifacts_path: str = 'artifacts'

    # Use .env file
    model_config = SettingsConfigDict(env_file=f'{base_dir}/.env')


settings = Settings()

logger = logging.getLogger('uvicorn')


@asynccontextmanager
async def lifespan(application: FastAPI):
    '''
    Initialization and shutdown events
    '''
    logger.info(
        'Artifacts directory: %s',
        f'{settings.base_dir}/{settings.artifacts_path}'
    )

    logger.info(
        'Ansible Runner directory: %s',
        f'{settings.base_dir}/{settings.scripts_path}'
    )

    if settings.reload:
        logger.warning(
            'Reloader should\'t not be used'
            'in production environment'
        )

    # Create ThreadPoolExecutor that will be used for
    # running queued ansible_runners
    application.executor = ThreadPoolExecutor(max_workers=settings.max_workers)
    logger.info('Created thread pool with %d workers', settings.max_workers)
    yield
    # Shutdown ThreadPoolExecutor after application is finished
    # all active ansible_runners will be finished gracefully while non-active
    # will be canceled
    application.executor.shutdown(cancel_futures=True)

app = FastAPI(lifespan=lifespan)
app.executor = None


def job(runner):
    '''
    Start Ansible Runner
    '''
    runner.run()  # TODO: handle errors

    logger.info('Job with ID: %s finished', runner.config.ident)


@app.post("/api/{step}/{task}", status_code=HTTPStatus.ACCEPTED)
async def run_task(step: str, task: str):
    '''
    Configure new Ansible Runner and add it to the
    executor queue
    '''
    rc = RunnerConfig(
        private_data_dir=f'{settings.base_dir}/{settings.scripts_path}',
        artifact_dir=f'{settings.base_dir}/{settings.artifacts_path}',
        playbook=step + '/' + task + '.yml',
        quiet=True,
    )

    # TODO: Handle ConfigurationError exception
    rc.prepare()

    app.executor.submit(job, Runner(config=rc))

    logger.info('Job with ID: %s scheduled', rc.ident)
    return {'Job_id': rc.ident}


@app.get("/api/job/{uid}")
async def get_job(uid: UUID):
    '''
    Get job status
    '''
    status = 'unavailable'
    str_uid = str(uid)
    status_file = f'{settings.base_dir}/{settings.artifacts_path}/{str_uid}/status'

    if Path(status_file).is_file():
        with open(file=status_file, mode='r', encoding='utf-8') as file:
            status = file.read().rstrip()

    return {'Status': status}


if __name__ == '__main__':
    uvicorn.run(
        'main:app',
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=settings.reload,
    )
