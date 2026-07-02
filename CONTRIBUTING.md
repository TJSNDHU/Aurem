# Contributing

Thanks for your interest in contributing! This document explains how to get
started and what we expect from contributions.

## Project Overview

This repository provides the backend service for the project. The codebase is
organized around a central router that maps API endpoints to handler modules.
Each handler is responsible for validating input, interacting with services or
data layers, and returning a consistent response shape. When adding new
endpoints, follow the existing router registration pattern so that routing,
middleware, and error handling remain uniform.

## Development Setup

1. **Fork and clone** the repository.
2. **Install dependencies** using the project's standard package manager.
3. **Copy the example environment file** (e.g. `.env.example`) to `.env` and
   fill in any required local values. Never commit real secrets.
4. **Run the service locally** and confirm it starts without errors.
5. **Run the test suite** to make sure your environment is healthy before
   making changes.

## Branch and Pull Request Conventions

- Branch from `main` (or the default branch) and name branches descriptively,
  for example `feature/add-user-endpoint` or `fix/router-404`.
- Keep pull requests focused: one logical change per PR.
- Open a PR against the default branch and fill out the PR template.
- Request review from at least one maintainer.
- Address review feedback with new commits rather than force-pushing once
  reviewers have commented, unless asked otherwise.
- Delete your branch after merge.

## Code Style

- Follow the existing formatting and naming conventions in the repository.
- Prefer small, focused functions and modules.
- Keep handlers thin: validate input, delegate to services, return responses.
- Add or update types/interfaces where applicable.
- Avoid commented-out code and debug logs in committed code.
- Do not introduce new dependencies without justification.
- Never hardcode secrets, tokens, or credentials. Use environment variables or
  a secrets manager.

## Testing

- Add or update tests for any change to behavior.
- Ensure the full test suite passes before requesting review.
- Cover both success and error paths where practical.
- If a bug fix is involved, add a regression test that fails before the fix
  and passes afterward.
- Run linters and formatters as part of your local checks.

## Reporting Issues

- Search existing issues before opening a new one.
- Include steps to reproduce, expected vs. actual behavior, and environment
  details (OS, runtime version, relevant config).

## Code of Conduct

Be respectful and constructive in all interactions. Harassment or
disrespectful behavior will not be tolerated.

By contributing, you agree that your contributions will be licensed under the
same license as the project.

Thank you for helping improve this project!