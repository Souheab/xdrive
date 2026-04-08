# Top-level Makefile — delegates to docs/

.PHONY: html docs clean-docs

html docs:
	$(MAKE) -C docs html

clean-docs:
	$(MAKE) -C docs clean
