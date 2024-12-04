# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2024 Fraunhofer IPM <support.fingerprint@ipm.fraunhofer.de>
#
# SPDX-License-Identifier: MIT

"""Mockup for a Track & Trace Fingerprint system for marker-free object identification. It exhibits
 the basic function set of a real system, but the functionality is simulated. This allows for the
 integration of the sensor control in a controller device, e.g. a PLC."""

__version__ = 1.01

import asyncio
from dataclasses import dataclass
from random import randint
from fp_tcpip_system.fp_tcp_clients.fp_tcp_interface_definitions import RunState, ResultState, \
    ErrorType, FpStatus


FINGERPRINT_SIZE = 0


@dataclass(frozen=True, eq=True)
class FpDatabaseEntry:
    """Database entries are bytes in a real Fingerprint system."""
    fingerprint: str
    part_id: str
    batch_id: str
    part_type: str


class FpMockupSystem:
    def __init__(self):
        # Set up Fingerprint system representing values.
        self.status = FpStatus()
        self.image_matching = 'default'
        self.fp_databases = {}  # elements will be {str: set()}

        # Set up mockup management.
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

    async def reset_system(self):
        async with self.task_lock:
            print("FPSystem-->reset_system()")
            # todo: terminate all running mockup tasks.
            self.status.reset()
            await asyncio.sleep(self.duration_estimations['reset_system'] / 1000.)
            self.status.update(RunState.SYSTEM_READY, ResultState.RESULT_UNDEFINED,
                               ErrorType.NO_ERROR, '')
            print("FPSystem-->reset_system finished.\n")
            return {}

    def reset_system_prior_info(self, *args):
        # For reset_system no requirements must be fulfilled.
        prior_info = {
            'ExpectedServiceExecutionDuration': self.duration_estimations['reset_system'],  # ms
            'ServiceTriggerResult': 1,            # 1=accepted
            'ServiceResultMessage': "",
            'ServiceResultCode': 0,
        }
        return prior_info

    async def get_status(self):
        """Return the status of the fingerprint system. Can be run parallel to other tasks."""
        print("FPSystem-->get_status()")
        await asyncio.sleep(self.duration_estimations['get_status'] / 1000.)
        print("FPSystem-->get_status finished.\n")
        return self._get_status()

    def get_status_prior_info(self, *args):
        # For get_status no requirements must be fulfilled.
        prior_info = {
            'ExpectedServiceExecutionDuration': self.duration_estimations['get_status'],  # ms
            'ServiceTriggerResult': 1,            # 1=accepted
            'ServiceResultMessage': "",
            'ServiceResultCode': 0,
        }
        return prior_info

    async def set_image_matching_type(self, image_matching_name):
        """Activates the image matching algorithm for a certain part type."""
        async with self.task_lock:
            print(f"FPSystem-->set_image_matching_type( {image_matching_name} )")
            self.status.update(RunState.COMMAND_RUNNING, ResultState.RESULT_UNDEFINED,
                               ErrorType.NO_ERROR, 'set_image_matching_type')
            self.image_matching = str(image_matching_name)
            await asyncio.sleep(self.duration_estimations['set_image_matching_type'] / 1000.)

            self.status.update(RunState.SYSTEM_READY, ResultState.RESULT_READY,
                               ErrorType.NO_ERROR, '')
            print("FPSystem-->set_image_matching_type finished.\n")
            return {}

    def set_image_matching_type_prior_info(self, *args):
        # For set_image_matching_type no requirements must be fulfilled.
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
        # Check whether requirements are fulfilled.
        prior_info = {
            'ServiceExecutionStatus': 0,
            'ServiceResultMessage': "",
            'ServiceResultCode': 0,
        }
        return prior_info

    async def add_part(self, database_name, check_id_duplicates, check_fp_duplicates, part_id,
                       batch_id, part_type):
        async with self.task_lock:
            print(f"FPSystem-->add_part( {database_name}, {check_id_duplicates}, "
                  f"{check_fp_duplicates}, {part_id}, {batch_id}, {part_type} )")

            # Check system status.
            if not (self.status.run_state == RunState.SYSTEM_READY
                    and self.status.error_type == ErrorType.NO_ERROR):

                print("FPSystem-->add_part not executed, system not ready or in error state. Call"
                      " ResetSystem first.\n")
                res = {
                    'PartIDsOfDuplicates': "",
                }
                return res

            # Acquire image - delay simulation.
            self.status.update(RunState.ACQUIRING_IMAGE, ResultState.RESULT_UNDEFINED,
                               ErrorType.NO_ERROR, 'add_part')
            await asyncio.sleep(self.duration_estimations['add_part'] / 1000. * 0.4)  # 40%, seconds

            # Compute the pseudo fingerprint.
            self.status.update(RunState.COMMAND_RUNNING, ResultState.RESULT_UNDEFINED,
                               ErrorType.NO_ERROR, 'add_part')
            new_fingerprint = part_id.rjust(FINGERPRINT_SIZE // 3, '-') \
                + batch_id.rjust(FINGERPRINT_SIZE // 3, '-') \
                + part_type.rjust(FINGERPRINT_SIZE // 3 + FINGERPRINT_SIZE % 3, '-')

            # If set, search for duplicates in all databases.
            id_duplicates = []
            fp_duplicates = []
            for db in self.fp_databases.values():
                for fp_entry in db:
                    if check_id_duplicates and fp_entry.part_id == part_id:
                        id_duplicates.append(fp_entry)
                    if check_fp_duplicates and fp_entry.fingerprint == new_fingerprint:
                        fp_duplicates.append(fp_entry)

            await asyncio.sleep(self.duration_estimations['add_part'] / 1000. * 0.6)  # 60%, seconds

            # If there are duplicates, do not add the new part to the database.
            if len(id_duplicates) > 0:
                print("The AddPart duplicate check found duplicates!")
                self.status.update(RunState.SYSTEM_ERROR, ResultState.RESULT_READY,
                                   ErrorType.ID_DUPLICATE_FOUND, '')
                print("FPSystem-->add_part finished. (ID duplicate Error)\n")
                res = {
                    'PartIDsOfDuplicates': str([part.part_id for part in fp_duplicates].append(
                        [part.part_id for part in id_duplicates])),
                }
                return res

            if len(fp_duplicates) > 0:
                print("The AddPart duplicate check found duplicates!")
                self.status.update(RunState.SYSTEM_ERROR, ResultState.RESULT_READY,
                                   ErrorType.FP_DUPLICATE_FOUND, '')
                print("FPSystem-->add_part finished. (FP duplicate error)\n")
                res = {
                    'PartIDsOfDuplicates': str([part.part_id for part in fp_duplicates].append(
                        [part.part_id for part in id_duplicates])),
                }
                return res

            # If target database does not exist, simply create it. (In a real Fingerprint system,
            # the database must exist, for example defined via ini file.)
            try:
                target_db = self.fp_databases[database_name]
            except KeyError:
                self.fp_databases[database_name] = set()
                target_db = self.fp_databases[database_name]

            # Finally add the fingerprint to the database.
            target_db.add(FpDatabaseEntry(new_fingerprint, part_id, batch_id, part_type))

            self.status.update(RunState.SYSTEM_READY, ResultState.RESULT_READY, ErrorType.NO_ERROR,
                               '')
            print("FP databases:\n ", "\n  ".join([f"{k}: {v}" for k, v in
                  self.fp_databases.items()]))
            print("FPSystem-->add_part finished. (Success)\n")
            res = {
                'PartIDsOfDuplicates': "",
            }
            return res

    def add_part_prior_info(self, *args):
        prior_info = {
            'ExpectedServiceExecutionDuration': self.duration_estimations['add_part'],  # ms
            'ServiceTriggerResult': 1,            # 1=accepted
            'ServiceResultMessage': "",
            'ServiceResultCode': 0,
        }
        return prior_info

    async def trace_part(self, database_name, ref_database_names, trace_all_databases, batch_ids,
                         trace_batchwise, part_types, trace_typewise):
        async with self.task_lock:
            print(f"FPSystem-->trace_part( {database_name}, {ref_database_names}, "
                  f"{trace_all_databases}, {batch_ids}, {trace_batchwise}, {part_types}, "
                  f"{trace_typewise} )")

            # Check system status.
            if not (self.status.run_state == RunState.SYSTEM_READY
                    and self.status.error_type == ErrorType.NO_ERROR):
                print("FPSystem-->trace_part not executed, system not ready or in error state. "
                      "Call ResetSystem first.\n")
                res = {
                    'PartIDsOfDuplicates': "",
                }
                return res

            # Acquire image delay simulation.
            self.status.update(RunState.ACQUIRING_IMAGE, ResultState.RESULT_UNDEFINED,
                               ErrorType.NO_ERROR, 'trace_part')
            await asyncio.sleep(self.duration_estimations['trace_part'] / 1000 * 0.4)  # 40%, sec

            # Convert the arguments ref_database_names, batch_ids and part_types, which are
            # passed as a string of format "aaa;bb;cccc".
            self.status.update(RunState.COMMAND_RUNNING, ResultState.RESULT_UNDEFINED,
                               ErrorType.NO_ERROR, 'trace_part')
            if len(batch_ids) != 0:
                batch_id_list = batch_ids.split(';')
            else:
                batch_id_list = []
            if len(part_types) != 0:
                part_type_list = part_types.split(';')
            else:
                part_type_list = []
            if len(ref_database_names) != 0:
                ref_db_name_list = ref_database_names.split(';')
            else:
                ref_db_name_list = []

            # Collect the databases to search in, keeping the assigned order.
            if database_name not in ref_db_name_list:
                ref_db_name_list.append(database_name)
            if trace_all_databases:
                for db_name in self.fp_databases.keys():
                    if db_name not in ref_db_name_list:
                        ref_db_name_list.append(db_name)

            for ref_db_name in ref_db_name_list:
                # Check if a datebase exists with the assigned name.
                try:
                    ref_db = self.fp_databases[ref_db_name]
                except KeyError:
                    if ref_db_name != database_name:  # database_name will be created if neccessary
                        print(f"Database {ref_db_name} cannot be searched. It does not exist.")
                    continue

                # Ignore all database entries with non-fitting batch_id and/or part_type.
                # Note!: The actual Fingerprint algorithm does not work this way, of course.
                candidates = []
                for fp_entry in ref_db:
                    if not ((trace_batchwise and fp_entry.batch_id not in batch_id_list) or
                            (trace_typewise and fp_entry.part_type not in part_type_list)):
                        candidates.append(fp_entry)
                if len(candidates) > 0:
                    x = randint(0, len(candidates) - 1)
                    fp_entry = candidates[x]
                    break
            else:
                # In none of the visited databases a fitting Fingerprint entry has been found.
                await asyncio.sleep(self.duration_estimations['trace_part'] / 1000 * 0.6)  # 60%,sec
                self.status.update(RunState.SYSTEM_READY, ResultState.RESULT_READY,
                                   ErrorType.NO_ERROR, '')

                print("FPSystem-->trace_part finished. (No part found)\n")
                res = {
                    'ServiceExecutionResult': 0,    # 0=success
                    'PartID': "",
                    'BatchID': "",
                    'PartType': "",
                    'CurrentConfidenceValue1': 0,
                    'CurrentConfidenceValue2': 0,
                    'AverageConfidenceValue1': 0,
                    'AverageConfidenceValue2': 0,
                }
                return res

            # A fitting Fingerprint entry has been found. Move it to the target database.
            # If target database does not exist, simply create it. (In a real Fingerprint system,
            # the database must exist, for example defined via ini file.)
            print(f"TracePart found part entry {fp_entry} in database '{ref_db_name}'!")
            ref_db.remove(fp_entry)
            try:
                self.fp_databases[database_name].add(fp_entry)
            except KeyError:
                self.fp_databases[database_name] = set()
                self.fp_databases[database_name].add(fp_entry)
                print(f"Found part entry was moved to newly created target database "
                      f"{database_name}. Previously the database did not exist.")

            await asyncio.sleep(self.duration_estimations['trace_part'] / 1000 * 0.6)  # 60%, sec

            self.status.update(RunState.SYSTEM_READY, ResultState.RESULT_READY, ErrorType.NO_ERROR,
                               '')
            print("FPSystem-->trace_part finished. (Part found)\n")
            res = {
                'ServiceExecutionResult': 0,    # 0=success
                'PartID': fp_entry.part_id,
                'BatchID': fp_entry.batch_id,
                'PartType': fp_entry.part_type,
                'CurrentConfidenceValue1': 99,
                'CurrentConfidenceValue2': 100,
                'AverageConfidenceValue1': 97,
                'AverageConfidenceValue2': 98,
            }
            return res

    def trace_part_prior_info(self, *args):
        prior_info = {
            'ExpectedServiceExecutionDuration': self.duration_estimations['trace_part'],  # ms
            'ServiceTriggerResult': 1,            # 1=accepted
            'ServiceResultMessage': "",
            'ServiceResultCode': 0,
        }
        return prior_info
