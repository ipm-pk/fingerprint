# Fingerprint OPC UA Interface

## Description
The Track & Trace Fingerprint technology developed at Fraunhofer IPM allows for unique identification of components -- marker-free, only based on the microstructures of the component's surface. It enables identification even in cases where boundary conditions inhibit marker-based approaches: For components with mostly functional surfaces, for components with a small available or disjoint surface area or when the cost of marking is not feasible for the application. Even tracing continuous materials like metal coils is possible.

In this repository, an OPC UA interface for Fingerprint systems is provided. Two simulation modes allow for setting up an OPC UA client without the need for the Fingerprint software or hardware.

The OPC UA interface has been implemented according to the SWAP IT architecture. Thus, a SWAP IT production automation system can integrate the Fingerprint sensor module dynamically into a production flow.

## Install
1. Download all files from the repository.
1. Install python >=3.10.
1. Install the required packages in requirements.txt.
1. Start the Fingerprint OPC UA server from a command prompt.
	- ```python fingerprint_interface.py <integration_level> ```
	- integration_level='echo': Activates only the OPC UA interface of a Fingerprint system. The functionality is reduced to logging the called method and the assigned arguments, as well as the simulation of status changes.
	- integration_level='mockup': Simulates the functionality of a Fingerprint system.
	- integration_level='tcpip': Connects the OPC UA to a running Fingerprint software instance.
1. Connect with an OPC UA client UI to examine the interface, <br>
set up a custom client solution, e. g. on a PLC, <br>
or let a SWAP IT client control the Fingerprint sensor system.

