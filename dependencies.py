'''
Copyright (C) 2023 Orange Turbine
https://orangeturbine.com
orangeturbine@cgcookie.com

Created by Jason van Gumster

    This file is part of an Install Dependencies Example.

    This example is free software; you can redistribute it and/or
    modify it under the terms of the GNU General Public License
    as published by the Free Software Foundation; either version 3
    of the License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, see <https://www.gnu.org/licenses/>.

'''

import os
import pkg_resources
import subprocess
import sys
from pathlib import Path


add_on_path = Path(__file__).parent                     # assuming this file is at root of add-on
os.environ["ADDON_PATH"] = str(add_on_path)
requirements_txt = add_on_path / 'requirements.txt'     # assuming requirements.txt is at root of add-on
requirements_for_check_txt = add_on_path / 'requirements_for_check.txt'     # assuming requirements.txt is at root of add-on

deps_path = add_on_path / 'deps_public'                 # might not exist until install_deps is called

# Append dependencies folder to system path so we can import
# (important for Windows machines, but less so for Linux)
sys.path.append(os.fspath(deps_path))



class Dependencies:
    # cache variables used to eliminate unnecessary computations
    _checked = None
    _requirements = None

    @staticmethod
    def install():
        if Dependencies.check():
            return True

        # Create folder into which pip will install dependencies
        try:
            deps_path.mkdir(exist_ok=True)
        except Exception as e:
            print(f'Caught Exception while trying to create dependencies folder')
            print(f'  Exception: {e}')
            print(f'  Folder: {deps_path}')
            return False

        # Ensure pip is installed
        try:
            subprocess.check_call([sys.executable, "-m", "ensurepip", "--upgrade"])
        except subprocess.CalledProcessError as e:
            print(f'Caught CalledProcessError while trying to ensure pip is installed')
            print(f'  Exception: {e}')
            print(f'  {sys.executable=}')
            return False

        # Install dependencies from requirements.txt
        try:
            cmd = [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-r",
                os.fspath(requirements_txt),
                "--target",
                os.fspath(deps_path)
            ]
            print(f'Installing: {cmd}')
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError as e:
            print(f'Caught CalledProcessError while trying to install dependencies')
            print(f'  Exception: {e}')
            print(f'  Requirements: {requirements_txt}')
            print(f'  Folder: {deps_path}')
            return False

        return Dependencies.check(force=True)

    @staticmethod
    def check(*, force=False):
        if force:
            Dependencies._checked = None
        elif Dependencies._checked is not None:
            # Assume everything is installed
            return Dependencies._checked

        Dependencies._checked = False

        if deps_path.exists():
            try:
                # Ensure all required dependencies are installed in dependencies folder
                ws = pkg_resources.WorkingSet(entries=[ os.fspath(deps_path) ])
                for dep in Dependencies.requirements(force=force):
                    ws.require(dep)

                # If we get here, we found all required dependencies
                Dependencies._checked = True

            except Exception as e:
                print(f'Caught Exception while trying to check dependencies')
                print(f'  Exception: {e}')
                Dependencies._checked = False

        return Dependencies._checked

    @staticmethod
    def requirements(*, force=False):
        if force:
            Dependencies._requirements = None
        elif Dependencies._requirements is not None:
            return Dependencies._requirements

        # load and cache requirements
        with requirements_for_check_txt.open() as requirements:
            dependencies = pkg_resources.parse_requirements(requirements)
            Dependencies._requirements = [ dep.project_name for dep in dependencies ]
        return Dependencies._requirements
