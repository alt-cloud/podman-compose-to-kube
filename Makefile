
# Copyright (C) 2022  Alexey Kostarev <kaf@altlinux.org>
#
# Makefile for the podman-compose.
#
# This file is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA.

DESTDIR =
prefix ?= /usr
sysconfdir ?= /etc
bindir ?= $(prefix)/bin
datadir ?= $(prefix)/share
mandir ?= $(datadir)/man
man1dir ?= $(mandir)/man1
man1dirru ?= $(mandir)/ru/man1

MKDIR_P = mkdir -p

.PHONY:	all install clean

all:

install: all
	$(MKDIR_P) -m755 $(DESTDIR)$(bindir)
	$(MKDIR_P) -m755 $(DESTDIR)$(man1dir)
	$(MKDIR_P) -m755 $(DESTDIR)$(man1dirru)
	cd ./bin;$(INSTALL) -m755 podman-compose-to-kube $(DESTDIR)$(bindir)/
	cd ./man;$(INSTALL) -m644 podman-compose-to-kube_en.1 $(DESTDIR)$(man1dir)/podman-compose-to-kube.1
	cd ./man;$(INSTALL) -m644 podman-compose-to-kube_ru.1 $(DESTDIR)$(man1dirru)/podman-compose-to-kube.1

