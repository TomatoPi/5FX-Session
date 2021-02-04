all: install

DIR=/usr/local/bin/

SERVER=nsm-server.py
SERVER_TARGET=$(DIR)5FX-Server

install:
	cp $(SERVER) $(SERVER_TARGET)

uninstall:
	rm $(SERVER_TARGET)