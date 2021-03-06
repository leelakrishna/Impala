#!/usr/bin/env python
# Copyright (c) 2012 Cloudera, Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import pytest
import sys
import re
from copy import copy
from tests.beeswax.impala_beeswax import ImpalaBeeswaxException
from tests.common.test_vector import *
from tests.common.impala_test_suite import *

class TestQueryMemLimitScaling(ImpalaTestSuite):
  """Test class to do functional validation of per query memory limits. """
  QUERY = ["select * from lineitem where l_orderkey = -1",
           "select min(l_orderkey) from lineitem",
           "select * from lineitem order by l_orderkey limit 1"]

  # These query take 400mb-1gb if no mem limits are set
  MEM_LIMITS = ["-1", "400m", "150m"]

  @classmethod
  def get_workload(self):
    return 'tpch'

  @classmethod
  def add_test_dimensions(cls):
    super(TestQueryMemLimitScaling, cls).add_test_dimensions()
    # add mem_limit as a test dimension.
    new_dimension = TestDimension('mem_limit', *TestQueryMemLimitScaling.MEM_LIMITS)
    cls.TestMatrix.add_dimension(new_dimension)
    if cls.exploration_strategy() != 'exhaustive':
      cls.TestMatrix.add_constraint(lambda v:\
          v.get_value('table_format').file_format in ['parquet'])

  # Test running with different mem limits to exercise the dynamic memory
  # scaling functionality.
  def test_mem_usage_scaling(self, vector):
    mem_limit = copy(vector.get_value('mem_limit'))
    table_format = vector.get_value('table_format')
    exec_options = copy(vector.get_value('exec_option'))
    exec_options['mem_limit'] = mem_limit
    for query in self.QUERY:
      self.execute_query(query, exec_options, table_format=table_format)

class TestExprMemUsage(ImpalaTestSuite):
  @classmethod
  def get_workload(cls):
    return 'tpch'

  @classmethod
  def add_test_dimensions(cls):
    super(TestExprMemUsage, cls).add_test_dimensions()
    cls.TestMatrix.add_dimension(create_single_exec_option_dimension())
    if cls.exploration_strategy() != 'exhaustive':
      cls.TestMatrix.add_constraint(lambda v:\
          v.get_value('table_format').file_format in ['parquet'])

  def test_scanner_mem_usage(self, vector):
    exec_options = vector.get_value('exec_option')
    # This value was picked empircally based on the query.
    exec_options['mem_limit'] = '300m'
    self.execute_query_expect_success(self.client,
      "select count(*) from lineitem where lower(l_comment) = 'hello'", exec_options,
      table_format=vector.get_value('table_format'))

class TestTpchMemLimitError(ImpalaTestSuite):
  EXPECTED_ERROR_MSG = "Memory limit exceeded"

  # The mem limits that will be used.
  MEM_IN_MB = [100, 150, 180, 420, 700, 780, 960, 980, 1050, 1100]

  # Different values of mem limits and minimum mem limit (in MBs) each query is expected
  # to run without problem. Those values were determined by manual testing.
  MIN_MEM_FOR_TPCH = { 'Q1' : 145, 'Q2' : 105, 'Q3' : 645, 'Q4' : 160, 'Q5' : 375,\
                       'Q6' : 25, 'Q7' : 685, 'Q8' : 740, 'Q9' : 650, 'Q18' : 1100,\
                       'Q20' : 420, 'Q21' : 975}

  @classmethod
  def get_workload(self):
    return 'tpch'

  @classmethod
  def add_test_dimensions(cls):
    super(TestTpchMemLimitError, cls).add_test_dimensions()

    cls.TestMatrix.add_dimension(
      TestDimension('mem_limit', *TestTpchMemLimitError.MEM_IN_MB))

    cls.TestMatrix.add_constraint(lambda v:\
        v.get_value('table_format').file_format in ['parquet'])

  def low_memory_limit_test(self, vector, tpch_query, limit):
    mem = vector.get_value('mem_limit')
    # Mem consumption can be +-30MBs, depending on how many scanner threads are
    # running. Adding this extra mem in order to reduce false negatives in the tests.
    limit = limit + 30

    # If memory limit larger than the minimum threshold, then it is not expected to fail.
    expects_error = mem < limit;
    new_vector = copy(vector)
    new_vector.get_value('exec_option')['mem_limit'] = str(mem) + "m"
    try:
      self.run_test_case(tpch_query, new_vector)
    except ImpalaBeeswaxException as e:
      if (expects_error == 0):
        raise
      assert TestTpchMemLimitError.EXPECTED_ERROR_MSG in str(e)

  def test_low_mem_limit_q1(self, vector):
    self.low_memory_limit_test(vector, 'tpch-q1', self.MIN_MEM_FOR_TPCH['Q1']);

  def test_low_mem_limit_q2(self, vector):
    self.low_memory_limit_test(vector, 'tpch-q2', self.MIN_MEM_FOR_TPCH['Q2']);

  def test_low_mem_limit_q3(self, vector):
    self.low_memory_limit_test(vector, 'tpch-q3', self.MIN_MEM_FOR_TPCH['Q3']);

  def test_low_mem_limit_q4(self, vector):
    self.low_memory_limit_test(vector, 'tpch-q4', self.MIN_MEM_FOR_TPCH['Q4']);

  def test_low_mem_limit_q5(self, vector):
    self.low_memory_limit_test(vector, 'tpch-q5', self.MIN_MEM_FOR_TPCH['Q5']);

  def test_low_mem_limit_q6(self, vector):
    self.low_memory_limit_test(vector, 'tpch-q6', self.MIN_MEM_FOR_TPCH['Q6']);

  def test_low_mem_limit_q7(self, vector):
    self.low_memory_limit_test(vector, 'tpch-q7', self.MIN_MEM_FOR_TPCH['Q7']);

  def test_low_mem_limit_q8(self, vector):
    self.low_memory_limit_test(vector, 'tpch-q8', self.MIN_MEM_FOR_TPCH['Q8']);

  def test_low_mem_limit_q9(self, vector):
    self.low_memory_limit_test(vector, 'tpch-q9', self.MIN_MEM_FOR_TPCH['Q9']);

  def test_low_mem_limit_q18(self, vector):
    self.low_memory_limit_test(vector, 'tpch-q18', self.MIN_MEM_FOR_TPCH['Q18']);

  def test_low_mem_limit_q20(self, vector):
    self.low_memory_limit_test(vector, 'tpch-q20', self.MIN_MEM_FOR_TPCH['Q20']);

  def test_low_mem_limit_q21(self, vector):
    self.low_memory_limit_test(vector, 'tpch-q21', self.MIN_MEM_FOR_TPCH['Q21']);
