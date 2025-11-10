Shared Devcontainer Configuration

This repository provides a robust, ready-to-use devcontainer environment for use across multiple projects. It is designed to be symlinked into any project as a shared `.devcontainer` folder. 

> **Prerequisite:**
> You must have [Docker](https://www.docker.com/products/docker-desktop/) and an IDE such as [Cursor](https://www.cursor.so/), [Windsurf](https://windsurf.ai/), or [VS Code](https://code.visualstudio.com/) installed on your local machine before using this template. 
> - You must also install the [Dev Containers (Remote Development) extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers).
> - Cursor and Windsurf are forks of VSCode and so have built-in support for devcontainers.
> - Please install these tools first if you haven't already.
>
> See the [official devcontainers documentation](https://code.visualstudio.com/docs/devcontainers/containers) for more details and platform-specific setup.
>
> **IMPORTANT:**
> This repository is intended to be **symlinked** into each code/project folder as a shared `.devcontainer` folder. **Do not add any project-specific code, onboarding, or workflow details into the folder that contains this .devcontainer folder**
> - This repo (and the local folder you clone it to) is for global devcontainer configuration only.
> - All project-specific onboarding, code, and workflow documentation should be maintained in the individual project repository/folder.
> - This ensures a single source of truth for devcontainer setup across all projects, while keeping project code and logic separate.

---

## 🧩 Why Use a Shared Devcontainer?

- **Centralized Management**: Maintain one set of devcontainer configs for all projects.
- **Consistent Environments**: All projects use the same Docker, Compose, and feature setup.
- **Easy Updates**: Update your devcontainer setup in one place for all projects.
- **Per-Project Isolation**: Each project gets its own `.env` and Docker named volumes for dependencies and caches (`.venv`, `frontend/node_modules`, `.mypy_cache`, `.pytest_cache`, `dist/`).
- These five folders all get stored on the container instead of your local machine (which is ideal), and will be re-created if they don't already exist. The `node_modules` directory is added to any existing frontend folder if it doesn't already exist there (to generate your frontend dependencies with `npm install`). It will not overwrite or delete any existing files in your existing frontend or any other source code elsewhere. These folders can safely be removed and recreated if you want to have the backend dependencies reinstalled (by way of uv creating them in the `.env` from the pyproject.toml), or the frontend dependencies being regenerated (by way of `npm install` generating them in the frontend/node_modules folder).

---

## How to Use This Global Devcontainer

1. **Clone this repository somewhere accessible on your machine:**
> cd to the path where you want the shared .devcontainer folder and configs stored (e.g. "development-devcontainer" is used below but choose your own name)
   ```sh
   cd /Users/Blake/Documents/projects/development-devcontainer
   git clone https://github.com/Baalakay/development-devcontainer-shared-config-template .devcontainer
   ```
2. **In each project folder (not the above folder), symlink the `.devcontainer` directory to this global repo:**
   ```sh
   cd /path/to/your/project/folder
   ln -s ~/development-devcontainer .devcontainer
   chmod +x .devcontainer/set-project-root.sh
   ```
3. **Open your project in your IDE from the project root:**
   ```sh
   cursor .   # For Cursor IDE
   code .     # For VS Code
   ```
4. **Rebuild and open in devcontainer.**

---

## How It Works
- Again, each project gets its own `.devcontainer/.env` and Docker named volumes for dependencies and caches: `.venv`, `frontend/node_modules`, `.mypy_cache`, `.pytest_cache`, and `dist`.
- The `set-project-root.sh` script (run via `initializeCommand` in `devcontainer.json`) ensures the correct project context is set before the container is built.
- All devcontainer config, Dockerfiles, and scripts are managed centrally in this repo.

---

See https://github.com/Baalakay/development-devcontainer-project-template for a ready-to-go Python/React/TypeScript/TailwindCSS project template that works with this devcontainer.

For more details, see the [official devcontainers documentation](https://containers.dev/) and [VS Code documentation on devcontainers](https://code.visualstudio.com/docs/devcontainers/containers). 
