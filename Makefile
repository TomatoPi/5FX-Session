all: install

DIR=/usr/local/bin/

SERVER=nsm-server.py
SERVER_TARGET=$(DIR)5FX-Server

install:
	cp nsmclient.py jack-patch.py $(DIR)
	cp nsm-jack-patch.py 5FX-Patcher
	cp $(SERVER) $(SERVER_TARGET)

uninstall:
	rm $(SERVER_TARGET)