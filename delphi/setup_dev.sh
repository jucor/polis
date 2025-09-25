#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Setting up Delphi development environment...${NC}"

# Check if Python 3.9+ is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not installed.${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
if ! python3 -c 'import sys; exit(0 if sys.version_info >= (3, 9) else 1)'; then
    echo -e "${RED}Error: Python 3.9+ is required, but found Python ${PYTHON_VERSION}${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python ${PYTHON_VERSION} found${NC}"

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo -e "${YELLOW}Warning: Not in a virtual environment. Creating one...${NC}"
    python3 -m venv delphi-dev-env
    source delphi-dev-env/bin/activate
    echo -e "${GREEN}✓ Virtual environment created and activated${NC}"
else
    echo -e "${GREEN}✓ Virtual environment detected: $VIRTUAL_ENV${NC}"
fi

# Upgrade pip
echo -e "${YELLOW}Upgrading pip...${NC}"
python -m pip install --upgrade pip

# Install the package in development mode with all dependencies
echo -e "${YELLOW}Installing Delphi package with development dependencies...${NC}"
pip install -e ".[dev,notebook]"

# Set up pre-commit hooks
echo -e "${YELLOW}Setting up pre-commit hooks...${NC}"
pre-commit install

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file from example.env...${NC}"
    cp example.env .env
    echo -e "${GREEN}✓ Created .env file. Please review and update with your specific configuration.${NC}"
else
    echo -e "${GREEN}✓ .env file already exists${NC}"
fi

# Check if Docker is available for local development
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✓ Docker detected${NC}"
    if command -v docker-compose &> /dev/null; then
        echo -e "${GREEN}✓ Docker Compose detected${NC}"
        echo -e "${YELLOW}You can now run 'docker-compose up -d' to start local services${NC}"
    else
        echo -e "${YELLOW}Warning: Docker Compose not found. You may need to install it for full local development.${NC}"
    fi
else
    echo -e "${YELLOW}Warning: Docker not found. Some features may require Docker for local development.${NC}"
fi

# Run initial quality checks
echo -e "${YELLOW}Running initial code quality checks...${NC}"
echo -e "${GREEN}Running ruff...${NC}"
if ruff check . --fix; then
    echo -e "${GREEN}✓ Ruff check passed${NC}"
else
    echo -e "${YELLOW}⚠ Ruff found issues but they may be fixable${NC}"
fi

echo -e "${GREEN}Running black...${NC}"
if black --check .; then
    echo -e "${GREEN}✓ Black formatting check passed${NC}"
else
    echo -e "${YELLOW}⚠ Code formatting issues found. Run 'make format' to fix${NC}"
fi

# Run a simple test to verify setup
echo -e "${YELLOW}Running a simple test to verify setup...${NC}"
if python -c "import polismath; print('✓ polismath package imports successfully')"; then
    echo -e "${GREEN}✓ Package import test passed${NC}"
else
    echo -e "${RED}✗ Package import test failed${NC}"
fi

echo -e "${GREEN}"
echo "=============================================="
echo "🎉 Development environment setup complete! 🎉"
echo "=============================================="
echo -e "${NC}"

echo "Next steps:"
echo "1. Review and update your .env file with proper configuration"
echo "2. Start local services: docker-compose up -d"
echo "3. Create DynamoDB tables: make setup-dynamodb"
echo "4. Run tests: make test"
echo "5. Check available commands: make help"
echo ""
echo "For more information, see:"
echo "- README.md for project overview"
echo "- CLAUDE.md for detailed documentation"
echo "- docs/ directory for specific topics"

if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo ""
    echo -e "${YELLOW}Remember to activate your virtual environment:${NC}"
    echo "source delphi-dev-env/bin/activate"
fi
