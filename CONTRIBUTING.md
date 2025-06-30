# Contributing to AutOps

Thank you for your interest in contributing to AutOps! This document provides guidelines and instructions for contributing to the project.

## 🤝 How to Contribute

### Types of Contributions

We welcome several types of contributions:

- **🐛 Bug Reports**: Help us identify and fix issues
- **✨ Feature Requests**: Suggest new capabilities or improvements
- **📝 Documentation**: Improve our docs, examples, and guides
- **💻 Code Contributions**: Fix bugs, implement features, or improve performance
- **🧪 Testing**: Add test cases or improve test coverage
- **🔧 DevOps/Infrastructure**: Improve deployment, monitoring, or development workflows

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- Poetry for dependency management
- Docker and Docker Compose
- Git

### Development Setup

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/yourusername/autops.git
   cd autops
   ```
3. **Install development dependencies**:
   ```bash
   pip install poetry
   poetry install
   ```
4. **Set up pre-commit hooks**:
   ```bash
   poetry run pre-commit install
   ```
5. **Create a development environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your development settings
   ```

### Running the Development Environment

```bash
# Start the full stack
make run-docker

# Or run just the API for development
make run-dev

# Run tests
make test

# Run linting and formatting
make lint
make format
```

## 📝 Development Workflow

### Creating a New Feature

1. **Create a new branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following our coding standards

3. **Add tests** for your changes:
   ```bash
   # Add tests in tests/ directory
   # Run tests to ensure they pass
   make test
   ```

4. **Update documentation** if needed

5. **Commit your changes**:
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

6. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

7. **Create a Pull Request** on GitHub

### Commit Message Guidelines

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

Examples:
```
feat: add support for Azure DevOps integration
fix: resolve memory leak in agent execution
docs: update installation instructions
test: add integration tests for Slack webhook
```

## 🏗️ Architecture Guidelines

### Adding New Agents

To add a new agent to the system:

1. **Create the agent file** in `src/autops/agents/`:
   ```python
   # src/autops/agents/your_new_agent.py
   from ..utils.logging import get_logger
   from ..utils.exceptions import AgentExecutionError
   
   class YourNewAgent:
       def __init__(self):
           self.logger = get_logger(f"{__name__}.YourNewAgent")
       
       def execute(self, input_data):
           # Your agent logic here
           pass
   ```

2. **Add agent to the registry** in `src/autops/agents/__init__.py`

3. **Create tests** in `tests/agents/test_your_new_agent.py`

4. **Update documentation** in README.md

### Adding New Tool Integrations

To add a new external tool integration:

1. **Create the client** in `src/autops/tools/`:
   ```python
   # src/autops/tools/your_tool_client.py
   from ..config import get_settings
   from ..utils.logging import get_logger
   from ..utils.exceptions import YourToolAPIError
   
   class YourToolClient:
       def __init__(self):
           self.settings = get_settings()
           self.logger = get_logger(f"{__name__}.YourToolClient")
   ```

2. **Add configuration** in `src/autops/config.py`

3. **Register the tool** in `src/autops/tools/__init__.py`

4. **Add tests and documentation**

## 🧪 Testing Guidelines

### Test Structure

```
tests/
├── unit/           # Unit tests for individual components
├── integration/    # Integration tests with external services
├── agents/         # Agent-specific tests
├── api/           # API endpoint tests
└── conftest.py    # Pytest configuration and fixtures
```

### Writing Tests

- **Use descriptive test names**: `test_query_understanding_agent_handles_invalid_input`
- **Follow AAA pattern**: Arrange, Act, Assert
- **Mock external dependencies**: Use `pytest-mock` for external API calls
- **Test edge cases**: Invalid inputs, network failures, etc.

Example test:
```python
def test_github_client_handles_api_error(mock_github_api):
    mock_github_api.side_effect = requests.RequestException("API Error")
    
    client = GitHubClient()
    
    with pytest.raises(GitHubAPIError):
        client.get_latest_pipeline_status("test-repo")
```

### Running Tests

```bash
# Run all tests
make test

# Run specific test file
poetry run pytest tests/unit/test_github_client.py

# Run with coverage
make test-coverage

# Run integration tests (requires API keys)
make test-integration
```

## 📊 Code Quality Standards

### Code Style

- **Python**: Follow PEP 8, enforced by Black and Flake8
- **Type hints**: Use type hints for all function signatures
- **Docstrings**: Use Google-style docstrings for all public functions
- **Imports**: Use absolute imports, group by standard/third-party/local

### Performance Guidelines

- **Async/await**: Use async patterns for I/O operations
- **Caching**: Cache expensive operations appropriately
- **Resource cleanup**: Always clean up resources (use context managers)
- **Error handling**: Handle errors gracefully with proper logging

### Security Guidelines

- **Input validation**: Validate all user inputs
- **Secrets management**: Never commit secrets to code
- **Dependencies**: Keep dependencies updated
- **Logging**: Don't log sensitive information

## 🐛 Bug Reports

When reporting bugs, please include:

1. **Clear description** of the issue
2. **Steps to reproduce** the problem
3. **Expected vs actual behavior**
4. **Environment details**:
   - Python version
   - AutOps version
   - Operating system
   - Relevant configuration
5. **Error messages or logs** (sanitized of secrets)
6. **Screenshots** if applicable

Use our bug report template:

```markdown
## Bug Description
A clear description of what the bug is.

## Steps to Reproduce
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

## Expected Behavior
What you expected to happen.

## Actual Behavior
What actually happened.

## Environment
- OS: [e.g. Ubuntu 20.04]
- Python: [e.g. 3.9.7]
- AutOps: [e.g. 0.1.0]

## Additional Context
Any other context about the problem.
```

## ✨ Feature Requests

For feature requests, please:

1. **Check existing issues** to avoid duplicates
2. **Describe the problem** you're trying to solve
3. **Propose a solution** if you have one in mind
4. **Consider alternatives** you've thought about
5. **Provide use cases** and examples

## 📚 Documentation

### Documentation Standards

- **Clear and concise**: Write for your audience
- **Examples**: Include practical examples
- **Up-to-date**: Keep docs in sync with code changes
- **Accessible**: Use clear language and good formatting

### Types of Documentation

- **README**: Overview and quick start
- **API docs**: Auto-generated from docstrings
- **Tutorials**: Step-by-step guides
- **Reference**: Detailed technical documentation

## 🔍 Code Review Process

### Pull Request Guidelines

- **Small, focused PRs**: Easier to review and merge
- **Clear description**: Explain what and why
- **Link issues**: Reference related issues
- **Update docs**: Include documentation updates
- **Add tests**: Ensure good test coverage

### Review Criteria

Reviewers will check for:

- **Functionality**: Does it work as intended?
- **Code quality**: Is it readable and maintainable?
- **Performance**: Any performance implications?
- **Security**: Any security concerns?
- **Tests**: Adequate test coverage?
- **Documentation**: Is documentation updated?

## 🏷️ Release Process

### Versioning

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR**: Incompatible API changes
- **MINOR**: New functionality (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Checklist

- [ ] All tests pass
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Version bumped in pyproject.toml
- [ ] Tag created and pushed
- [ ] Release notes created

## 💬 Communication

### Getting Help

- **GitHub Discussions**: General questions and ideas
- **GitHub Issues**: Bug reports and feature requests
- **Discord**: Real-time chat (coming soon)

### Code of Conduct

We are committed to providing a welcoming and inclusive environment. Please:

- **Be respectful** and professional
- **Be constructive** in feedback
- **Be patient** with newcomers
- **Be collaborative** in spirit

## 🙏 Recognition

Contributors will be recognized in:

- **README.md**: Contributors section
- **Release notes**: Major contributions highlighted
- **GitHub**: Contributor graphs and statistics

Thank you for contributing to AutOps! 🚀 