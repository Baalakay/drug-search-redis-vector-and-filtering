#!/bin/bash
set -e

echo "Setting up development environment..."

# Function to safely clone or update git repos with credential store protection
clone_or_skip() {
    local repo_url="$1"
    local target_dir="$2"
    if [ ! -d "$target_dir" ]; then
        # Add retry logic for credential store conflicts
        for attempt in 1 2 3; do
            if git clone "$repo_url" "$target_dir" 2>/dev/null; then
                echo "✅ Cloned $(basename "$target_dir")"
                return 0
            else
                echo "⚠️ Git clone attempt $attempt failed for $(basename "$target_dir"), retrying..."
                sleep 1
            fi
        done
        echo "❌ Failed to clone $(basename "$target_dir") after 3 attempts"
        return 1
    else
        echo "⚠️ $(basename "$target_dir") already exists, skipping"
    fi
}


# 2. Setup dotfiles (with error handling and credential store protection)
echo "Setting up dotfiles..."
if [ ! -d ~/.dotfiles ]; then
    # Add delay after previous git operations to prevent credential store conflicts
    sleep 1
    
    # Retry logic for dotfiles clone
    for attempt in 1 2 3; do
        if git clone https://github.com/Baalakay/.dotfiles.git ~/.dotfiles 2>/dev/null; then
            echo "✅ Dotfiles cloned successfully"
            break
        else
            echo "⚠️ Dotfiles clone attempt $attempt failed, retrying..."
            sleep 2
            if [ $attempt -eq 3 ]; then
                echo "❌ Failed to clone dotfiles after 3 attempts, continuing without dotfiles..."
                mkdir -p ~/.dotfiles  # Create empty dir to prevent further attempts
            fi
        fi
    done
    
    if [ -d ~/.dotfiles ] && [ "$(ls -A ~/.dotfiles 2>/dev/null)" ]; then
        cd ~/.dotfiles
        stow --adopt . || true  # Don't fail if stow has conflicts
        git reset --hard || true
        cd $LOCAL_WORKSPACE_FOLDER
        echo "✅ Dotfiles setup complete"
    fi
else
    echo "⚠️ Dotfiles already exist, skipping"
fi

# 4. npm global install (if needed)
echo "Updating npm globally..."
npm install -g npm@11.4.1 || echo "⚠️ Failed to update npm globally, continuing..."

# 6. Project setup
PROJECT_PATH="/workspaces/$ACTIVE_PROJECT"
cd "$PROJECT_PATH"

if [ -d "frontend" ]; then
    # Check if frontend has any meaningful content (excluding node_modules and system files)
    non_node_modules=$(find frontend -mindepth 1 -maxdepth 1 ! -name node_modules ! -name '.DS_Store' ! -name '.git*')
    if [ -z "$non_node_modules" ]; then
        echo "frontend is empty (except node_modules), setting up React Router..."
        # Clean up any residual files that might confuse create-react-router
        rm -f frontend/.DS_Store
        rm -rf frontend/node_modules
        
        # Ensure directory is completely empty before creating React Router app
        # Add delay before create-react-router to prevent git credential store conflicts
        sleep 2
        
        # Retry logic for create-react-router (which also does git operations)
        for attempt in 1 2; do
            if printf "n\ny\n" | npx --yes create-react-router@latest frontend 2>/dev/null; then
                echo "✅ React Router setup complete"
                break
            else
                echo "⚠️ create-react-router attempt $attempt failed, retrying..."
                rm -rf frontend 2>/dev/null || true  # Clean up partial failure
                sleep 3
                if [ $attempt -eq 2 ]; then
                    echo "❌ create-react-router failed after 2 attempts, continuing..."
                    # Ensure directory exists for the Node.js setup later
                    mkdir -p frontend
                fi
            fi
        done
    else
        echo "frontend contains meaningful files, skipping create-react-router setup."
    fi
fi

# Node.js dependencies will be handled in parallel section below

# 6. Fast Python environment setup using pre-installed packages
echo "Setting up Python environment with base packages..."

# Copy base packages first (much faster than installing from PyPI)
# copy-base-packages.sh  # TODO: Create this optimization script if needed

# Run uv sync in background and npm install in parallel
echo "Installing Python and Node.js dependencies in parallel..."

# Python setup (background)
{
    # Check if uv is available
    if command -v uv >/dev/null 2>&1; then
        echo "Running uv sync..."
        uv sync || echo "⚠️ uv sync failed, continuing..."
        if [ -f "requirements.txt" ]; then
            uv pip install -r requirements.txt || echo "⚠️ uv pip install failed, continuing..."
        fi
        echo "✅ Python dependencies complete"
    else
        echo "⚠️ uv command not found, skipping Python dependency installation"
    fi
} &
PYTHON_PID=$!

# Node.js setup (background) 
{
    if [ -d "frontend" ]; then
        cd frontend
        # Use npm ci for faster installs from package-lock.json if it exists
        if [ -f "package-lock.json" ]; then
            if ! npm ci --prefer-offline --no-audit; then
                echo "⚠️ npm ci failed, trying npm install..."
                npm install --prefer-offline --no-audit || echo "⚠️ npm install also failed"
            fi
        elif [ -f "package.json" ]; then
            npm install --prefer-offline --no-audit || echo "⚠️ npm install failed"
        else
            echo "⚠️ No package.json found in frontend directory"
        fi
        echo "✅ Node.js dependencies complete"
        cd ..
    else
        echo "⚠️ No frontend directory found, skipping Node.js setup"
    fi
} &
NODE_PID=$!

# Wait for both to complete
wait $PYTHON_PID
wait $NODE_PID

# Install zsh if not already installed (required for terminal to work)
if ! command -v zsh >/dev/null 2>&1; then
    echo "Installing zsh for terminal support..."
    sudo apt-get update && sudo apt-get install -y --no-install-recommends zsh || echo "⚠️ zsh installation failed, continuing..."
fi

# Set zsh as default shell for vscode user (ensures terminal tool uses correct shell)
if command -v zsh >/dev/null 2>&1; then
    ZSH_PATH=$(which zsh)
    echo "Setting zsh ($ZSH_PATH) as default shell for vscode user..."
    # Update /etc/passwd directly to ensure shell is set correctly
    sudo sed -i "s|^vscode:.*:.*:.*:.*:.*:.*:/bin/bash|vscode:x:1000:1000::/home/vscode:$ZSH_PATH|" /etc/passwd 2>/dev/null || \
    sudo sed -i "s|^vscode:.*:.*:.*:.*:.*:.*:/usr/bin/zsh|vscode:x:1000:1000::/home/vscode:$ZSH_PATH|" /etc/passwd 2>/dev/null || \
    sudo chsh -s "$ZSH_PATH" vscode 2>/dev/null || echo "⚠️ Failed to set zsh as default shell, continuing..."
    # Verify the change
    if grep -q "^vscode:.*:$ZSH_PATH$" /etc/passwd; then
        echo "✅ zsh set as default shell for vscode user"
    fi
fi

echo "Development environment setup complete! Launch a new terminal session to begin in your devcontainer."