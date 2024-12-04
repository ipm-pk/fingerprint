# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2024 Fraunhofer IPM <support.fingerprint@ipm.fraunhofer.de>
#
# SPDX-License-Identifier: MIT

"""Placeholder class for a Track & Trace Fingerprint system. It exhibits the basic function set of
 a real system, but most functions print only a notification that they were called. The call
 validation is disabled as well."""

__version__ = 1.02

import asyncio
from fp_tcpip_system.fp_tcp_clients.fp_tcp_interface_definitions import RunState, ResultState, \
    ErrorType, FpStatus


class FpEchoSystem:
    def __init__(self):
        # Set up Fingerprint system representing values.
        self.status = FpStatus()

        # Set up echo management.
        self.task_lock = asyncio.Lock()  # used to serialize certain tasks.
        self._init_duration_estimations()

    def _init_duration_estimations(self):
        """For each service, set a fix expected duration, in milliseconds."""
        self.duration_estimations = {
            'reset_system': 5,
            'get_status': 10,
            'set_image_matching_type': 10,
            'add_part': 2000,
            'trace_part': 2100,
        }

    async def _get_status(self):
        return self.status.as_dict()

    async def reset_system(self, *args):
        async with self.task_lock:
            print("FPSystem-->reset_system.", args)
            self.status.reset()
            await asyncio.sleep(self.duration_estimations['reset_system'] / 1000.)  # seconds
            self.status.update(RunState.SYSTEM_READY, ResultState.RESULT_UNDEFINED,
                               ErrorType.NO_ERROR, '')
            print("FPSystem-->reset_system finished.")
            return {}

    def reset_system_prior_info(self, *args):
        # For echoing input no requirements must be fulfilled.
        prior_info = {
            'ExpectedServiceExecutionDuration': self.duration_estimations['reset_system'],  # ms
            'ServiceTriggerResult': 1,            # 1=accepted
            'ServiceResultMessage': "",
            'ServiceResultCode': 0,
        }
        return prior_info

    async def get_status(self, *args):
        async with self.task_lock:
            """Return the status of the fingerprint system."""
            print("FPSystem-->get_status.", args)
            await asyncio.sleep(self.duration_estimations['get_status'] / 1000.)
            print("FPSystem-->get_status finished.")
            return self._get_status()

    def get_status_prior_info(self, *args):
        # For echoing input no requirements must be fulfilled.
        prior_info = {
            'ExpectedServiceExecutionDuration': self.duration_estimations['get_status'],  # ms
            'ServiceTriggerResult': 1,            # 1=accepted
            'ServiceResultMessage': "",
            'ServiceResultCode': 0,
        }
        return prior_info

    async def set_image_matching_type(self, *args):
        """Activates the image matching algorithm for a certain part type."""
        async with self.task_lock:
            print("FPSystem-->set_image_matching_type.", args)
            self.status.update(RunState.COMMAND_RUNNING, ResultState.RESULT_UNDEFINED,
                               ErrorType.NO_ERROR, 'set_image_matching_type')
            await asyncio.sleep(self.duration_estimations['set_image_matching_type'] / 1000.)
            self.status.update(RunState.SYSTEM_READY, ResultState.RESULT_READY, ErrorType.NO_ERROR,
                               '')
            print("FPSystem-->set_image_matching_type finished.")
            return {}

    def set_image_matching_type_prior_info(self, *args):
        # For echoing input no requirements must be fulfilled.
        prior_info = {
            'ExpectedServiceExecutionDuration':
                self.duration_estimations['set_image_matching_type'],  # ms
            'ServiceTriggerResult': 1,            # 1=accepted
            'ServiceResultMessage': "",
            'ServiceResultCode': 0,
        }
        return prior_info

    def _sync_success_prior_info(self):
        # Currently unused, since all commands are implemented async.
        # For echoing input no requirements must be fulfilled.
        prior_info = {
            'ServiceExecutionStatus': 0,
            'ServiceResultMessage': "",
            'ServiceResultCode': 0,
        }
        return prior_info

    async def add_part(self, *args):
        async with self.task_lock:
            print("FPSystem-->add_part.", args)
            self.status.update(RunState.ACQUIRING_IMAGE, ResultState.RESULT_UNDEFINED,
                               ErrorType.NO_ERROR, 'add_part')
            await asyncio.sleep(self.duration_estimations['add_part'] / 1000. * 0.4)
            self.status.update(RunState.COMMAND_RUNNING, ResultState.RESULT_UNDEFINED,
                               ErrorType.NO_ERROR, 'add_part')
            await asyncio.sleep(self.duration_estimations['add_part'] / 1000. * 0.6)
            self.status.update(RunState.SYSTEM_READY, ResultState.RESULT_READY,
                               ErrorType.NO_ERROR, '')
            print("FPSystem-->add_part finished.")
            res = {
                'ServiceExecutionResult': 0,    # 0=success
                'PartIDsOfDuplicates': "",
            }
            return res

    def add_part_prior_info(self, *args):
        # For echoing input no requirements must be fulfilled.
        prior_info = {
            'ExpectedServiceExecutionDuration': self.duration_estimations['add_part'],  # ms
            'ServiceTriggerResult': 1,            # 1=accepted
            'ServiceResultMessage': "",
            'ServiceResultCode': 0,
        }
        return prior_info

    async def trace_part(self, *args):
        async with self.task_lock:
            print("FPSystem-->trace_part.", args)
            self.status.update(RunState.ACQUIRING_IMAGE, ResultState.RESULT_UNDEFINED,
                               ErrorType.NO_ERROR, 'trace_part')
            await asyncio.sleep(self.duration_estimations['trace_part'] / 1000 * 0.4)
            self.status.update(RunState.COMMAND_RUNNING, ResultState.RESULT_UNDEFINED,
                               ErrorType.NO_ERROR, 'trace_part')
            await asyncio.sleep(self.duration_estimations['trace_part'] / 1000 * 0.6)
            self.status.update(RunState.SYSTEM_READY, ResultState.RESULT_READY, ErrorType.NO_ERROR,
                               '')
            print("FPSystem-->trace_part finished.")
            res = {
                'ServiceExecutionResult': 0,    # 0=success
                'PartID': "",
                'BatchID': "",
                'PartType': "",
                'CurrentConfidenceValue1': 99,
                'CurrentConfidenceValue2': 100,
                'AverageConfidenceValue1': 97,
                'AverageConfidenceValue2': 98,
            }
            return res

    def trace_part_prior_info(self, *args):
        # For echoing input no requirements must be fulfilled.
        prior_info = {
            'ExpectedServiceExecutionDuration': self.duration_estimations['trace_part'],  # ms
            'ServiceTriggerResult': 1,            # 1=accepted
            'ServiceResultMessage': "",
            'ServiceResultCode': 0,
        }
        return prior_info
