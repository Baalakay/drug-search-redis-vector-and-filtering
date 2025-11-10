#!/bin/bash
# Quick checker to see if launch template setup worked
# Run this after SSH'ing into a new instance to verify everything is ready

echo "🔍 Checking if launch template setup completed successfully..."

# Check if completion marker exists
if [ -f "/tmp/devcontainer-setup-complete" ]; then
    echo "✅ Launch template setup completion marker found"
    echo "   Setup completed: $(cat /tmp/devcontainer-setup-complete)"
else
    echo "❌ Launch template setup completion marker NOT found"
    echo "   This means either:"
    echo "   1. Launch template is still running (wait a few minutes)"
    echo "   2. Launch template failed"
    echo "   3. No launch template was used"
fi

echo ""
echo "🧪 Verifying devcontainer requirements..."

# Check Node.js
if command -v node &> /dev/null; then
    echo "✅ Node.js available: $(node --version)"
else
    echo "❌ Node.js not available globally"
fi

# Check Docker buildx
if command -v docker &> /dev/null; then
    BUILDX_VERSION=$(docker buildx version 2>/dev/null | grep -o '[0-9]*\.[0-9]*\.[0-9]*' | head -1 || echo "not found")
    if [ "$BUILDX_VERSION" != "not found" ]; then
        echo "✅ Docker buildx: $BUILDX_VERSION"
        if [ "$(printf '%s\n' "0.17.0" "$BUILDX_VERSION" | sort -V | head -n1)" = "$BUILDX_VERSION" ]; then
            echo "❌ Buildx version too old (need 0.17+)"
        fi
    else
        echo "❌ Docker buildx not found"
    fi
else
    echo "❌ Docker not available"
fi

echo ""

# Final recommendation
if [ -f "/tmp/devcontainer-setup-complete" ] && command -v node &> /dev/null; then
    echo "🎉 Ready for devcontainer development!"
    echo ""
    echo "Next steps:"
    echo "1. git clone [your-repository]"
    echo "2. cd [repository-name]" 
    echo "3. Open in Cursor"
    echo "4. Ctrl+Shift+P → 'Dev Containers: Rebuild and Reopen in Container'"
else
    echo "⚠️  Setup incomplete. Choose an option:"
    echo ""
    echo "Option A - Wait and retry (if launch template is still running):"
    echo "  Wait 2-3 minutes and run this script again"
    echo ""
    echo "Option B - Manual setup (if launch template failed):"
    echo "  git clone [your-repository]"
    echo "  cd [repository-name]"
    echo "  ./.devcontainer/setup-ec2-host.sh"
fi
echo ""
