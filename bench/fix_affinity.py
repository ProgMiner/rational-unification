#!/usr/bin/env python3
"""
Script corrects CPU affinity of processes that are not children of a specified PID.
If a process does not have the given PID in its parent tree (argument 1) and its affinity
includes the specified CPU number (argument 2), this CPU is removed from affinity.

Usage (usually as root):
    ./fix_affinity.py <excluded_parent_pid> <cpu_to_remove>
"""

import sys
import psutil


def has_ancestor(proc, target_pid):
    """
    Traverses up the parent process tree (ppid) and checks if target_pid is among them.
    Returns True if target_pid is found or if the chain cannot be verified (error).
    Returns False if init (pid 1) is reached and target_pid is not encountered.
    """

    while proc:
        if proc.pid == target_pid:
            return True

        try:
            ppid = proc.ppid()

            if ppid == 0:
                proc = None
            else:
                proc = psutil.Process(ppid)

        except Exception as e:
            print(e)
            return True

    return False


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <excluded_parent_pid> <cpu_to_remove>")
        sys.exit(1)

    try:
        excluded_pid = int(sys.argv[1])
        cpu_to_remove = int(sys.argv[2])
    except ValueError:
        print("Arguments must be integers (PID and CPU number).")
        sys.exit(1)

    for proc in psutil.process_iter(['pid', 'ppid']):
        try:
            pid = proc.pid

            if has_ancestor(proc, excluded_pid):
                continue

            try:
                current_affinity = proc.cpu_affinity()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

            if cpu_to_remove in current_affinity:
                new_affinity = [c for c in current_affinity if c != cpu_to_remove]

                if not new_affinity:
                    # print(f"Warning: removing CPU {cpu_to_remove} from PID {pid} "
                    #       f"would result in empty affinity. Skipping.")
                    continue

                try:
                    proc.cpu_affinity(new_affinity)
                    print(f"PID {pid}: removed CPU {cpu_to_remove}, "
                          f"new affinity = {new_affinity}")
                except Exception as e:
                    # print(f"Failed to set affinity for PID {pid}: {e}")
                    pass

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


if __name__ == "__main__":
    main()
