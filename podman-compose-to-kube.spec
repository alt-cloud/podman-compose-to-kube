%define name podman-compose-to-kube
Name: %name
Version: 2.0.0
Release: alt1
Summary: An implementation of Docker Compose Spec with Podman backend
BuildArch: noarch

License: GPL-2.0-only
Group: Development/Python3
Url: https://github.com/containers/podman-compose

Source: %name-%version.tar

BuildRequires: rpm-build-python3

Requires: podman-compose >= 1.0.6

%description
The script podman-compose-to-kube generates kubernetes manifests to deploy
the specified service stack in kubernetes.
The POD created by the podman-compose command is used as the basis for generation.

%prep
%setup -n %name-%version

%build
%python3_build

%install
%python3_install

%files
%doc LICENSE README.md
%_bindir/%name
%python3_sitelibdir/*

%changelog
* Tue Feb 20 2024 Alexey Kostarev <kaf@altlinux.org> 2.0.0-alt1
- 2.0.0




