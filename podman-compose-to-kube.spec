%define name podman-compose-to-kube
Name: %name
Version: 1.0.0
Release: alt1
Summary:A set of scripts to support the migration of docker-compose solutions to kubernetes
BuildArch: noarch

License: GPL-2.0
Group: Development/Other
Url: https://github.com/alt-cloud/podman-compose-to-kube

Source: %name-%version.tar

Requires: podman >= 4.4.4
Requires: podman-compose >= 1.0.6-alt1
Requires: yq >= 3.2.2

%description
This software provides the migration of docker-compose solutions to kubernetes.
The script podman-compose-to-kube generates `kubernetes manifests` to deploy the specified service stack
in kubernetes.
The POD created by the podman-compose command is used as the basis for generation.

%prep
%setup -n %name-%version

%build
%make_build

%install
%makeinstall_std

%files
%doc LICENSE README.md
%_bindir/podman-compose-to-kube
%_mandir/man1/*
%_mandir/ru/man1/*

%changelog
* Sun Jan 28 2024 Alexey Kostarev <kaf@altlinux.org> 1.0.0-alt1
- 1.0.0



