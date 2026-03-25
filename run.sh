#!/usr/bin/env bash
set -euo pipefail

cd -- "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

port=8000
flask_args=()

while (($# > 0)); do
  case "$1" in
    -p|--port)
      if (($# < 2)); then
        echo "Missing value for $1" >&2
        exit 1
      fi
      port="$2"
      shift 2
      ;;
    --port=*)
      port="${1#*=}"
      shift
      ;;
    -h|--help)
      cat <<'EOF'
Usage: ./run.sh [-p PORT|--port PORT] [FLASK_RUN_ARGS...]

Starts the Flask app on 0.0.0.0. Default port: 8000.
Any extra arguments are forwarded to `flask run`.
EOF
      exit 0
      ;;
    --)
      shift
      flask_args+=("$@")
      break
      ;;
    *)
      flask_args+=("$1")
      shift
      ;;
  esac
done

exec uv run flask --app czech_vocab.web.app:create_app run --host 0.0.0.0 --port "$port" "${flask_args[@]}"
