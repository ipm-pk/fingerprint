# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2024 Fraunhofer IPM <support.fingerprint@ipm.fraunhofer.de>
#
# SPDX-License-Identifier: MIT

"""The OPCUA interface of Track & Trace Fingerprint systems. Python implementation is based on
the 'asyncua' module, which wraps Open62541 (C code).
Server settings and OPCUA interface variables are initialized from config file.
OPCUA interface services are connected via corresponding name to methods in the fp_system instance
that has been loaded.
"""

__version__ = 1.00
# Nodeset: r023,024

import asyncio
from asyncua import Server, ua, uamethod
from configparser import ConfigParser
from enum import Enum
import logging
from pathlib import Path


CURR_FILE_PATH = Path(__file__).parent
OPCUA_CONFIG_PATH = CURR_FILE_PATH / 'fp_opcua.ini'


class ConfigSection(Enum):
    DESCR = 'DESCRIPTION'
    NODES = 'NODESETS'
    # CAPABILITIES = 'CAPABILITIES'
    # PROPERTIES = 'PROPERTIES'
    STATE = 'STATE'


def camel_to_snake(s):
    """Converts CamelCase to snake_case (without additional lib)."""
    return ''.join(['_' + c.lower() if c.isupper() else c for c in s]).lstrip('_')


def snake_to_camel(s):
    """Converts snake_case to CamelCase (without additional lib)."""
    return ''.join(part.capitalize() for part in s.split('_'))


def dict_to_attribs(self, dict_, obj):
    """Write each dict_ item as attribute to obj."""
    for name, val in dict_:
        setattr(obj, name, val)
    return


class FpOpcuaServer:
    def __init__(self):
        """Create a quite empty FpOpcuaServer instance."""
        # Enable logging.
        global FpOpcuaLogger
        # logging.basicConfig(level=logging.DEBUG)
        FpOpcuaLogger = logging.Logger('fp_opcua')
        my_handler = logging.StreamHandler()
        FpOpcuaLogger.addHandler(my_handler)
        FpOpcuaLogger.setLevel(logging.INFO)

        # Create plain OpcUa server.
        self.server = None

        # FP Opcua server management containers.
        self.variables = {}         # storage for capability and property nodes.
        self.event_gens = {}        # storage for prepared events that can then be easily used.
        self.tasks_running = set()  # prevent early garbage collection of concurrent tasks.

        self.fp_system = None

    @staticmethod
    async def read_config(path):
        """Read in the config file at 'path' and return the ConfigParser object."""
        config = ConfigParser()
        config.optionxform = str    # disable preprocessing to lowercase
        visited = config.read(path)
        if len(visited) == 0:
            FpOpcuaLogger.error("ERROR: Reading config file failed!")
        return config

    async def set_up_server(self):
        """Create and initialize the asyncua OPCUA server component."""
        self.server = Server()
        await self.server.init()
        # self.server.disable_clock()  # For debugging

        # Read and set general server settings from config.
        config = await self.read_config(OPCUA_CONFIG_PATH)
        server_name = config.get(ConfigSection.DESCR.value, 'server_name', fallback='unnamed')
        opcua_host = config.get(ConfigSection.DESCR.value, 'opcua_host', fallback='127.0.0.1')
        opcua_port = config.getint(ConfigSection.DESCR.value, 'opcua_port', fallback=4840)
        app_uri = config.get(ConfigSection.DESCR.value, 'app_uri')

        self.server.set_endpoint(f'opc.tcp://{opcua_host}:{opcua_port}/freeopcua/server/')
        self.server.set_server_name(server_name)
        await self.server.set_application_uri(app_uri)
        return

    async def bind_sensor(self, fp_system):
        self.fp_system = fp_system

    async def load_nodesets(self):
        """Load the nodesets listed in the config file and provided as xml files.
            The nodesets define the interface of the opcua server."""
        # Get "objects" node. Instantiating object nodes will create them below "objects" node.
        objects = self.server.get_objects_node()

        # Load server nodeset: Import the nodes from the xml files defined in the config.
        config = await self.read_config(OPCUA_CONFIG_PATH)
        for nodeset_name, nodeset_path in config.items(ConfigSection.NODES.value):
            p = CURR_FILE_PATH/Path(nodeset_path)
            _ = await self.server.import_xml(p.absolute())
            FpOpcuaLogger.debug(f'DEBUG: Loaded nodeset "{nodeset_name}": {_}.')

        # Get correct namespace indices.
        namespaces = await self.server.get_namespace_array()
        FpOpcuaLogger.info(f"INFO: Loaded namespaces: {namespaces}.")
        self.idx_swap = namespaces.index("http://common.swap.fraunhofer.de")
        self.idx_fp = namespaces.index("http://fingerprint.swap.ipm.fraunhofer.de")
        self.loaded_type_definitions = await self.server.load_data_type_definitions()
        FpOpcuaLogger.debug(f"DEBUG: Loaded data type definitions: {self.loaded_type_definitions}.")

        # Get the type node FingerprintModule and create an instance.
        root = self.server.get_root_node()
        FingerprintModuleTypeNode = await root.get_child(
            [
                "0:Types",
                "0:ObjectTypes",
                "0:BaseObjectType",
                f"{self.idx_swap}:BaseModuleType",
                f"{self.idx_fp}:FingerprintModuleType",
            ]
        )
        self.FingerprintModuleObj = await objects.add_object(self.idx_fp, "FingerprintModule",
                                                             FingerprintModuleTypeNode)

    async def initialize_nodeset(self):
        await self.init_variables()
        await self.link_services()
        await self.init_threads()

    async def init_variables(self):
        """Initialize all opcua interface SWAP-IT variables (= in 'Capabilities', 'Properties',
            'State') from config file."""
        config = await self.read_config(OPCUA_CONFIG_PATH)

        # todo: moved 'state' var outside. Apply "init_variable" here too, then re-merge.
        for container_name in ('Capabilities', 'Properties'):
            var_container = await self.FingerprintModuleObj.get_child(f"{self.idx_swap}:"
                                                                      f"{container_name}")
            for var_node in await var_container.get_variables():
                # All variables of 'Capabilities', 'Properties' and 'State' shall be read-only
                # for clients.
                await var_node.set_read_only()

                # Init type and value.
                try:
                    await self.init_variable(container_name, var_node, config)
                except ua.UaError as e:
                    FpOpcuaLogger.error(f"Error: Could not initialize {container_name}-{var_node}"
                                        f": {e}")
                    return

        # todo: temporary separation. see todo above (re-merge).
        for container_name in ('State',):
            var_container = await self.FingerprintModuleObj.get_child(f"{self.idx_swap}:"
                                                                      f"{container_name}")
            for var_node in await var_container.get_variables():
                await var_node.set_read_only()

                # Init value.
                var_name = (await var_node.read_browse_name()).Name
                self.variables[var_name] = var_node
                val = config.get(ConfigSection.STATE.value, var_name)
                await self.update_state({var_name: val})
        return

    async def init_variable(self, container_name, var_node, config):
        """Set the variable's initial value and use the initial type to define the type in
            general. Also set the access rights (for clients). """
        var_name = (await var_node.read_browse_name()).Name

        # Make node directly accessible via dict.
        self.variables[var_name] = var_node

        # Search for a config val, uppercase and capitalized. Get it as string.
        init_val = config.get(container_name.upper(), var_name, fallback=None)    # set raw=True?
        if init_val is None:
            init_val = config.get(container_name.capitalize(), var_name, fallback=None)
            if init_val is None:
                FpOpcuaLogger.warning(f"WARN: No entry in config file to initialize "
                                      f"{container_name}-{var_name}.")
                return

        # todo: Reverse: Look up type of variable in xml definition, then try suitable conversion.
        # Convert init value: string to correct type.
        # handle decimal, float, boolean, none, string; scalars and 1d arrays
        val_array = init_val.split(',')

        if val_array[0].isdecimal():
            type_ = int
            ua_type = ua.uatypes.Int16
        elif val_array[0].lower() in ('false', 'true'):
            type_ = bool
            ua_type = ua.uatypes.Boolean
        else:
            try:
                float(val_array[0])
            except ValueError:
                type_ = str
                ua_type = ua.uatypes.String
            else:
                type_ = float
                ua_type = ua.uatypes.Float

        if len(val_array) > 1:
            vals_typed = [type_(v.strip('"')) for v in val_array]
            dims = len(vals_typed)
            ua_variant = ua.Variant(vals_typed, ua_type, [dims])
        else:
            vals_typed = type_(val_array[0].strip('"'))
            dims = None
            ua_variant = ua.Variant(vals_typed, ua_type)
        FpOpcuaLogger.debug(f"DEBUG: {vals_typed} | {dims} dim | {ua_type}.")

        # Set attribute node to typed initial value; with type and dimensions handed on.
        FpOpcuaLogger.info(f"INFO: Initializing {container_name}-{var_name} to '{vals_typed}'...")
        try:
            ua_val = ua.DataValue(ua_variant)
            await self.server.write_attribute_value(var_node.nodeid, ua_val)
#            await self.server.write_attribute_value(var_node.nodeid, ua.DataValue(vals_typed))
        except ua.UaError:
            FpOpcuaLogger.warning(f"WARN: Initializing {container_name}-{var_name} -/-> "
                                  f"{vals_typed} failed!")

    async def link_services(self):
        """Link all services (nodes) to methods of the same name but snake case and prefixed with
            'service_backend_'. Also prepare the ServiceFinishedEventType for the service, to
            realize the immediate service response.
            Throws: ua.UaError if loaded xml nodesets would violate SWAP IT architecture.
        """
        # From the loaded opcua interface, get the nodes of the SWAP-IT services, the sync and
        # async result data types, and service finished event types; for the next steps.
        services_node = await self.FingerprintModuleObj.get_child(f'{self.idx_swap}:Services')
        root = self.server.get_root_node()
        sync_result_type = await root.get_child(
            [
                "0:Types",
                "0:DataTypes",
                "0:BaseDataType",
                "0:Structure",
                f"{self.idx_swap}:ServiceExecutionResultDataType",
                f"{self.idx_swap}:ServiceExecutionSyncResultDataType",
            ]
        )
        async_result_type = await root.get_child(
            [
                "0:Types",
                "0:DataTypes",
                "0:BaseDataType",
                "0:Structure",
                f"{self.idx_swap}:ServiceExecutionResultDataType",
                f"{self.idx_swap}:ServiceExecutionAsyncResultDataType",
            ]
        )
        s_f_event_type = await root.get_child(
            [
                "0:Types",
                "0:EventTypes",
                "0:BaseEventType",
                f"{self.idx_swap}:ServiceFinishedEventType",
            ]
        )

        # Loop over the services.
        service_nodes = await services_node.get_methods()
        for service_node in service_nodes:
            service_name = (await service_node.read_browse_name()).Name

            # Ignore services handled by the SWAP-IT architecture.
            if service_name in ('register', 'unregister'):
                continue

            # Get the FpSystem's functionality methods to connect to.
            fp_system_method_name = camel_to_snake(service_name)
            try:
                fp_system_func = getattr(self.fp_system, fp_system_method_name)
            except AttributeError:
                FpOpcuaLogger.error(f"ERROR: No method {fp_system_method_name} found for service "
                                    f"{service_name}.")
                continue
            fp_system_prior_info_func = getattr(self.fp_system,
                                                f'{fp_system_method_name}_prior_info', None)

            # Find out if the service is defined to return immediately (sync) or delayed (async &
            # event). A corresponding sync result data type or a service finished event type
            # reveals this.
            try:
                service_event_type = await s_f_event_type.get_child(
                    f"{self.idx_fp}:{service_name}ServiceFinishedEventType",
                )
                returns_async = True
            except ua.UaError:
                try:
                    service_result_type = await sync_result_type.get_child(
                        f"{self.idx_fp}:{service_name}ServiceExecutionSyncResultDataType",
                    )
                    returns_async = False
                except ua.UaError as e:
                    FpOpcuaLogger.error(f"ERROR: Service {service_name} could not be linked since"
                                        f" neither EventType '{service_name}"
                                        f"ServiceFinishedEventType' nor DataType '{service_name}"
                                        f"ServiceExecutionSyncResultDataType' exists: {e}")
                    continue

            if returns_async:
                # Get the event generator for the service that returns delayed. Set it to create
                # the event inside the FingerprintModule object.
                self.event_gens[service_name] = await self.server.get_event_generator(
                    service_event_type, self.FingerprintModuleObj)

                # All services that return delayed use the same async result type.
                async_result_type_name = (await async_result_type.read_browse_name()).Name
                try:
                    result_type = self.loaded_type_definitions[async_result_type_name]
                    # print( type(async_result_type), type(result_type) )
                except KeyError:
                    FpOpcuaLogger.error(f"ERROR: General DataType {async_result_type} not found "
                                        f"for async service {service_name} in "
                                        f"{self.loaded_type_definitions}.")
                    continue
            else:
                # All services that return immediately use their own sync result type.
                # FpOpcuaLogger.debug("Debug:", await self.server.load_data_type_definitions(
                #    node=sync_result_type))
                service_result_type_name = (await service_result_type.read_browse_name()).Name
                try:
                    result_type = self.loaded_type_definitions[service_result_type_name]
                except KeyError:
                    FpOpcuaLogger.warning(f"WARN: Specific DataType {service_result_type_name} "
                                          f"not found for sync service {service_name}.")
                    # FpOpcuaLogger.error(f"ERROR: Specific DataType {service_result_type_name} "
                    #                     f"not found for sync service {service_name} in "
                    #                     f"{self.loaded_type_definitions}.")  #todo disabled
                    continue

            # Wrap the non-opcua fp system's func to make it return sync or async.
            backend_method = await self.make_it_service_responding(service_name, fp_system_func,
                                                                   fp_system_prior_info_func,
                                                                   result_type, returns_async)
            backend_method_name = f'service_backend_{camel_to_snake(service_name)}'
            setattr(self, backend_method_name, backend_method)

            # Link the service to the new wrapped func.
            try:
                self.server.link_method(service_node, backend_method)
            except (AttributeError, ua.UaError) as e:
                FpOpcuaLogger.error(f"ERROR: Could not link {service_name} to self."
                                    f"{backend_method_name}: {e}")
                return
            FpOpcuaLogger.info(f"INFO: Linked service {service_name} to self.{backend_method_name} "
                               f"with core functionality {fp_system_func.__qualname__}.")

        return

    async def make_it_service_responding(self, service_name, func, func_prior_info,
                                         immediate_result_datatype, returns_async):
        """Wrap func so it can be linked to an opcua SWAP-IT service."""
        if returns_async:
            @uamethod
            async def service_responding_func(node_id, *input_args):
                """When linked to a service of the opcua interface, a call to the service will call
                    the func with parameters node_id and a list of inputs arguments."""
                FpOpcuaLogger.info(f"INFO: Service {service_name} request received. Returns "
                                   f"async: {returns_async}. Input args: {input_args}.")

                # Get prior info.
                if func_prior_info is None:
                    FpOpcuaLogger.warning("WARN: No method '[func]_prior_info' found for service"
                                          f" '{service_name}'.")
                    prior_info = {
                        'ExpectedServiceExecutionDuration': -1.0,
                        'ServiceTriggerResult': 1,
                        'ServiceResultMessage': "",
                        'ServiceResultCode': 1,
                    }
                else:
                    prior_info = dict(func_prior_info(*input_args))

                # For a delayed returning func, make it event triggering and call it in a new
                # thread.
                event_gen = self.event_gens[service_name]
                event_triggering_func = await self.make_it_event_triggering(func, event_gen)
                event_loop = asyncio.get_event_loop()
                task = event_loop.create_task(event_triggering_func(*input_args))
                self.tasks_running.add(task)
                task.add_done_callback(self.tasks_running.discard)
                await self.update_state(await self.fp_system._get_status())

                # Immedately return the prior info (without waiting for the thread).
                immediate_result = immediate_result_datatype(**prior_info)
                return ua.Variant(immediate_result, ua.VariantType.ExtensionObject)
            return service_responding_func

        else:
            @uamethod
            async def service_responding_func(node_id, *input_args):
                """When linked to a service of the opcua interface, a call to the service will call
                    the func with parameters node_id and a list of inputs arguments."""
                FpOpcuaLogger.info(f"INFO: Service {service_name} request received. Returns "
                                   f"async: {returns_async}. Input args: {input_args}.")

                # Get prior info.
                if func_prior_info is None:
                    FpOpcuaLogger.warning(f"WARN: No method '[func]_prior_info' found for service"
                                          f" '{service_name}'.")
                    prior_info = {}
                else:
                    prior_info = dict(func_prior_info(*input_args))

                # Call the sync returning func.
                sync_results = func(*input_args)
                prior_info.update(**sync_results)
                await self.update_state(await self.fp_system._get_status())
                immediate_result = immediate_result_datatype(**sync_results)
                return ua.Variant(immediate_result, ua.VariantType.ExtensionObject)
            return service_responding_func

    async def make_it_event_triggering(self, func, event_gen):
        """Wrap the func so its results are filled into an event that is finally triggered."""
        # @uamethod  Not an uamethod. Would cause error.
        async def event_triggering_func(*input_args):
            try:
                print("HERE:", type(func), input_args)
                res = await func(*input_args)
            except Exception as e:
                raise e                                 # todo: debug raise
                event_gen.ServiceExecutionResult = 1    # 1==error
            else:
                event_gen.ServiceExecutionResult = 0    # 0==success
                for name, val in res.items():
                    try:
                        setattr(event_gen, name, val)
                    except Exception:  # todo: error impossible? Then use dict_to_attribs().
                        FpOpcuaLogger.info(f"INFO: FPSystem returned {name}={val}, which is not "
                                           "part of the opcua interface and thus not displayed.")
                        continue
                # Triggering the event generator means emitting the event.
                await event_gen.trigger()
            finally:
                await self.update_state(await self.fp_system._get_status())
        return event_triggering_func

    async def update_state(self, status):
        """Write the values of the assigned status dict to 'state' variables."""
        for state_var_name, val in status.items():
            if state_var_name in ('RunState', 'ResultState', 'ErrorType'):
                ua_val = ua.DataValue(ua.Variant(val, ua.VariantType.SByte))
            elif state_var_name in ('CurrentCommand'):
                ua_val = ua.DataValue(ua.Variant(val, ua.VariantType.String))
            else:
                continue
            await self.server.write_attribute_value(self.variables[state_var_name].nodeid, ua_val)
#        print("STATE:", ", ".join( [f"{k}={v}" for k, v in status.items()] ))

    async def periodic_state_update(self, interval=0.5):
        """Every interval seconds, update the state of the opcua interface from the FpSystem."""
        while True:
            await self.update_state(await self.fp_system._get_status())
            await asyncio.sleep(interval)

    async def init_threads(self):
        """Start sets of threads that work in the background."""
        event_loop = asyncio.get_event_loop()

        task = event_loop.create_task(self.periodic_state_update(0.25), name='auto_update_fp_state')
        self.tasks_running.add(task)
        task.add_done_callback(self.tasks_running.discard)
