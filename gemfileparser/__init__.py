#!/usr/bin/env python
#
# Copyright 2015 Balasankar C <balasankarc@autistici.org>
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# .
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# .
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

'''Python library to parse Ruby's Gemfiles and gemspec files.'''

import csv
import io
import re
import os
import glob
import collections


class GemfileParser(object):

    '''Creates a GemfileParser object to perform operations. '''

    class Dependency(object):

        ''' A class to hold information about a dependency gem.'''

        def __init__(self):
            self.name = None
            self.requirement = []
            self.autorequire = None
            self.source = None
            self.parent = []
            self.group = None
            self.platform = None
            self.platforms = []
            self.groups = []

        def __str__(self):
            attributes = self.__dict__
            output = {}
            for key, value in attributes.items():
                if value is None or value == []:
                    next
                else:
                    output[key] = value
            return str(output)

    gemfile_regexes = collections.OrderedDict()
    gemfile_regexes['name'] = re.compile(r"gem ['\"](?P<name>.*?)['\"]")
    gemfile_regexes['source'] = re.compile(
        r".*source(:|[ ]?=>)[ ]*['\"](?P<source>[a-zA-Z:\/\.-\\]+)['\"].*")
    gemfile_regexes['git'] = re.compile(
        r".*git(:|[ ]?=>)[ ]*(?P<git>[a-zA-Z:\/\.-]+).*")
    gemfile_regexes['platform'] = re.compile(
        r".*platform(:|[ ]?=>)[ ]*(?P<platform>[a-zA-Z:\/\.-]+).*")
    gemfile_regexes['platforms'] = re.compile(
        r".*platforms(:|[ ]?=>)[ ]*(?P<platforms>\[.*\])[,]?.*")
    gemfile_regexes['path'] = re.compile(
        r".*path(:|[ ]?=>)[ ]*(?P<path>.+['\"\)]).*")
    gemfile_regexes['github'] = re.compile(
        r".*github(:|[ ]?=>)[ ]*[\'\"](?P<github>[a-zA-Z:\/\.-0-9]+)[\'\"].*")
    gemfile_regexes['branch'] = re.compile(
        r".*branch(:|[ ]?=>)[ ]*(?P<branch>[a-zA-Z:\/\.-]+).*")
    gemfile_regexes['autorequire'] = re.compile(
        r".*require(:|[ ]?=>)[ ]*(?P<autorequire>[a-zA-Z:\/\.-]+).*")
    gemfile_regexes['group'] = re.compile(
        r".*group(:|[ ]?=>)[ ]*(?P<group>[a-zA-Z:\/\.-]+).*")
    gemfile_regexes['groups'] = re.compile(
        r".*groups(:|[ ]?=>)[ ]*(?P<groups>\[.*\]),.*")
    gemfile_regexes['requirement'] = re.compile(
        r"gem[ ]['\"].*?['\"](?P<requirement>([>|<|=|~>|\d]+[ ]*[0-9\.\w]+[ ,]*)+).*")
    global_group = 'runtime'
    group_block_regex = re.compile(
        r".*group[ ]?(:|[ ]?=>)[ ]*(?P<groupblock>.*?) do")
    add_dvtdep_regex = re.compile(
        r".*add_development_dependency (?P<line>.*)")
    add_rundep_regex = re.compile(
        r".*add_runtime_dependency (?P<line>.*)")

    def __init__(self, filepath, appname=''):
        self.filepath = filepath    # Required when calls to gemspec occurs
        self.gemfile = open(filepath)
        self.appname = appname
        self.dependencies = {
            'development': [],
            'runtime': [],
            'test': [],
            'production': [],
            'metrics': []
        }
        self.contents = self.gemfile.readlines()
        if filepath.endswith('gemspec'):
            self.gemspec = True
        else:
            self.gemspec = False

    @staticmethod
    def preprocess(line):
        '''Removes the comment portion and excess spaces.'''

        if "#" in line:
            line = line[:line.index('#')]
        line = line.strip()
        return line

    def parse_line(self, line):
        '''Parses each line and creates dependency objects accordingly'''

        try:

            # StringIO requires a unicode object.
            # But unicode() doesn't work with Python3
            # as it is already in unicode format.
            # So, first try converting and if that fails, use original.

            line = unicode(line)
        except NameError:
            pass
        dep = self.Dependency()
        dep.group = GemfileParser.global_group
        if not self.appname:
            dep.parent = []
        else:
            dep.parent.append(self.appname)
        # Check for a match in each regex and assign to
        # corresponding variables
        for criteria in GemfileParser.gemfile_regexes:
            criteria_regex = GemfileParser.gemfile_regexes[criteria]
            match = criteria_regex.match(line)
            if match:
                if criteria == 'requirement':
                    dep.requirement.append(match.group(criteria))
                else:
                    setattr(dep, criteria, match.group(criteria))
        if dep.group in self.dependencies:
            self.dependencies[dep.group].append(dep)
        else:
            self.dependencies[dep.group] = [dep]

    def parse_gemfile(self, path=''):
        '''Parses a Gemfile and returns a dict of categorized dependencies.'''

        if path == '':
            contents = self.contents
        else:
            contents = open(path).readlines()
        for line in contents:
            line = self.preprocess(line)
            if line == '' or line.startswith('source'):
                continue
            elif line.startswith('group'):
                match = self.group_block_regex.match(line)
                if match:
                    GemfileParser.global_group = match.group('groupblock')
            elif line.startswith('end'):
                GemfileParser.global_group = 'runtime'
            elif line.startswith('gemspec'):
                # Gemfile contains a call to gemspec
                gemfiledir = os.path.dirname(self.filepath)
                gemspec_list = glob.glob(os.path.join(gemfiledir, "*.gemspec"))
                if len(gemspec_list) > 1:
                    print("Multiple gemspec files found")
                    continue
                elif len(gemspec_list) < 1:
                    print("No gemspec file found. Ignoring the gemspec call")
                else:
                    gemspec_file = gemspec_list[0]
                    self.parse_gemspec(
                        path=os.path.join(gemfiledir, gemspec_file))
            elif line.startswith('gem '):
                self.parse_line(line)
        return self.dependencies

    def parse_gemspec(self, path=''):
        '''Method to handle gemspec files.'''

        if path == '':
            contents = self.contents
        else:
            contents = open(path).readlines()
        for line in contents:
            line = self.preprocess(line)
            match = GemfileParser.add_dvtdep_regex.match(line)
            if match:
                GemfileParser.global_group = 'development'
            else:
                match = GemfileParser.add_rundep_regex.match(line)
                if match:
                    GemfileParser.global_group = 'runtime'
            if match:
                line = match.group('line')
                self.parse_line(line)
        return self.dependencies

    def parse(self):
        '''Calls necessary function based on whether file is a gemspec file
        or not and forwards the dicts returned by them.'''
        if self.gemspec:
            return self.parse_gemspec()
        else:
            return self.parse_gemfile()
