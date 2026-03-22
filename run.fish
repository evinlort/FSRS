#!/usr/bin/env fish

cd (status dirname)

exec uv run flask --app czech_vocab.web.app:create_app run --host 0.0.0.0 --port 8000
