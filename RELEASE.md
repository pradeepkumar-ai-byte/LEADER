# How to Release Leader

This document describes the steps for releasing a new version of Leader to PyPI and GitHub.

## 1. Versioning Rules

Leader follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html):
- **PATCH** (`0.1.x`): Bug fixes, dependency updates, documentation improvements.
- **MINOR** (`0.x.0`): New adapters, new plugins, backward-compatible features.
- **MAJOR** (`x.0.0`): Backward-incompatible changes (e.g. database schema change without migration, removing supported platforms).

---

## 2. Release Steps

### Step 1: Update Files and Version
1. Update version string in `leader/__init__.py` (`__version__ = "X.Y.Z"`).
2. Update version string in `pyproject.toml` (`version = "X.Y.Z"`).
3. Update `CHANGELOG.md` to document the new release under the release version and date.

### Step 2: Run Tests and Linters
Ensure everything is fully functional:
```bash
# Run pytest
pytest leader/test_leader.py -v
pytest leader/test_integration.py -v

# Run formatters/linters
black --check leader/
ruff check leader/
```

### Step 3: Build the Distribution Packages
Clean previous build artifacts and build source and wheel archives:
```bash
# Remove old builds
rm -rf build/ dist/ *.egg-info

# Build new packages
python -m build
```
Verify that the `dist/` directory contains both a `.tar.gz` (source) and a `.whl` (wheel) file.

### Step 4: Publish to PyPI
First upload to TestPyPI to ensure packaging is correct, then to PyPI:

```bash
# Test PyPI upload
python -m twine upload --repository testpypi dist/*

# Verify TestPyPI installation
pip install --index-url https://test.pypi.org/simple/ leader-agent

# Production PyPI upload
python -m twine upload dist/*
```

### Step 5: Tag and Release on GitHub
Tag the release and push it:
```bash
git add .
git commit -m "Release vX.Y.Z"
git tag -a vX.Y.Z -m "Leader Release vX.Y.Z"
git push origin main --tags
```

Go to [GitHub Releases](https://github.com/pradeepkumar-ai-byte/LEADER/releases) and create a release pointing to the tagged version. Copy the corresponding entry from `CHANGELOG.md` into the release notes.
