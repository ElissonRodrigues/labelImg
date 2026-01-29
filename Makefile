# Makefile for labelImg (PyQt6 version)

all: test

test:
	python3 -m unittest discover tests

# Resources are now pre-compiled or managed by the app
resources:
	# pyside6-rcc -o libs/resources.py resources.qrc
	echo "Resources should be updated to PyQt6 manually or via tools."

clean:
	rm -rf ~/.labelImgSettings.pkl *.pyc dist labelImg.egg-info __pycache__ build

.PHONY: all test resources clean
