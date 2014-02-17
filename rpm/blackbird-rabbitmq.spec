%define _unpackaged_files_terminate_build 0
%define name blackbird-rabbitmq
%define version 0.1.4
%define unmangled_version 0.1.4
%define release 1

%define blackbird_conf_dir /etc/blackbird/conf.d

Summary: Get monitorring stats of rabbitmq for blackbird
Name: %{name}
Version: %{version}
Release: %{release}%{?dist}
Source0: %{name}-%{unmangled_version}.tar.gz
License: UNKNOWN
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
BuildArch: noarch
Vendor: makocchi <makocchi@gmail.com>
Packager: makocchi <makocchi@gmail.com>
Requires:  blackbird
Requires:  python-requests
Url: https://github.com/Vagrants/blackbird-rabbitmq
BuildRequires:  python-devel

%description
Project Info
============

* Project Page: https://github.com/Vagrants/blackbird-rabbitmq


%prep
%setup -n %{name}-%{unmangled_version} -n %{name}-%{unmangled_version}

%build
python setup.py build

%install
python setup.py install --skip-build --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES
mkdir -p $RPM_BUILD_ROOT/%{blackbird_conf_dir}
cp -p rabbitmq.cfg $RPM_BUILD_ROOT/%{blackbird_conf_dir}/rabbitmq.cfg

%clean
rm -rf $RPM_BUILD_ROOT

%files -f INSTALLED_FILES
%defattr(-,root,root)

%changelog
* Mon Feb 17 2014 makochi <makocchi@gmail.com> - 0.1.4
- version up to 0.1.4
- add ping item

* Wed Jan  8 2014 makochi <makocchi@gmail.com> - 0.1.3
- version up to 0.1.3
- add Requires python-requests

* Wed Jan  8 2014 makochi <makocchi@gmail.com> - 0.1.2
- version up to 0.1.2

* Fri Nov 13 2013 makochi <makocchi@gmail.com> - 0.1.1
- add rabbitmq.cfg

* Thu Nov 12 2013 makochi <makocchi@gmail.com> - 0.1.0
- first package
