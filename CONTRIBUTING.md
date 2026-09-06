# Contributing to win32-vnc-k8s

Thank you for your interest in contributing to **win32-vnc-k8s**! We welcome bug reports, documentation improvements, and code contributions.

## Code of Conduct

All contributors and participants are expected to adhere to standard respectful, professional, and inclusive open-source community standards.

## How to Contribute

### 1. Reporting Bugs

* Check the existing GitHub Issues to see if the issue has already been reported.
* If not, open a new issue detailing:
  * A clear and descriptive title.
  * Reproduction steps.
  * Expected vs actual behavior.
  * Environment details (Docker version, Kubernetes/AKS version, base OS).

### 2. Suggesting Enhancements

* Open an issue labeled `enhancement` describing the proposed feature and why it would be beneficial for running legacy x86 Win32 applications in containers.

### 3. Submitting Pull Requests

1. Fork the repository on GitHub.
2. Clone your fork locally and create a feature branch:
   ```bash
   git checkout -b feature/my-feature-name
   ```
3. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```
4. Run the unit test suite and linters:
   ```bash
   pytest tests/
   flake8 orchestrator tests
   black --check orchestrator tests
   ```
5. Ensure all tests pass and your code conforms to PEP 8 standards.
6. Commit your changes with clear, semantic commit messages.
7. Push your branch to GitHub and open a Pull Request against `main`.

## Development Setup

The project requires Python 3.10+ for the orchestrator layer and Docker for building the container runtime.

```bash
# Clone the repository
git clone https://github.com/asyntec/win32-vnc-k8s.git
cd win32-vnc-k8s

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests
pytest
```
