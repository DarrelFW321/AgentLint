# Releasing AgentLint

AgentLint publishes the `agentlint-trace` distribution from tagged commits through
PyPI Trusted Publishing.

## One-time setup

Create a PyPI trusted publisher with:

- PyPI project: `agentlint-trace`
- GitHub owner: `DarrelFW321`
- GitHub repository: `AgentLint`
- Workflow: `release.yml`
- Environment: `pypi`

Create the matching protected `pypi` environment in the GitHub repository. No PyPI
API token is stored in GitHub.

## Release

1. Update `src/agentlint/version.py` and `CHANGELOG.md`.
2. Run `python -m pytest -q`.
3. Run `python -m build` and `python -m twine check dist/*`.
4. Run `python scripts/test_wheel.py dist/*.whl`.
5. Merge the release commit after CI passes.
6. Create and push a matching tag, such as `v0.1.0a1`.
7. Approve the `pypi` environment deployment when required.
8. Verify installation from PyPI in a new virtual environment.
9. Create a GitHub pre-release using the changelog entry.

The release workflow rejects tags that do not match the package version. It builds
the distributions once, tests those exact artifacts, and publishes them only after
all supported-runtime jobs pass.

## Faulty release

Published files cannot be replaced. If a release is broken:

1. Yank it on PyPI so new dependency resolution avoids it.
2. Add the failure to the changelog and a regression test when applicable.
3. Increment the version, publish a corrected release, and point users to it.

Do not delete a release merely to reuse its version; package indexes and installer
caches may retain the original files.
