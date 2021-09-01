all: install

DIR=/usr/local/bin/

SERVER=nsm-server.py
SERVER_TARGET=$(DIR)5FX-Server

install:
	cp nsmclient.py jack-patch.py $(DIR)
	cp $(SERVER) $(SERVER_TARGET)

uninstall:
	rm $(SERVER_TARGET)