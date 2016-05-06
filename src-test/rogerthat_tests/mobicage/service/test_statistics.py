# -*- coding: utf-8 -*-
# Copyright 2016 Mobicage NV
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# @@license_version:1.1@@

import datetime
import logging

import mc_unittest
from rogerthat.models import FlowStatistics
from rogerthat.rpc import users
from rogerthat.to.statistics import FlowStatisticsTO
from rogerthat.utils import now

SENT = FlowStatistics.STATUS_SENT
RCVD = FlowStatistics.STATUS_RECEIVED
READ = FlowStatistics.STATUS_READ
ACKED = FlowStatistics.STATUS_ACKED


class FlowStatisticsTestCase(mc_unittest.TestCase):
    tag = u'GO'
    service_identity_user = users.User(u'service@example.com/+default+')

    def test_status_list_names(self):
        stats = FlowStatistics(key=FlowStatistics.create_key(self.tag, self.service_identity_user))
        stats.labels = list('012345')
        self.assertEqual('step_0_read', stats._get_status_list_name(list(), '0', 'read'))
        self.assertEqual('step_0_1_2_3_4_sent', stats._get_status_list_name(list('0123'), '4', 'sent'))
        self.assertEqual('step_0_1_2_3_4_acked_5', stats._get_status_list_name(list('0123'), '4', 'acked', '5'))

    def _create_stats(self):
        # Flow used in this unit test:
        #
        #                      START
        #                        |
        #                    +-------+
        #                    | id: A |
        #                    +-------+
        #                 _one_|   |_two_
        #                |               |
        #            +-------+       +-------+
        #            | id: B |       | id: C |--------+
        #            +-------+       +-------+        |
        #              |   |_negative_   |            |
        #         positive            |  |_three_     |
        #              |              |          |    |
        #          +-------+          |          |    |
        #          | id: D |---+------+-----+----+----+
        #          +-------+                |
        #                               +-------+
        #                               | id: E |---------- END
        #                               +-------+

        stats = FlowStatistics(key=FlowStatistics.create_key(self.tag, self.service_identity_user))
        stats.set_today()

        # path: A --one--> B --positive--> D -->rogerthat--> E -->rogerthat--> END
        stats.add([], 'A', SENT)
        stats.add([], 'A', RCVD)
        stats.add([], 'A', READ)
        stats.add([], 'A', ACKED, 'one')
        stats.add(['A', 'one'], 'B', SENT)
        stats.add(['A', 'one'], 'B', RCVD)
        stats.add(['A', 'one'], 'B', READ)
        stats.add(['A', 'one'], 'B', ACKED, 'positive')
        stats.add(['A', 'one', 'B', 'positive'], 'D', SENT)
        stats.add(['A', 'one', 'B', 'positive'], 'D', RCVD)
        stats.add(['A', 'one', 'B', 'positive'], 'D', READ)
        stats.add(['A', 'one', 'B', 'positive'], 'D', ACKED, None)
        stats.add(['A', 'one', 'B', 'positive', 'D', None], 'E', SENT)
        stats.add(['A', 'one', 'B', 'positive', 'D', None], 'E', RCVD)
        stats.add(['A', 'one', 'B', 'positive', 'D', None], 'E', READ)
        stats.add(['A', 'one', 'B', 'positive', 'D', None], 'E', ACKED, None)

        # path: A --one--> B (sent+rcvd+READ)
        stats.add([], 'A', SENT)
        stats.add([], 'A', RCVD)
        stats.add([], 'A', READ)
        stats.add([], 'A', ACKED, 'one')
        stats.add(['A', 'one'], 'B', SENT)
        stats.add(['A', 'one'], 'B', RCVD)
        stats.add(['A', 'one'], 'B', READ)

        # path: A --two--> C --rogerthat--> E -->rogerthat--> END
        stats.add([], 'A', SENT)
        stats.add([], 'A', RCVD)
        stats.add([], 'A', READ)
        stats.add([], 'A', ACKED, 'two')
        stats.add(['A', 'two'], 'C', SENT)
        stats.add(['A', 'two'], 'C', RCVD)
        stats.add(['A', 'two'], 'C', READ)
        stats.add(['A', 'two'], 'C', ACKED, None)
        stats.add(['A', 'two', 'C', None], 'E', SENT)
        stats.add(['A', 'two', 'C', None], 'E', RCVD)
        stats.add(['A', 'two', 'C', None], 'E', READ)
        stats.add(['A', 'two', 'C', None], 'E', ACKED, None)

        # path: A --two--> C --three--> E (sent+RCVD)
        stats.add([], 'A', SENT)
        stats.add([], 'A', RCVD)
        stats.add([], 'A', READ)
        stats.add([], 'A', ACKED, 'two')
        stats.add(['A', 'two'], 'C', SENT)
        stats.add(['A', 'two'], 'C', RCVD)
        stats.add(['A', 'two'], 'C', READ)
        stats.add(['A', 'two'], 'C', ACKED, 'three')
        stats.add(['A', 'two', 'C', 'three'], 'E', SENT)
        stats.add(['A', 'two', 'C', 'three'], 'E', RCVD)

        return stats

    def test_stats_model(self):
        stats = self._create_stats()

        self.assertEqual(4, stats.step_0_sent[0])
        self.assertEqual(4, stats.step_0_received[0])
        self.assertEqual(4, stats.step_0_read[0])

        self.assertEqual(4, stats.get_status_list([], 'A', SENT)[0])
        self.assertEqual(4, stats.get_status_list([], 'A', RCVD)[0])
        self.assertEqual(4, stats.get_status_list([], 'A', READ)[0])
        self.assertEqual(2, stats.get_status_list([], 'A', ACKED, 'one')[0])
        self.assertEqual(2, stats.get_status_list([], 'A', ACKED, 'two')[0])

        self.assertEqual(2, stats.get_status_list(['A', 'one'], 'B', SENT)[0])
        self.assertEqual(2, stats.get_status_list(['A', 'one'], 'B', RCVD)[0])
        self.assertEqual(2, stats.get_status_list(['A', 'one'], 'B', READ)[0])
        self.assertEqual(1, stats.get_status_list(['A', 'one'], 'B', ACKED, 'positive')[0])
        self.assertEqual(0, stats.get_status_list(['A', 'one'], 'B', ACKED, 'negative')[0])

        self.assertEqual(2, stats.get_status_list(['A', 'two'], 'C', SENT)[0])
        self.assertEqual(2, stats.get_status_list(['A', 'two'], 'C', RCVD)[0])
        self.assertEqual(2, stats.get_status_list(['A', 'two'], 'C', READ)[0])
        self.assertEqual(1, stats.get_status_list(['A', 'two'], 'C', ACKED, 'three')[0])
        self.assertEqual(1, stats.get_status_list(['A', 'two'], 'C', ACKED, None)[0])

        self.assertEqual(1, stats.get_status_list(['A', 'one', 'B', 'positive'], 'D', SENT)[0])
        self.assertEqual(1, stats.get_status_list(['A', 'one', 'B', 'positive'], 'D', RCVD)[0])
        self.assertEqual(1, stats.get_status_list(['A', 'one', 'B', 'positive'], 'D', READ)[0])
        self.assertEqual(1, stats.get_status_list(['A', 'one', 'B', 'positive'], 'D', ACKED, None)[0])

        self.assertEqual(1, stats.get_status_list(['A', 'two', 'C', None], 'E', SENT)[0])
        self.assertEqual(1, stats.get_status_list(['A', 'two', 'C', None], 'E', RCVD)[0])
        self.assertEqual(1, stats.get_status_list(['A', 'two', 'C', None], 'E', READ)[0])
        self.assertEqual(1, stats.get_status_list(['A', 'two', 'C', None], 'E', ACKED, None)[0])

        self.assertEqual(1, stats.get_status_list(['A', 'two', 'C', 'three'], 'E', SENT)[0])
        self.assertEqual(1, stats.get_status_list(['A', 'two', 'C', 'three'], 'E', RCVD)[0])
        self.assertEqual(0, stats.get_status_list(['A', 'two', 'C', 'three'], 'E', READ)[0])
        self.assertEqual(0, stats.get_status_list(['A', 'two', 'C', 'three'], 'E', ACKED, None)[0])

        self.assertEqual(1, stats.get_status_list(['A', 'one', 'B', 'positive', 'D', None], 'E', SENT)[0])
        self.assertEqual(1, stats.get_status_list(['A', 'one', 'B', 'positive', 'D', None], 'E', RCVD)[0])
        self.assertEqual(1, stats.get_status_list(['A', 'one', 'B', 'positive', 'D', None], 'E', READ)[0])
        self.assertEqual(1, stats.get_status_list(['A', 'one', 'B', 'positive', 'D', None], 'E', ACKED, None)[0])

    def test_stats_t_o_with_flows_only(self):
        def count(day_stats):
            return sum(s.count for s in day_stats)

        stats = self._create_stats()

        for days in (1, 7, 300):  # should all return the same result
            logging.info('Days: %s', days)
            statsTO = FlowStatisticsTO.from_model(stats,
                                                  FlowStatisticsTO.VIEW_FLOWS,
                                                  days=days)
            self.assertEqual(self.tag, statsTO.tag)
            self.assertEqual(0, len(statsTO.steps))
            self.assertEqual(1, len(statsTO.flows))

            step_a = statsTO.flows[0]
            # step_a paths:
            # A --one--> B --positive--> D -->rogerthat--> E -->rogerthat--> END
            # A --one--> B (sent+rcvd+READ)
            # A --two--> C --rogerthat--> E -->rogerthat--> END
            # A --two--> C --three--> E (sent+RCVD)
            self.assertEqual('A', step_a.step_id)
            self.assertTupleEqual((4, 4, 4),
                                  (count(step_a.sent_count), count(step_a.received_count), count(step_a.read_count)))
            self.assertEqual(2, len(step_a.buttons))
            self.assertEqual(2, count(step_a.get_button('one').acked_count))
            self.assertEqual(2, count(step_a.get_button('two').acked_count))

            step_a_one_b = step_a.get_button('one').next_steps[0]
            # step_a_one_b paths:
            # A --one--> B --positive--> D -->rogerthat--> E -->rogerthat--> END
            # A --one--> B (sent+rcvd+READ)
            self.assertEqual('B', step_a_one_b.step_id)
            self.assertTupleEqual((2, 2, 2), (count(step_a_one_b.sent_count),
                                              count(step_a_one_b.received_count),
                                              count(step_a_one_b.read_count)))
            self.assertEqual(1, len(step_a_one_b.buttons))
            self.assertEqual(1, count(step_a_one_b.get_button('positive').acked_count))

            step_a_one_b_pos_d = step_a_one_b.get_button('positive').next_steps[0]
            # step_a_one_b_pos_d paths:
            # A --one--> B --positive--> D -->rogerthat--> E -->rogerthat--> END
            self.assertEqual('D', step_a_one_b_pos_d.step_id)
            self.assertTupleEqual((1, 1, 1), (count(step_a_one_b_pos_d.sent_count),
                                              count(step_a_one_b_pos_d.received_count),
                                              count(step_a_one_b_pos_d.read_count)))
            self.assertEqual(1, len(step_a_one_b_pos_d.buttons))
            self.assertEqual(1, count(step_a_one_b_pos_d.get_button(None).acked_count))

            step_a_one_b_pos_d_rt_e = step_a_one_b_pos_d.get_button(None).next_steps[0]
            # step_a_one_b_pos_d_rt_e paths:
            # A --one--> B --positive--> D -->rogerthat--> E -->rogerthat--> END
            self.assertEqual('E', step_a_one_b_pos_d_rt_e.step_id)
            self.assertTupleEqual((1, 1, 1), (count(step_a_one_b_pos_d_rt_e.sent_count),
                                              count(step_a_one_b_pos_d_rt_e.received_count),
                                              count(step_a_one_b_pos_d_rt_e.read_count)))
            self.assertEqual(1, len(step_a_one_b_pos_d_rt_e.buttons))
            self.assertEqual(1, count(step_a_one_b_pos_d_rt_e.get_button(None).acked_count))
            self.assertEqual(0, len(step_a_one_b_pos_d_rt_e.get_button(None).next_steps))

            step_a_two_c = step_a.get_button('two').next_steps[0]
            # step_a_two_c paths:
            # A --two--> C --rogerthat--> E -->rogerthat--> END
            # A --two--> C --three--> E (sent+RCVD)
            self.assertEqual('C', step_a_two_c.step_id)
            self.assertTupleEqual((2, 2, 2), (count(step_a_two_c.sent_count),
                                              count(step_a_two_c.received_count),
                                              count(step_a_two_c.read_count)))
            self.assertEqual(2, len(step_a_two_c.buttons))
            self.assertEqual(1, count(step_a_two_c.get_button(None).acked_count))
            self.assertEqual(1, count(step_a_two_c.get_button('three').acked_count))

            step_a_two_c_rt_e = step_a_two_c.get_button(None).next_steps[0]
            # step_a_two_c_rt_e paths:
            # A --two--> C --rogerthat--> E -->rogerthat--> END
            self.assertEqual('E', step_a_two_c_rt_e.step_id)
            self.assertTupleEqual((1, 1, 1), (count(step_a_two_c_rt_e.sent_count),
                                              count(step_a_two_c_rt_e.received_count),
                                              count(step_a_two_c_rt_e.read_count)))
            self.assertEqual(1, len(step_a_two_c_rt_e.buttons))
            self.assertEqual(1, count(step_a_two_c_rt_e.get_button(None).acked_count))

            step_a_two_c_three_e = step_a_two_c.get_button('three').next_steps[0]
            # step_a_two_c_three_e paths:
            # A --two--> C --three--> E (sent+RCVD)
            self.assertEqual('E', step_a_two_c_three_e.step_id)
            self.assertTupleEqual((1, 1, 0), (count(step_a_two_c_three_e.sent_count),
                                              count(step_a_two_c_three_e.received_count),
                                              count(step_a_two_c_three_e.read_count)))
            self.assertEqual(0, len(step_a_two_c_three_e.buttons))

    def test_stats_t_o_with_steps_only(self):

        def count(day_stats):
            return sum(s.count for s in day_stats)

        stats = self._create_stats()

        for days in (1, 7, 300):  # should all return the same result
            logging.info('Days: %s', days)
            statsTO = FlowStatisticsTO.from_model(stats,
                                                  FlowStatisticsTO.VIEW_STEPS,
                                                  days=days)
            self.assertEqual(self.tag, statsTO.tag)
            self.assertEqual(0, len(statsTO.flows))
            self.assertEqual(5, len(statsTO.steps))

            # A --one--> B --positive--> D -->rogerthat--> E -->rogerthat--> END
            # A --one--> B (sent+rcvd+READ)
            # A --two--> C --rogerthat--> E -->rogerthat--> END
            # A --two--> C --three--> E (sent+RCVD)

            # step A
            step_a = statsTO.get_step('A')
            self.assertEqual('A', step_a.step_id)
            self.assertTupleEqual((4, 4, 4),
                                  (count(step_a.sent_count), count(step_a.received_count), count(step_a.read_count)))
            self.assertEqual(2, len(step_a.buttons))
            self.assertEqual(2, count(step_a.get_button('one').acked_count))
            self.assertEqual(2, count(step_a.get_button('two').acked_count))

            # step B
            step_b = statsTO.get_step('B')
            self.assertTupleEqual((2, 2, 2),
                                  (count(step_b.sent_count), count(step_b.received_count), count(step_b.read_count)))
            self.assertEqual(1, len(step_b.buttons))  # only 'positive' is reached, no entry for 'negative'
            self.assertEqual(1, count(step_b.get_button('positive').acked_count))
            self.assertIsNone(step_b.get_button('negative'))

            # step C
            step_c = statsTO.get_step('C')
            self.assertTupleEqual((2, 2, 2),
                                  (count(step_c.sent_count), count(step_c.received_count), count(step_c.read_count)))
            self.assertEqual(2, len(step_c.buttons))
            self.assertEqual(1, count(step_c.get_button('three').acked_count))
            self.assertEqual(1, count(step_c.get_button(None).acked_count))

            # step D
            step_d = statsTO.get_step('D')
            self.assertTupleEqual((1, 1, 1),
                                  (count(step_d.sent_count), count(step_d.received_count), count(step_d.read_count)))
            self.assertEqual(1, len(step_d.buttons))
            self.assertEqual(1, count(step_d.get_button(None).acked_count))

            # step E
            step_e = statsTO.get_step('E')
            self.assertTupleEqual((3, 3, 2),
                                  (count(step_e.sent_count), count(step_e.received_count), count(step_e.read_count)))
            self.assertEqual(1, len(step_e.buttons))
            self.assertEqual(2, count(step_e.get_button(None).acked_count))

    def test_flow_stats_tomorrow(self):
        stats = FlowStatistics(key=FlowStatistics.create_key(self.tag, self.service_identity_user))
        _now = now()
        stats.set_today(datetime.datetime.utcfromtimestamp(_now - 86400).date())
        breadcrumbs = list()
        current_step_id = 'step_1'
        status = FlowStatistics.STATUS_SENT
        btn_id = None
        stats.add(breadcrumbs, current_step_id, status, btn_id)
        self.assertListEqual([1], stats.step_0_sent)
        stats.set_today(datetime.datetime.utcfromtimestamp(_now).date())
        self.assertListEqual([1, 0], stats.step_0_sent)
        stats.add(breadcrumbs, current_step_id, status, btn_id)
        self.assertListEqual([1, 1], stats.step_0_sent)
        stats.add(breadcrumbs, current_step_id, status, btn_id)
        self.assertListEqual([1, 2], stats.step_0_sent)

        statsTO = FlowStatisticsTO.from_model(stats,
                                              FlowStatisticsTO.VIEW_STEPS,
                                              days=2)
        stepTO = statsTO.get_step(current_step_id)
        self.assertEqual(1, stepTO.sent_count[0].count)  # yesterday
        self.assertEqual(2, stepTO.sent_count[1].count)  # today
        self.assertLess(datetime.date(year=stepTO.sent_count[0].year, month=stepTO.sent_count[0].month,
                                      day=stepTO.sent_count[0].day),
                        datetime.date(year=stepTO.sent_count[1].year, month=stepTO.sent_count[1].month,
                                      day=stepTO.sent_count[1].day))
