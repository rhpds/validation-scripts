# validation-scripts/cli/main.py
import click
import os # Keep for os.path.exists if used, or rely on Path.exists()
import time
import logging
from pathlib import Path
import sys
import json # For printing output

# --- Adjust Python Path to find the 'core' package ---
PROJECT_ROOT_CLI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT_CLI)) # Add project root to path
# --- End path setup ---

from core import settings # Initialize settings first
from core import jobs     # Then initialize jobs

cli_logger = logging.getLogger('script_cli')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# If you want to see debug logs from jobs.py in the CLI:
# logging.getLogger('uvicorn').setLevel(logging.DEBUG) # 'uvicorn' is the logger name used in jobs.py

def initialize_services_cli():
    """Initializes necessary services from the core package."""
    if not getattr(jobs.this, 'executor', None) or getattr(jobs.this.executor, '_shutdown', True):
        cli_logger.info("CLI: Initializing jobs manager...")
        jobs.init()
    else:
        cli_logger.info("CLI: Jobs manager already initialized.")

def shutdown_services_cli():
    """Shuts down initialized services from the core package."""
    if getattr(jobs.this, 'executor', None) and not getattr(jobs.this.executor, '_shutdown', True):
        cli_logger.info("CLI: Shutting down jobs manager...")
        jobs.shutdown()

@click.command()
@click.argument('script_directory', type=click.Path(exists=True, file_okay=False, dir_okay=True, resolve_path=True))
@click.option('--poll-interval', default=5, help='Interval in seconds to poll for job status.', type=int, show_default=True)
@click.option('--debug-ansible', is_flag=True, help="Enable debug logging for Ansible tasks (sets settings.debug).")
def main(script_directory: str, poll_interval: int, debug_ansible: bool):
    """
    Runs shell scripts from a specified DIRECTORY on hosts derived from filenames.

    Each .sh file in the DIRECTORY (e.g., host1.sh, server_alpha.sh) will be
    executed on a host with the same name as the file (e.g., host1, server_alpha).

    Example:
        python cli/main.py ./my_adhoc_scripts
    """
    if debug_ansible:
        settings.debug = True # Override settings.debug for this CLI run
        logging.getLogger('uvicorn').setLevel(logging.DEBUG) # Also set the logger for jobs.py
        cli_logger.setLevel(logging.DEBUG)
        cli_logger.debug("CLI: Ansible debug mode enabled.")


    cli_logger.info(f"Initializing services for CLI tool...")
    initialize_services_cli()

    scripts_path_obj = Path(script_directory)
    cli_logger.info(f"Scanning directory for scripts: {scripts_path_obj}")

    final_script_executions = []
    found_scripts_count = 0
    for item in scripts_path_obj.iterdir():
        if item.is_file() and item.name.endswith(".sh"):
            found_scripts_count +=1
            hostname = item.stem
            final_script_executions.append({
                'module_dir': '', # Scripts are at the root of script_directory
                'filename': item.name,
                'target_host': hostname
            })
            cli_logger.info(f"Found script: {item.name} for host: {hostname}")

    if not final_script_executions:
        cli_logger.warning(f"No .sh files found in directory: {scripts_path_obj}")
        click.echo(f"No .sh files found in {scripts_path_obj}", err=True)
        shutdown_services_cli()
        sys.exit(1)
        
    cli_logger.info(f"Preparing to execute {len(final_script_executions)} script(s).")

    click.echo(f"Starting job for scripts in {script_directory}...")
    try:
        job_id = jobs.create_multi_script_job(
            module="cli_adhoc",
            stage="run",
            script_executions=final_script_executions,
            custom_script_base_dir=str(scripts_path_obj) # Pass the absolute path to the scripts
        )
    except Exception as e:
        click.echo(f"Error during job creation: {e}", err=True)
        cli_logger.error(f"Job creation failed: {e}", exc_info=True)
        shutdown_services_cli()
        sys.exit(1)


    if job_id is None:
        click.echo("Error: Failed to create and schedule job.", err=True)
        shutdown_services_cli()
        sys.exit(1)

    click.echo(f"Job submitted with ID: {job_id}")
    click.echo("Waiting for job to complete (Ctrl+C to attempt abort)...")

    terminal_statuses = ["successful", "failed", "timeout", "canceled"]
    job_completed_successfully = False
    try:
        while True:
            status = jobs.get_job_status(job_id) # get_job_status expects UUID
            if not status: # Job disappeared or was never fully registered
                click.echo(f"\nError: Job {job_id} status could not be retrieved. It might have been cleaned up or failed very early.", err=True)
                sys.exit(1) # Or handle as appropriate

            # \r to return to beginning of line, end='' to not add newline, flush=True for immediate output
            click.echo(f"\rJob status: {status}{' ' * 20}", nl=False) # Extra spaces to clear previous longer status
            sys.stdout.flush()


            if status in terminal_statuses:
                click.echo() # Newline after final status
                if status == "successful":
                    click.echo(click.style(f"Job {job_id} completed successfully.", fg="green"))
                    job_completed_successfully = True
                else:
                    click.echo(click.style(f"Job {job_id} finished with status: {status}", fg="red"), err=True)
                
                if settings.debug or status != "successful": # Show output in debug or if not successful
                    click.echo("Job Output:")
                    output = jobs.get_job_output(job_id) # get_job_output expects UUID
                    click.echo(json.dumps(output, indent=2, ensure_ascii=False))
                break # Exit polling loop
            
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        click.echo("\nCLI interrupted by user. Job may still be running if already picked up by a worker.", err=True)
        # The actual Ansible process might continue if already started.
        # jobs.shutdown() will try to cancel pending Python futures.
        sys.exit(130) # Standard exit code for Ctrl+C
    except Exception as e:
        click.echo(f"\nAn error occurred during polling: {e}", err=True)
        cli_logger.error(f"Polling error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        click.echo()
        shutdown_services_cli()
        if job_completed_successfully:
            sys.exit(0)
        else:
            sys.exit(1)


if __name__ == '__main__':
    main()