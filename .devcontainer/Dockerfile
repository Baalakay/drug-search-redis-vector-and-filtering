ARG VARIANT=3.12-bookworm
# Uses multi-arch image (automatically pulls correct architecture for x86_64/ARM64)
FROM ghcr.io/astral-sh/uv:0.7.6-python${VARIANT}
ENV DEBIAN_FRONTEND=noninteractive
# Only set bytecode compilation, but keep default symlink behavior
ENV UV_COMPILE_BYTECODE=1
# We're explicitly NOT setting UV_LINK_MODE=copy here

# We need to set this environment variable so that uv knows where
# the virtual environment is to install packages
ARG ACTIVE_PROJECT
ENV VIRTUAL_ENV="/workspaces/${ACTIVE_PROJECT:-.}/.venv"
ENV PATH="/workspaces/${ACTIVE_PROJECT:-.}/.venv/bin:$PATH"

# ENV VIRTUAL_ENV="/workspace/.venv"

# Set the working directory to match the workspaceFolder in devcontainer.json
WORKDIR /workspaces

# Make sure that the virtual environment is in the PATH so
# we can use the binaries of packages that we install such as pip
# without needing to activate the virtual environment explicitly
#ENV PATH="/opt/venv/bin:$PATH"
ENV PATH="/workspaces/.venv/bin:$PATH"

# Remove imagemagick due to security vulnerability, then install system binaries
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    # Remove imagemagick due to https://security-tracker.debian.org/tracker/CVE-2019-10131 \
    && apt-get purge -y imagemagick imagemagick-6-common \
    # Add additional desired binaries (including zsh for terminal)
    && apt-get install -y --no-install-recommends ghostscript bat fd-find postgresql-client zsh \
    && rm -rf /var/lib/apt/lists/*

# Pre-install common Python packages to speed up cold starts
# This creates a base virtual environment with commonly used packages
RUN uv venv /opt/base-venv \
    && . /opt/base-venv/bin/activate \
    && uv pip install --no-cache \
        # Common development packages
        pytest pytest-cov pytest-mock \
        mypy black isort pre-commit \
        requests httpx pydantic \
        # AWS and cloud packages  
        boto3 botocore \
        # Data packages (if needed)
        pandas numpy \
    && deactivate

# Create script to copy base packages to project venv (faster than installing from scratch)
RUN echo '#!/bin/bash\n\
if [ -d "/opt/base-venv" ] && [ -d "$VIRTUAL_ENV" ]; then\n\
    echo "Copying base packages to project venv for faster startup..."\n\
    cp -r /opt/base-venv/lib/python*/site-packages/* "$VIRTUAL_ENV/lib/python*/site-packages/" 2>/dev/null || true\n\
    cp -r /opt/base-venv/bin/* "$VIRTUAL_ENV/bin/" 2>/dev/null || true\n\
    echo "Base packages copied successfully"\n\
fi' > /usr/local/bin/copy-base-packages.sh \
    && chmod +x /usr/local/bin/copy-base-packages.sh 

    