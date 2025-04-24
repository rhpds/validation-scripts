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
import os

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
    Create and schedule a single job to run scripts for a given module/stage.
    '''
    logger.info('func: run_task, module=%s, stage=%s', module, stage)

    # Validate module and stage existence in the loaded config
    if not (module in MODULE_CONFIG and stage in MODULE_CONFIG.get(module, {})):
        logger.error(f"Module '{module}' or stage '{stage}' not found in MODULE_CONFIG.")
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f'Job configuration for {module}/{stage} not found'
        )

    # Build the list of script executions for this module/stage
    script_executions = []
    try:
        for script_info in MODULE_CONFIG[module][stage]:
            # Ensure required keys exist
            if 'hostname' in script_info and 'path' in script_info:
                 script_executions.append({
                    'module_dir': module, # Pass module name for context within playbook
                    'filename': script_info['path'],
                    'target_host': script_info['hostname']
                 })
            else:
                 logger.warning(f"Skipping script entry due to missing 'hostname' or 'path': {script_info}")
    except KeyError:
         logger.error(f"Error accessing MODULE_CONFIG for {module}/{stage}. Structure might be unexpected.")
         raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f'Internal configuration error for {module}/{stage}'
         )

    if not script_executions:
         logger.warning(f"No valid scripts found to execute for {module}/{stage}.")
         raise HTTPException(
             status_code=HTTPStatus.NOT_FOUND,
             detail=f'No scripts found to execute for job {module}/{stage}'
         )

    # Call the new function ONCE to create a single job for all scripts
    logger.info(f"Creating multi-script job for {module}/{stage} with {len(script_executions)} scripts.")
    job_id = jobs.create_multi_script_job(module, stage, script_executions)

    if job_id is None:
        logger.error(f"Failed to create multi-script job for {module}/{stage}.")
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f'Failed to create job for {module}/{stage}'
        )

    logger.info('func: run_task, module=%s, stage=%s, job_id=%s', module, stage, job_id)
    # Return the single job ID associated with this multi-script execution
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

    response = {'Status': status}
    if os.environ.get("DEBUG") == "true":
        response['Output'] = jobs.get_job_output(uid)

    return response


@app.get("/api/config", response_model=Dict[str, List[str]])
async def get_module_config():
    """Get a module directory structure showing only modules and their stages as JSON"""
    module_config = modules.get_module_config_from_directory_structure(MODULE_CONFIG)
    return module_config


if __name__ == '__main__':
    uvicorn.run(
        'main:app',
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=settings.reload,
    )
