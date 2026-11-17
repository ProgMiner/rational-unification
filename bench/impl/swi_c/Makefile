CC ?= cc
CFLAGS ?= -O3 -Wall -Wextra
PKG_CONFIG ?= pkg-config

SWIPL_CFLAGS := $(shell $(PKG_CONFIG) --cflags swipl)
SWIPL_LIBS := $(shell $(PKG_CONFIG) --libs swipl)
SWIPL_LIBDIR := $(shell $(PKG_CONFIG) --variable=libdir swipl)

.PHONY: all clean check

all: swi

swi: swi.c
	$(CC) $(CFLAGS) $(SWIPL_CFLAGS) $< $(SWIPL_LIBS) -Wl,-rpath,$(SWIPL_LIBDIR) -o $@

clean:
	rm -f swi
