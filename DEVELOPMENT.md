
# Development Guide

Thank you for your interest in developing The Last Yes.

This guide explains how to set up the project locally and run its available checks.

## Requirements

- Python 3
- pip
- Git

## Getting the project

Clone the repository:

```bash
git clone https://github.com/JayPlange/the-last-yes-.git
cd the-last-yes-
```

## Setting up the environment

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```powershell
.venv\Scripts\Activate.ps1
```

Or on macOS/Linux:

```bash
source .venv/bin/activate
```

Install the development dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

## Running the tests

Run the test suite:

```bash
python -m pytest -q
```

Run the reference validation:

```bash
python validate_reference.py
```

## Running evaluations

Refer to the README for the evaluation workflow and available configuration options.

Some evaluation runs may require provider credentials or external API access. Never commit API keys, passwords, tokens or other secrets to the repository.

Use `.env.example` as a configuration reference where applicable.

## Contributing

- Keep changes focused and explain their purpose.
- Add or update tests when changing behaviour.
- Run the available checks before submitting changes.
- Do not publish private credentials, confidential data or materials you do not have permission to redistribute.

## Reporting issues

When reporting an issue, include the steps to reproduce it, the expected behaviour and the actual behaviour. Remove secrets and sensitive information from logs before sharing them.
