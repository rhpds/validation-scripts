'''
Validation Scripts API
'''
import logging
from uuid import UUID
from http import HTTPStatus
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

from typing import Dict, Any, List
import yaml

import settings
import jobs
import modules

logger = logging.getLogger('uvicorn')

# Global module configuration, built on service start 
# and accessible by api and job function
MODULE_CONFIG: Dict[str, Any] = {}

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

    logger.info(
        'Root path: %s',
        settings.root_path
    )

    if settings.reload:
        logger.warning(
            'Reloader should\'t not be used'
            'in production environment'
        )
        
    global MODULE_CONFIG
    
    # Set the directory path you want to read
    directory_path = f'{settings.base_dir}/runtime-automation'
    
    try:
        MODULE_CONFIG = modules.parse_module_directory_structure(directory_path)
        logger.info(
            'Module config loaded from: %s',
            directory_path
        )
    except Exception as e:
        logger.error(
            'Error loading module config: %s, Error: %s',
            directory_path, str(e)
        )
        MODULE_CONFIG = {"error": str(e)}

    jobs.init()

    yield

    jobs.shutdown()

app = FastAPI(
    lifespan=lifespan,
    root_path=settings.root_path
)

@app.post("/api/{module}/{stage}", status_code=HTTPStatus.ACCEPTED)
async def run_task(module: str, stage: str):
    '''
    Create and schedule new job
    '''
    logger.info('func: run_task, module=%s, stage=%s', module, stage)
    
    if not (module in MODULE_CONFIG and stage in MODULE_CONFIG["index"]):
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f'Job {module}/{stage} not found'
        )
    
    for scripts in MODULE_CONFIG[module][stage]:
        logger.info('func: run_task, hostname=%s, filename=%s', scripts['hostname'], scripts['path'])
        
        job_id = jobs.create_job(module, stage, scripts['hostname'], scripts['path'])

        if job_id is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail=f'Job {module}/{stage} not found'
            )

        logger.info('func: run_task, hostname=%s, filename=%s, job_id=%s', scripts['hostname'], scripts['path'], job_id)

    return {'Job_id': job_id}


@app.get("/api/job/{uid}")
async def get_job(uid: UUID):
    '''
    Get job status
    '''
    logger.info('GET /api/job/%s', uid)
    
    status = jobs.get_job_status(uid)
    if not status:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f'Job {str(uid)} not found'
        )
    output = jobs.get_job_output(uid)

    return {'Status': status, 'Output': output}



@app.get("/api/config", response_model=Dict[str, List[str]])
async def get_module_config():
    """Get a module directory structure showing only modules and their stages as YAML"""
    module_config = modules.get_module_config_from_directory_structure(MODULE_CONFIG)
    yaml_content = yaml.dump(module_config, default_flow_style=False, sort_keys=False)
    
    # Return YAML response
    return Response(content=yaml_content, media_type="application/yaml")


if __name__ == '__main__':
    uvicorn.run(
        'main:app',
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=settings.reload,
    )
