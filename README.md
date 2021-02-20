# ROCKSEED RS310P PSU control
This provides a command line tool written in python to control the
ETommens eTM-xxxxP Series PSU. Several Mfg's use this supply,
Hanmatek HM305P, Rockseed RS305P, Hanmatek HM310P, RockSeed RS310P,
Rockseed RS605P.


# Installation

## Building debian package
pipenv2deb must be installed in order to build this package. See https://github.com/pjaos/pipenv2deb for details.

```
sudo pipenv2deb
INFO:  Set executable attribute: create_pip_env.sh
INFO:  Created build/DEBIAN
INFO:  Created build/usr/local/bin/python-rs3psu.pipenvpkg
INFO:  Copied Pipfile to build/usr/local/bin/python-rs3psu.pipenvpkg
INFO:  Copied Pipfile.lock to build/usr/local/bin/python-rs3psu.pipenvpkg
INFO:  Set executable attribute: build/usr/local/bin/python-rs3psu.pipenvpkg/create_pip_env.sh
INFO:  Copied /scratch/git_repos/python3/rs310p_dc_psu/psu.py to build/usr/local/bin/python-rs3psu.pipenvpkg
INFO:  Creating build/DEBIAN/postinst
INFO:  Set executable attribute: build/DEBIAN/postinst
INFO:  Set executable attribute: build/DEBIAN/control
INFO:  Set executable attribute: build/DEBIAN/postinst
INFO:  Created: build/usr/local/bin/psu
INFO:  Set executable attribute: build/usr/local/bin/psu
INFO:  Executing: dpkg-deb -Zgzip -b build packages/python-rs3psu-1.0-all.deb
dpkg-deb: building package 'python-rs3psu' in 'packages/python-rs3psu-1.0-all.deb'.
INFO:  Removed build path
```

Once built the package maybe installed using.

```
sudo dpkg -i packages/python-rs3psu-1.0-all.deb
(Reading database ... 410568 files and directories currently installed.)
Preparing to unpack .../python-rs3psu-1.0-all.deb ...
Unpacking python-rs3psu (1.0) over (1.0) ...
Setting up python-rs3psu (1.0) ...
Virtualenv already exists!
Removing existing virtualenv…
Creating a virtualenv for this project…
Using /usr/bin/python3 (3.8.5) to create virtualenv…
⠋created virtual environment CPython3.8.5.final.0-64 in 213ms
  creator CPython3Posix(dest=/usr/local/bin/python-rs3psu.pipenvpkg/.venv, clear=False, global=False)
  seeder FromAppData(download=False, progress=latest, setuptools=latest, html5lib=latest, ipaddr=latest, pep517=latest, idna=latest, retrying=latest, webencodings=latest, CacheControl=latest, pytoml=latest, distlib=latest, chardet=latest, packaging=latest, contextlib2=latest, urllib3=latest, pip=latest, pyparsing=latest, six=latest, colorama=latest, certifi=latest, appdirs=latest, pkg_resources=latest, wheel=latest, requests=latest, distro=latest, msgpack=latest, lockfile=latest, via=copy, app_data_dir=/root/.local/share/virtualenv/seed-app-data/v1.0.1.debian)
  activators BashActivator,CShellActivator,FishActivator,PowerShellActivator,PythonActivator,XonshActivator

Virtualenv location: /usr/local/bin/python-rs3psu.pipenvpkg/.venv
Installing dependencies from Pipfile.lock (05aef1)…
  🐍   ▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉ 3/3 — 00:00:01
To activate this project's virtualenv, run the following:
 $ pipenv shell
************************************
* The psu command is now available *
* 'psu -h' for command line help   *
************************************
```

#Running the psu command

The psu command has command line help as shown below

```
psu -h
Usage: Provide a control interface to the ROCKSEED RS310P/RS305P Bench PSU.

Options:
  -h, --help  show this help message and exit
  --debug     Enable debugging.
  -p P        Serial port (default=/dev/ttyUSB0).
  -v V        The required output voltage.
  -a A        The current limit value in amps.
  -s          The PSU status showing output state, voltage, current and power
              out.
  --vs        The verbose PSU status.
  --ov=OV     The required over voltage protection value in volts
  --oa=OA     The required over current protection value in amps.
  --op=OP     The required over power protection value in watts.
  --on        Turn the PSU output on.
  --off       Turn the PSU output off.
  --bon       Set the buzzer on.
  --boff      Set the buzzer off.
```

Below is an example of PSU control

```
psu -s
INFO:  Output:                 OFF
INFO:  Voltage (volts):        1.00
INFO:  Output voltage (volts): 0.00
INFO:  Current (amps):         0.000
INFO:  Watts (watts):          0.000

psu -s
INFO:  Output:                 OFF
INFO:  Voltage (volts):        1.00
INFO:  Output voltage (volts): 0.00
INFO:  Current (amps):         0.000
INFO:  Watts (watts):          0.000

psu -v 10
INFO:  Set output to 10.00 Volts

psu --on
INFO:  Set output ON

psu -s
INFO:  Output:                 ON
INFO:  Voltage (volts):        10.00
INFO:  Output voltage (volts): 10.00
INFO:  Current (amps):         1.622
INFO:  Watts (watts):          16.220
```
