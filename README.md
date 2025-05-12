# Validation Scripts

This project provides a framework for running validation scripts, setup scripts, or any shell scripts on target hosts using Ansible in the backend. It offers both an API and a CLI interface for triggering and managing these script executions.

## Directory Structure

```
validation-scripts/
├── api/                     # FastAPI application for API interface
│   ├── main.py              # Main API application, defines endpoints
│   └── modules.py           # Helpers for parsing module/script structure
├── ansible/                 # Ansible playbooks and configuration
│   ├── ansible.cfg          # Ansible configuration
│   ├── playbook_main.yml    # Main playbook for multi-script execution
│   └── playbook_single_run.yml # Playbook for single script execution (included by main)
├── cli/                     # Command-Line Interface (CLI)
│   └── main.py              # Main CLI application script
├── core/                    # Core logic shared by API and CLI
│   ├── jobs.py              # Manages job creation, status, and output via Ansible Runner
│   ├── settings.py          # Project settings and environment variable management
│   └── .env.example         # Example environment file (user should create .env)
├── runtime-automation/      # Default directory for API-triggered scripts, organized by modules
│   ├── module_name/         # Example: 'index', 'module-02'
│   │   ├── setup-hostname.sh
│   │   ├── validation-hostname.sh
│   │   └── solve-hostname.sh
│   └── ...
├── setup-automation/        # Directory for other example automation scripts
├── artifacts/               # (Created at runtime) Ansible Runner artifact store
├── jobs/                    # (Created at runtime) Stores job-related information
└── requirements.txt         # Python dependencies
```

* **`api/`**: Contains the FastAPI application that exposes endpoints for running scripts and checking job statuses.
* **`ansible/`**: Holds the Ansible configuration and playbooks used to execute the shell scripts on target hosts.
* **`cli/`**: Provides a command-line interface to run ad-hoc scripts from a specified directory.
* **`core/`**: Includes shared modules for managing settings (e.g., Ansible connection details, paths) and job handling (interfacing with Ansible Runner).
* **`runtime-automation/`**: This is the default directory (`SCRIPTS_PATH`) where the API expects to find scripts. Scripts should be organized into subdirectories (modules), and filenames should follow the pattern `stage-hostname.sh` (e.g., `setup-host1.sh`, `validation-serverA.sh`).
* **`setup-automation/`**: Contains example scripts for setup tasks.
* **`requirements.txt`**: Lists all Python packages required to run the project.

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd validation-scripts
    ```
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Configure Environment Variables:**
    Create `core/.env` and set environment variables. Key variables include:
    * `BASE_DIR`: The root directory of the application (defaults to `/app` if running in a container, adjust if running locally).
    * `SCRIPTS_PATH`: Path to the directory containing scripts for the API (default: `runtime-automation`).
    * `ANSIBLE_USER`: Username for SSH connections to target hosts.
    * `ANSIBLE_PASSWORD` or `ANSIBLE_SSH_PRIVATE_KEY_FILE`: Credentials for Ansible. `ANSIBLE_SSH_PRIVATE_KEY_FILE` takes precedence.
    * Refer to `core/settings.py` for all configurable variables.

## API Interface

The API allows for programmatic execution of scripts and status monitoring.

### Running the API

To start the API server (uses Uvicorn):
```bash
python api/main.py
```
By default, it runs on `http://127.0.0.1:8000` (configurable via environment variables `HOST` and `PORT`).

### API Endpoints

* **`GET /api/config`**
    * Description: Retrieves the modules and their stages where at least one host script existing for the stage in `SCRIPTS_PATH`.
    * Response: A JSON object mapping module names to a list of their stages.
        ```json
        {
          "module_name": ["stage1", "stage2"]
        }
        ```

* **`POST /api/{module}/{stage}`**
    * Description: Creates and schedules a job to run all scripts associated with the specified `module` and `stage`. Scripts are expected to be named like `{stage}-{hostname}.sh` within the `{module}` directory (e.g., `runtime-automation/my_module/setup-host1.sh`).
    * Path Parameters:
        * `module` (string): The name of the module (directory name).
        * `stage` (string): The stage of the scripts to run (e.g., `setup`, `validation`, `solve`).
    * Success Response (202 Accepted):
        ```json
        {
          "Job_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        }
        ```
    * Error Responses:
        * 404 Not Found: If the module/stage combination or scripts are not found.
        * 500 Internal Server Error: If job creation fails.

* **`GET /api/job/{uid}`**
    * Description: Retrieves the status of a job. If `DEBUG` mode is enabled in settings and the job is in a terminal state (e.g., `successful`, `failed`), the response will also include job output.
    * Path Parameter:
        * `uid` (UUID string): The ID of the job.
    * Response:
        ```json
        {
          "Status": "running" // or "scheduled", "successful", "failed", "timeout", "canceled"
          // "Output": { ... } // Included if DEBUG=true and job is terminal
        }
        ```
    * Error Response:
        * 404 Not Found: If the job ID is not found.

## CLI Interface

The CLI provides a way to run ad-hoc shell scripts located in a specified directory.

### How to Use the CLI

The main command executes all `.sh` scripts within a given directory. The script's filename (without the `.sh` extension) is used as the target hostname.

**Command Syntax:**
```bash
python cli/main.py <SCRIPT_DIRECTORY> [OPTIONS]
```

**Arguments:**
* `<SCRIPT_DIRECTORY>`: (Required) Path to the directory containing the `.sh` scripts to execute.

**Options:**
* `--poll-interval <INTEGER>`: Interval in seconds to poll for job status. Default is `5`.
* `--debug-ansible`: Enable debug logging for Ansible tasks and include job output in the CLI regardless of job status.

**Example:**

1.  Create a directory with your scripts, for example `my_scripts/`:
    ```
    my_scripts/
    ├── host1.sh
    └── server_alpha.sh
    ```
    Where `host1.sh` will run on `host1` and `server_alpha.sh` on `server_alpha`.

2.  Run the CLI:
    ```bash
    python cli/main.py ./my_scripts
    ```
    Or with options:
    ```bash
    python cli/main.py ./my_scripts --poll-interval 2 --debug-ansible
    ```

The CLI will:
1.  Initialize the job manager.
2.  Scan the specified directory for `*.sh` files.
3.  Create a single job to execute all found scripts on their respective target hosts.
4.  Poll for the job status until it reaches a terminal state (successful, failed, etc.).
5.  Display the final status and, if `--debug-ansible` is used or the job fails, print the job output.
