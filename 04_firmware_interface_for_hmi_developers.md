# Firmware Interface for HMI Developers

## Purpose

Define the firmware-side contracts HMI must respect.

## Source Of Truth Files

- docs/firmware-data-flow.md
- app/prj.conf
- app/protos/state_control_msg.proto
- app/src/control/control_service.c
- app/src/zbus/state/state_udp_sender.c

## Ingress Contract, Control

- Transport: UDP
- Port: 30010
- Message type: Control protobuf
- Required fields used by actuation path:
  - control.effort.state.x
  - control.effort.state.y

## Egress Contract, State

- Transport: UDP
- Port: 30011
- Message type: State protobuf snapshot
- Snapshot built from merged partial updates on firmware side

## Merge Semantics That Affect HMI

Firmware merge accepts incoming field when:

- field missing in cache
- incoming stamp is newer
- incoming stamp equals cached stamp

HMI should treat identical stamp updates as valid latest value updates.

## SMP Management Contract

- Transport: MCUmgr SMP over UDP
- Port: 1337
- Groups in use:
  - OS
  - STAT
  - TASKSTAT
  - SHELL

## SMP Output Size Constraints

Current firmware settings constrain shell response size to fit safe UDP payload limits.

Operational implication:

- Long shell outputs may be truncated or fail with size-related errors
- HMI must show result robustly and avoid assuming infinite shell output stream

## Firmware Timing Expectations For HMI

Nominal producer rates documented in firmware data flow:

- IMU: 10 Hz
- Magnetometer: 5 Hz
- Distance: about 60 Hz
- Light: 2 Hz

HMI should not hardcode these values as strict guarantees.
