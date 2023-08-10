.PHONY:

.venv/touchfile: requirements.txt
 	ifeq (, $(shell which virtualenv))
 		$(error "Could not find virtualenv, consider doing `pip install virtualenv`")
 	endif	
	test -d .venv || virtualenv .venv
	. .venv/bin/activate ; pip install -Ur requirements.txt
	touch .venv/touchfile

freeze: .venv/touchfile
	set -e ; . .venv/bin/activate ; pip freeze
	
docker-build: .venv/touchfile server.py Dockerfile
	./build.sh

docker-publish: .venv/touchfile server.py Dockerfile
	./build.sh --push

run: .venv/touchfile
	set -e ; . .venv/bin/activate ; python server.py

clean:
	rm -rf .venv build dist *.egg-info .pytest-cache
	find -iname "*.pyc" -delete
	find -iname "__pycache__" -delete

