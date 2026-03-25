#!/usr/bin/env fish

cd (status dirname)

set port 8000
set flask_args

while test (count $argv) -gt 0
    switch $argv[1]
        case -p --port
            if test (count $argv) -lt 2
                echo "Missing value for $argv[1]" >&2
                exit 1
            end
            set port $argv[2]
            set -e argv[1..2]
        case '--port=*'
            set port (string replace -- '--port=' '' $argv[1])
            set -e argv[1]
        case -h --help
            echo "Usage: ./run.fish [-p PORT|--port PORT] [FLASK_RUN_ARGS...]"
            echo
            echo "Starts the Flask app on 0.0.0.0. Default port: 8000."
            echo "Any extra arguments are forwarded to \`flask run\`."
            exit 0
        case --
            set -e argv[1]
            set flask_args $argv
            break
        case '*'
            set flask_args $flask_args $argv[1]
            set -e argv[1]
    end
end

exec uv run flask --app czech_vocab.web.app:create_app run --host 0.0.0.0 --port $port $flask_args
