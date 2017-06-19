# Copyright 2015 Red Hat Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import io
import tempfile

import mock
from oslotest import base
import six
import testscenarios

from tripleo_heat_templates import environment_generator

load_tests = testscenarios.load_tests_apply_scenarios

basic_template = '''
parameters:
  FooParam:
    default: foo
    description: Foo description
    type: string
  BarParam:
    default: 42
    description: Bar description
    type: number
  EndpointMap:
    default: {}
    description: Parameter that should not be included by default
    type: json
resources:
  # None
'''
basic_private_template = '''
parameters:
  FooParam:
    default: foo
    description: Foo description
    type: string
  _BarParam:
    default: 42
    description: Bar description
    type: number
resources:
  # None
'''
mandatory_template = '''
parameters:
  FooParam:
    description: Mandatory param
    type: string
resources:
  # None
'''
index_template = '''
parameters:
  FooParam:
    description: Param with %index% as its default
    type: string
    default: '%index%'
resources:
  # None
'''
multiline_template = '''
parameters:
  FooParam:
    description: |
      Parameter with
      multi-line description
    type: string
    default: ''
resources:
  # None
'''


class GeneratorTestCase(base.BaseTestCase):
    content_scenarios = [
        ('basic',
         {'template': basic_template,
          'exception': None,
          'input_file': '''environments:
  -
    name: basic
    title: Basic Environment
    description: Basic description
    files:
      foo.yaml:
        parameters: all
''',
          'expected_output': '''# title: Basic Environment
# description: |
#   Basic description
parameter_defaults:
  # Bar description
  # Type: number
  BarParam: 42

  # Foo description
  # Type: string
  FooParam: foo

''',
          }),
        ('basic-one-param',
         {'template': basic_template,
          'exception': None,
          'input_file': '''environments:
  -
    name: basic
    title: Basic Environment
    description: Basic description
    files:
      foo.yaml:
        parameters:
          - FooParam
''',
          'expected_output': '''# title: Basic Environment
# description: |
#   Basic description
parameter_defaults:
  # Foo description
  # Type: string
  FooParam: foo

''',
          }),
        ('basic-static-param',
         {'template': basic_template,
          'exception': None,
          'input_file': '''environments:
  -
    name: basic
    title: Basic Environment
    description: Basic description
    files:
      foo.yaml:
        parameters: all
    static:
      - BarParam
''',
          'expected_output': '''# title: Basic Environment
# description: |
#   Basic description
parameter_defaults:
  # Foo description
  # Type: string
  FooParam: foo

  # ******************************************************
  # Static parameters - these are values that must be
  # included in the environment but should not be changed.
  # ******************************************************
  # Bar description
  # Type: number
  BarParam: 42

  # *********************
  # End static parameters
  # *********************
''',
          }),
        ('basic-static-param-sample',
         {'template': basic_template,
          'exception': None,
          'input_file': '''environments:
  -
    name: basic
    title: Basic Environment
    description: Basic description
    files:
      foo.yaml:
        parameters: all
    static:
      - BarParam
    sample_values:
      BarParam: 1
      FooParam: ''
''',
          'expected_output': '''# title: Basic Environment
# description: |
#   Basic description
parameter_defaults:
  # Foo description
  # Type: string
  FooParam: ''

  # ******************************************************
  # Static parameters - these are values that must be
  # included in the environment but should not be changed.
  # ******************************************************
  # Bar description
  # Type: number
  BarParam: 1

  # *********************
  # End static parameters
  # *********************
''',
          }),
        ('basic-private',
         {'template': basic_private_template,
          'exception': None,
          'input_file': '''environments:
  -
    name: basic
    title: Basic Environment
    description: Basic description
    files:
      foo.yaml:
        parameters: all
''',
          'expected_output': '''# title: Basic Environment
# description: |
#   Basic description
parameter_defaults:
  # Foo description
  # Type: string
  FooParam: foo

''',
          }),
        ('mandatory',
         {'template': mandatory_template,
          'exception': None,
          'input_file': '''environments:
  -
    name: basic
    title: Basic Environment
    description: Basic description
    files:
      foo.yaml:
        parameters: all
''',
          'expected_output': '''# title: Basic Environment
# description: |
#   Basic description
parameter_defaults:
  # Mandatory param
  # Mandatory. This parameter must be set by the user.
  # Type: string
  FooParam: <None>

''',
          }),
        ('basic-sample',
         {'template': basic_template,
          'exception': None,
          'input_file': '''environments:
  -
    name: basic
    title: Basic Environment
    description: Basic description
    files:
      foo.yaml:
        parameters: all
    sample_values:
      FooParam: baz
''',
          'expected_output': '''# title: Basic Environment
# description: |
#   Basic description
parameter_defaults:
  # Bar description
  # Type: number
  BarParam: 42

  # Foo description
  # Type: string
  FooParam: baz

''',
          }),
        ('basic-resource-registry',
         {'template': basic_template,
          'exception': None,
          'input_file': '''environments:
  -
    name: basic
    title: Basic Environment
    description: Basic description
    files:
      foo.yaml:
        parameters: all
    resource_registry:
      OS::TripleO::FakeResource: fake-filename.yaml
''',
          'expected_output': '''# title: Basic Environment
# description: |
#   Basic description
parameter_defaults:
  # Bar description
  # Type: number
  BarParam: 42

  # Foo description
  # Type: string
  FooParam: foo

resource_registry:
  OS::TripleO::FakeResource: fake-filename.yaml
''',
          }),
        ('basic-hidden',
         {'template': basic_template,
          'exception': None,
          'input_file': '''environments:
  -
    name: basic
    title: Basic Environment
    description: Basic description
    files:
      foo.yaml:
        parameters: all
    sample_values:
      EndpointMap: |-2

            foo: bar
''',
          'expected_output': '''# title: Basic Environment
# description: |
#   Basic description
parameter_defaults:
  # Bar description
  # Type: number
  BarParam: 42

  # Parameter that should not be included by default
  # Type: json
  EndpointMap:
    foo: bar

  # Foo description
  # Type: string
  FooParam: foo

''',
          }),
        ('missing-param',
         {'template': basic_template,
          'exception': RuntimeError,
          'input_file': '''environments:
  -
    name: basic
    title: Basic Environment
    description: Basic description
    files:
      foo.yaml:
        parameters:
          - SomethingNonexistent
''',
          'expected_output': None,
          }),
        ('percent-index',
         {'template': index_template,
          'exception': None,
          'input_file': '''environments:
  -
    name: basic
    title: Basic Environment
    description: Basic description
    files:
      foo.yaml:
        parameters: all
''',
          'expected_output': '''# title: Basic Environment
# description: |
#   Basic description
parameter_defaults:
  # Param with %index% as its default
  # Type: string
  FooParam: '%index%'

''',
          }),
        ('multi-line-desc',
         {'template': multiline_template,
          'exception': None,
          'input_file': '''environments:
  -
    name: basic
    title: Basic Environment
    description: Basic description
    files:
      foo.yaml:
        parameters: all
''',
          'expected_output': '''# title: Basic Environment
# description: |
#   Basic description
parameter_defaults:
  # Parameter with
  # multi-line description
  # Type: string
  FooParam: ''

''',
          }),
        ]

    @classmethod
    def generate_scenarios(cls):
        cls.scenarios = testscenarios.multiply_scenarios(
            cls.content_scenarios)

    def test_generator(self):
        fake_input = io.StringIO(six.text_type(self.input_file))
        fake_template = io.StringIO(six.text_type(self.template))
        _, fake_output_path = tempfile.mkstemp()
        fake_output = open(fake_output_path, 'w')
        with mock.patch('tripleo_heat_templates.environment_generator.open',
                        create=True) as mock_open:
            mock_open.side_effect = [fake_input, fake_template, fake_output]
            if not self.exception:
                environment_generator.generate_environments('ignored.yaml')
            else:
                self.assertRaises(self.exception,
                                  environment_generator.generate_environments,
                                  'ignored.yaml')
                return
        expected = environment_generator._FILE_HEADER + self.expected_output
        with open(fake_output_path) as f:
            self.assertEqual(expected, f.read())

GeneratorTestCase.generate_scenarios()
