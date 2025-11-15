PYTHON ?= python

help:
	@echo "make run TX=0x... RPC=https://..."
	@echo "make lint"

run:
	$(PYTHON) txfeeapp.py $(TX) --rpc $(RPC)

lint:
	$(PYTHON) -m compileall txfeeapp.py
