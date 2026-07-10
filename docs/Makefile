# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = source
BUILDDIR      = build

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile

PACKAGES = $(wildcard ../packages/*/src/*)

apidoc:
	rm -f source/reference/*
	$(foreach pkg,$(PACKAGES),\
		sphinx-apidoc -d 1 -t source/_templates/ -o source/reference/ $(pkg) &&) true
	printf "API Reference\n=============\n\n.. toctree::\n   :maxdepth: 1\n\n" > source/reference/modules.rst
	$(foreach pkg,$(PACKAGES),echo "   $(notdir $(pkg))" >> source/reference/modules.rst;)

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).-
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
