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

from Queue import Queue
import datetime
import threading

import cloudstorage
from rogerthat.consts import DEBUG, OFFLOAD_QUEUE
from rogerthat.utils import OFFLOAD_HEADER, now
from google.appengine.api.logservice import logservice
from google.appengine.ext import db, deferred


try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

MAX_BUF_SIZE = 1024 * 1024 * 10
OFFLOAD_HEADER_LENGTH = len(OFFLOAD_HEADER)

class OffloadSettings(db.Model):
    until_request_id = db.ByteStringProperty(indexed=False)

    @staticmethod
    def get_instance():
        return OffloadSettings.get_or_insert("settings")

class OffloadRun(db.Model):
    offset = db.ByteStringProperty(indexed=False)
    until_request_id = db.ByteStringProperty(indexed=False)

def offload_logs(offload_run_key=None):
    if DEBUG:
        return
    offset_settings = OffloadSettings.get_instance()
    if offload_run_key is None:
        offload_run = OffloadRun()
        offload_run.until_request_id = offset_settings.until_request_id
        offload_run.put()
        offload_run_key = offload_run.key()
    deferred.defer(_offload_logs, offload_run_key, _queue=OFFLOAD_QUEUE, _countdown=5)

def _get_bucket_file_handle(date):
    bucket = '/rogerthat-protocol-logs'
    counter = 0
    while True:
        counter += 1
        file_name = "%s/protocol-logs-%04d%02d%02d.%d" % (bucket, date.year, date.month, date.day, counter)
        try:
            cloudstorage.stat(file_name)
        except cloudstorage.NotFoundError:
            break
    return cloudstorage.open(file_name, 'w', content_type='text/plain')

def _offload_logs(offload_run_key):
    to_be_saved = list()
    write_queue = Queue()
    def writer():
        current_date = None
        gcs_fh = None
        while True:
            packet = write_queue.get()
            if packet is None:
                if gcs_fh:
                    gcs_fh.close()
                return  # Exit thread
            date, buf, offset, to_be_saved = packet
            if current_date is None or current_date != date:
                if gcs_fh:
                    gcs_fh.close()
                current_date = date
                gcs_fh = _get_bucket_file_handle(date)
            gcs_fh.write(buf.getvalue())
            if offset is not None:
                offload_run = db.get(offload_run_key)
                offload_run.offset = offset
                to_be_saved.append(offload_run)
            if to_be_saved:
                db.put(to_be_saved)
    done = False
    offload_run = db.get(offload_run_key)
    offset = offload_run.offset
    thread = threading.Thread(target=writer)
    thread.daemon = True
    thread.start()
    try:
        buf_date = None
        buf = StringIO()
        start = now()
        for requestLog in logservice.fetch(offset=offset, minimum_log_level=logservice.LOG_LEVEL_INFO,
                                           include_incomplete=False, include_app_logs=True):
            if offset is None:
                # This is the first request
                # ==> Store the request id
                offset_settings = OffloadSettings.get_instance()
                offset_settings.until_request_id = requestLog.request_id
                to_be_saved.append(offset_settings)
            elif requestLog.request_id == offload_run.until_request_id:
                if buf_date:
                    write_queue.put((buf_date, buf, None, to_be_saved))
                    to_be_saved = list()
                    db.delete(offload_run_key)  # This job is done
                done = True
                break
            offset = requestLog.offset
            date = datetime.datetime.fromtimestamp(requestLog.start_time).date()
            if not buf_date:
                buf_date = date
            elif date != buf_date:
                if buf.tell() > 0:
                    write_queue.put((buf_date, buf, offset, to_be_saved))
                    to_be_saved = list()
                    buf = StringIO()
                buf_date = date
            elif buf.tell() > MAX_BUF_SIZE:
                write_queue.put((buf_date, buf, offset, to_be_saved))
                to_be_saved = list()
                buf = StringIO()
            elif now() - start > 9 * 60:  # Deffered deadline = 10 minutes
                write_queue.put((buf_date, buf, offset, to_be_saved))
                break
            for appLog in requestLog.app_logs:
                if appLog.message and appLog.message.startswith(OFFLOAD_HEADER):
                    buf.write(appLog.message[OFFLOAD_HEADER_LENGTH + 1:])
                    buf.write("\n")
        else:
            if buf.tell() > 0:
                write_queue.put((buf_date, buf, None, to_be_saved))
            done = True
    finally:
        write_queue.put(None)  # Exit writer thread
        thread.join()
    if not done:
        offload_logs(offload_run_key)
