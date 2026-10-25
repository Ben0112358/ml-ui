# ml-ui

`ml-ui` is the user interface stage of the ML pipeline. Its purpose is to provide a frontend layer that connects to endpoints exposed by `ml-serving`.  

This submodule forms a self-contained step in the larger ML pipeline:

```
ml-infra → ml-data → ml-training → ml-serving → ml-ui
```

`ml-ui` can be run **locally** for development or as part of the **full pipeline** orchestrated via `execute.sh` from https://github.com/Ben0112358/ml-pipeline.

To get an overview of how all sub-repos in the full pipeline are tied together, refer to https://github.com/Ben0112358/ml-meta. Links to all sub-repos can be found therein as well.

---

## Project Structure

```
ml-ui/
├── docker-compose.dummy_project.yaml   # Docker Compose file for containerized run
├── Dockerfile.dummy_project            # Dockerfile for containerized project
├── LICENSE
├── poetry.lock
├── pyproject.toml
├── README.md
├── src/
│   └── ml_ui/
│       ├── config.py                   # Global configuration (paths, suffixes)
│       ├── dummy_project/
│       │   ├── ui.py                   # Core UI logic
│       │   ├── utils/                  # Project-specific helpers
│       │   ├── __main__.py             # Local dev CLI entrypoint
│       │   └── __init__.py
│       └── utils/                      # Shared utils (logging, etc.)
└── tests/                              # Unit tests
```

---

## Prerequisites

- **OS**: Linux or macOS  
- **Docker**: Installed and running  
- **Python**: 3.13 (`>=3.13,<3.14`); use `poetry install --sync`  
- **Poetry**: For dependency management  

Set the base directory where shared ML assets and configs are stored:

```bash
export ML_HOMELAB_ROOT=/absolute/path/to/ml-homelab
```

Also set network and port for containerized UI:

```bash
export DOCKER_NETWORK_NAME=<network_name>
export UI_PORT=<port_number>
```

**Important:** In order for the UI to communicate with endpoints created in `ml-serving`, both `ml-serving` and `ml-ui` must use the **same `DOCKER_NETWORK_NAME`**.

---

## Containerized run (more control)

`ml-ui` can be run for example in the following way. You may add args as you see fit.

```bash
export ML_HOMELAB_ROOT=/path/to/ml_homelab_root
export DOCKER_NETWORK_NAME=<network_name>
export UI_PORT=<port_number>
docker-compose -f docker-compose.<project_name>.yaml -p "<project_name>_<mode>" build --no-cache
docker-compose -f docker-compose.<project_name>.yaml -p "<project_name>_<mode>" up
```

For more control, the following can be exported:

```bash
export LOGS_DIR=/path/to/logs
export OUTPUT_SUFFIX=some_suffix
export SERVING_URL=http://serving:8000
```

**Notes**:
- The UI is exposed on `localhost:$UI_PORT`.  
- Ensure the same `DOCKER_NETWORK_NAME` is used as in `ml-serving` if the UI needs to access its endpoints.
- `SERVING_URL` is the base address of the `ml-serving` API used by `investing_allocation_optimizer` and `board_meeting_protocol`. Their Compose files default it to `http://serving:8000`. For `investing_allocation_optimizer`, the host must be `serving`, `localhost`, or `127.0.0.1`.

---

## Python run (less control; simplified)

Run `ml-ui` locally with sensible defaults:

```bash
export ML_HOMELAB_ROOT=/path/to/ml_homelab_root
export DOCKER_NETWORK_NAME=<network_name>
export UI_PORT=<port_number>
python -m ml_ui.<project_name>
```

Or with more control over directories and outputs:

```bash
export ML_HOMELAB_ROOT=/path/to/ml_homelab_root
export DOCKER_NETWORK_NAME=<network_name>
export UI_PORT=<port_number>
export LOGS_DIR=/path/to/logs
export OUTPUT_SUFFIX=some_suffix

python -m ml_ui.<project_name>
```

Also here, the UI will be exposed on `localhost:$UI_PORT`.  

---

## Adding a New Project
1. Create a folder under `ml_ui/` with your project name:

```
src/ml_ui/<new_project>/
```

2. Implement the modules (mirroring `dummy_project`):

- `ui.py` → core UI logic (Streamlit for current projects)  
- `utils/` → project-specific utils  
- `__main__.py` → optional CLI entrypoint for local dev  
- `__init__.py` → marks the package  

3. Add corresponding `docker-compose.<new_project>.yaml` and `Dockerfile.<new_project>`.

4. Set project-specific configuration in `ml_ui/config.py` or via environment variables (`LOGS_DIR`, `OUTPUT_SUFFIX`, `DOCKER_NETWORK_NAME`, `UI_PORT`).  

`src/ml_ui/dummy_project` is a very simple project which can be studied to learn how it all ties together.

---

## board_meeting_protocol

Streamlit page with writing and reviewing modes. History rows are optional, up to three. Each row you add needs its first two documents. The optional third input is pasted email text in both modes. Writing downloads a protocol in the same file type as the new notes, following the font and margins of the latest finished protocol when it can. Reviewing shows short feedback text you can copy, as a nested list of edits. Nothing is sent. A HIGH UNCERTAINTY line names what is unclear. Fill that part in by hand or with an optional note. Saved history is one file per mode under `$ML_HOMELAB_ROOT/.local/board_meeting_protocol/`, outside the git repos.

The backend list comes from serving. When the Cursor backend is selected, the page asks for one model for the history rows and a separate model for the orchestrator. Keys stay in the serving environment; the page does not ask for them.

## Testing

Run unit tests with Poetry:

```bash
poetry run pytest tests/
```

## CI

Pull requests and pushes to `main` run lint (`black`, `flake8`), tests (`pytest`), and security checks (Gitleaks, Trivy, CodeQL, Bandit, pip-audit). Trivy, Bandit, and pip-audit **fail the workflow only on HIGH/CRITICAL** findings; fix versions are bumped in `pyproject.toml` when advisories require it. Dependabot opens weekly grouped updates for Python and GitHub Actions.
