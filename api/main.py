'''
Validation Scripts API
'''
import logging
from uuid import UUID
from http import HTTPStatus
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

import settings
import jobs

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

    jobs.init()

    yield

    jobs.shutdown()

app = FastAPI(lifespan=lifespan)


@app.post("/api/{module}/{stage}", status_code=HTTPStatus.ACCEPTED)
async def run_task(module: str, stage: str):
    '''
    Create and schedule new job
    '''
    job_id = jobs.create_job(module, stage)

    return {'Job_id': job_id}


@app.get("/api/job/{uid}")
async def get_job(uid: UUID):
    '''
    Get job status
    '''
    status = jobs.get_job_status(uid)

    return {'Status': status}


if __name__ == '__main__':
    uvicorn.run(
        'main:app',
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=settings.reload,
    )
