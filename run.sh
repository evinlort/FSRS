#!/usr/bin/env bash
set -euo pipefail

cd -- "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

exec uv run flask --app czech_vocab.web.app:create_app run --host 0.0.0.0 --port 8000
