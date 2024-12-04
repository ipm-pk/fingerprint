# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2024 Fraunhofer IPM <support.fingerprint@ipm.fraunhofer.de>
#
# SPDX-License-Identifier: MIT

"""Execute an OPCUA server interface for Track & Trace Fingerprint systems. Multiple integration
levels, selectable via input argument, enable a stepwise integration of an OPCUA client (e.g. on a
PLC)."""

__version__ = 1.00


import argparse
import asyncio
from enum import Enum
import logging

from fp_opcua_server.fp_opcua_server import FpOpcuaServer


class IntegrationLevel(Enum):
    ECHO = 0
    MOCKUP = 1
    TCPIP = 2


async def run_opcua_server(opcua_server, sensor_system):
    await opcua_server.set_up_server()
    await opcua_server.bind_sensor(sensor_system)
    await opcua_server.load_nodesets()
    await opcua_server.initialize_nodeset()
    async with opcua_server.server:
        print("Fingerprint OPCUA server is listening...")
        while True:
            await asyncio.sleep(0.5)  # seconds
            # print([t.get_name() for t in opcua_server.tasks_running])    # debug info


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARN)

    parser = argparse.ArgumentParser(description='FingerprintInterface parameters.')
    parser.add_argument('integration_level', type=str, help='Level of Fingerprint integration: '
                        + str([e.value for e in IntegrationLevel]))
    parser.add_argument('-ip', '--host', type=str, required=False, default='localhost',
                        help='IP address or host name.')
    parser.add_argument('-p', '--port', type=int, required=False, default=50001, help='Port used '
                        'at the host.')
    parser.add_argument('-t', '--partner_type', type=str, required=False, choices=['reader',
                        'management'], default='reader', help='Fingerprint component type.')

    args = parser.parse_args()

    # Convert str via int or str to enum IntegrationLevel.
    try:
        level = IntegrationLevel(int(args.integration_level))
    except ValueError:
        try:
            level = IntegrationLevel[str(args.integration_level).upper()]
        except KeyError:
            raise SystemExit(f"Exit: '{args.integration_level}' is not an integration level.")

    logging.info(f"INFO: Integration level selected: {level}")

    # Select backend functionality for the Opcua server by instantiating an FP system class.
    fp_system_kwargs = {}
    if level == IntegrationLevel.ECHO:
        from fp_echo_system.fp_echo_system import FpEchoSystem
        sensor_system = FpEchoSystem()
    elif level == IntegrationLevel.MOCKUP:
        from fp_mockup_system.fp_mockup_system import FpMockupSystem
        sensor_system = FpMockupSystem()
    elif level == IntegrationLevel.TCPIP:
        raise NotImplementedError("TCP/IP level not yet available. Coming soon!")
        from fp_tcpip_system.fp_opcua_tcp_interface import FpTcpIpInterface, FpSystemType
        try:
            partner_type = FpSystemType[args.partner_type.upper()]
        except KeyError:
            raise SystemExit(f"Exit: '{args.partner_type}' is not in "
                             f"{[t.name for t in FpSystemType]}.")
        sensor_system = FpTcpIpInterface(host=args.host, port=args.port,
                                         partner_type=partner_type)
    else:
        raise SystemExit(f"Exit: Integration level '{level}' is out of range.")

    # Set up Opcua server and run it.
    opcua_server = FpOpcuaServer()
    try:
        asyncio.run(run_opcua_server(opcua_server, sensor_system))  # debugging: debug=True
    except KeyboardInterrupt:
        print("\nStopped by KeyboardInterrupt.")
    raise SystemExit('=== End of main ===')
