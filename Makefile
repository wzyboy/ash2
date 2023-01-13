.PHONY: dev-server

dev-server:
	FLASK_APP=ash.py FLASK_DEBUG=true TEMPLATES_AUTO_RELOAD=True flask run
