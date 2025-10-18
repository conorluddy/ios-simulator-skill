# iOS Simulator Skill - Development Repository

This is the **development repository** for the iOS Simulator Skill. Users should download the packaged skill from [GitHub Releases](https://github.com/YOUR_USERNAME/ios-simulator-skill/releases).

## What is This?

A production-ready Claude Code skill providing 12 scripts for iOS simulator testing and automation with:
- 🏗️ **Ultra token-efficient build automation** with progressive disclosure
- 🔍 **Real-time log monitoring** with intelligent filtering
- 🎯 **Accessibility-driven navigation** (semantic, not pixel-based)
- ♿ **WCAG accessibility auditing**
- 📸 **Visual regression testing**
- 🎬 **Test recording and documentation**

**Total:** ~5,200 lines of production Python code

## For Users: Installation

Download the latest release and extract to your Claude skills directory:

```bash
# Download from releases
curl -L https://github.com/YOUR_USERNAME/ios-simulator-skill/releases/latest/download/ios-simulator-skill-v1.0.0.zip -o skill.zip

# Extract to Claude Code skills directory
unzip skill.zip -d ~/.claude/skills/ios-simulator-skill

# Restart Claude Code
```

See [`skill/README.md`](skill/README.md) for usage documentation.

## For Contributors: Development Setup

### Prerequisites

- macOS 11+ (required for iOS simulator)
- Xcode Command Line Tools: `xcode-select --install`
- Python 3.12+
- Git

### Setup

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/ios-simulator-skill.git
cd ios-simulator-skill

# Install development dependencies
pip3 install black ruff mypy pre-commit

# Install pre-commit hooks
pre-commit install

# Verify setup
pre-commit run --all-files
```

### Development Workflow

```bash
# Make changes to skill/scripts/
vim skill/scripts/build_and_test.py

# Hooks run automatically on commit (Black, Ruff, mypy)
git add skill/scripts/build_and_test.py
git commit -m "feat: improve build error reporting"

# Push and create PR
git push origin feature-branch
# Open PR on GitHub - lint workflow runs automatically
```

### Linting Tools

All code in `skill/scripts/` is checked with **STRICT** configuration:

- **Black** - Auto-formats to consistent style (line length: 100)
- **Ruff** - Fast linter catching bugs, style issues, unused imports
- **mypy** - Strict type checking (all type hints required)

Configuration in [`pyproject.toml`](pyproject.toml).

### Running Linters Manually

```bash
# Format code
black skill/scripts/

# Lint code (with auto-fix)
ruff check --fix skill/scripts/

# Type check
mypy skill/scripts/

# Or run all checks
pre-commit run --all-files
```

### Repository Structure

```
ios-simulator-skill/
├── skill/                      # 🎁 What users get (packaged in releases)
│   ├── SKILL.md               # Entry point with YAML frontmatter
│   ├── CLAUDE.md              # Developer guide for Claude
│   ├── README.md              # User-facing documentation
│   ├── scripts/               # 12 production scripts (~5,200 lines)
│   ├── references/            # Deep documentation
│   └── examples/              # Usage examples
│
├── .github/workflows/         # CI/CD automation
│   ├── release.yml           # Auto-package skill/ on release
│   ├── lint.yml              # Run linters on PRs
│   └── validate-version.yml  # Ensure version consistency
│
├── pyproject.toml             # Linting configuration
├── .pre-commit-config.yaml    # Git hooks
└── README.md                  # This file (dev guide)
```

### Creating a Release

```bash
# 1. Update version in pyproject.toml
vim pyproject.toml  # Update version = "1.1.0"

# 2. Commit version bump
git add pyproject.toml
git commit -m "chore: bump version to 1.1.0"
git push origin main

# 3. Create and push tag
git tag v1.1.0
git push origin v1.1.0

# 4. Create GitHub release
# Go to: https://github.com/YOUR_USERNAME/ios-simulator-skill/releases/new
# - Tag: v1.1.0
# - Title: "Release v1.1.0"
# - Description: (auto-generated or write your own)
# - Publish release

# 5. GitHub Actions automatically:
#    - Validates version consistency
#    - Packages skill/ directory
#    - Attaches ios-simulator-skill-v1.1.0.zip to release
```

### Testing

```bash
# Test scripts locally with booted simulator
open -a Simulator

# Run health check
bash skill/scripts/sim_health_check.sh

# Test individual scripts
python skill/scripts/build_and_test.py --help
python skill/scripts/screen_mapper.py

# Test skill installation
mkdir -p ~/.claude/skills/ios-simulator-skill-test
cp -r skill/* ~/.claude/skills/ios-simulator-skill-test/
# Restart Claude Code and verify
```

## Code Style Guidelines

From [`CLAUDE.md`](skill/CLAUDE.md):

- **Jackson's Law**: Minimal code to solve the problem
- **Guard clauses**: Validate inputs first, happy path last
- **Functions < 50 lines**: Keep functions focused
- **Files < 300 lines**: Keep modules understandable
- **Actionable errors**: Always explain what failed and how to fix
- **Type hints**: All functions use type annotations (enforced by mypy --strict)
- **Security**: Never `shell=True`, always validate paths

## GitHub Actions Workflows

### release.yml
- **Trigger:** When release is published
- **Actions:** Validate structure → Zip skill/ → Upload to release

### lint.yml
- **Trigger:** On PR to main (for Python files)
- **Actions:** Run Black, Ruff, mypy → Block merge if fails

### validate-version.yml
- **Trigger:** On release published
- **Actions:** Check pyproject.toml version matches git tag

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make changes (hooks will run on commit)
4. Push and create a PR
5. Wait for lint workflow to pass
6. Request review

## License

MIT License - see [LICENSE.md](LICENSE.md)

## Questions?

- **Usage questions**: See [skill/README.md](skill/README.md)
- **Bug reports**: [Open an issue](https://github.com/YOUR_USERNAME/ios-simulator-skill/issues)
- **Development questions**: [Open a discussion](https://github.com/YOUR_USERNAME/ios-simulator-skill/discussions)
