#!/usr/bin/env python3
"""
Скрипт корректирует CPU affinity процессов, не являющихся потомками указанного PID.
Если процесс не имеет в дереве родителей заданный PID (аргумент 1), и его affinity
включает указанный номер CPU (аргумент 2), этот CPU удаляется из affinity.

Запуск (обычно от root):
    python script.py <excluded_parent_pid> <cpu_to_remove>
"""

import sys
import psutil


def has_ancestor(proc, target_pid):
    """
    Поднимается вверх по дереву родителей (ppid) и проверяет, есть ли среди них target_pid.
    Возвращает True, если target_pid найден или если проверить цепочку невозможно (ошибка).
    Возвращает False, если достигнут init (pid 1) и target_pid не встретился.
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
