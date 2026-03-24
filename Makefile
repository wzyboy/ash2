.PHONY: dev-server

dev-server:
	uv run env FLASK_APP=ash FLASK_DEBUG=true TEMPLATES_AUTO_RELOAD=True flask run --port 3026
