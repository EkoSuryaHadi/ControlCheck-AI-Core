# Patched mppjs Linux converter

Upstream: https://github.com/byteink/mppjs
Upstream tag: v0.1.6
MPXJ version: 16.1.0

ControlCheck patch: the converter uses `org.mpxj.mpp.MPPReader`
directly and calls `setReadPresentationData(false)` before reading
the Microsoft Project file.

Purpose: ControlCheck imports schedule data only. Skipping Microsoft
Project presentation/view formatting prevents the known headless Linux
AWT failure for MPP files with saved Gantt Chart formatting while
preserving schedule tasks, resources, assignments, calendars and
relationships.

The native binary contains MPXJ and remains subject to the upstream
LGPL-2.1-or-later terms included in LICENSE and NOTICE.
