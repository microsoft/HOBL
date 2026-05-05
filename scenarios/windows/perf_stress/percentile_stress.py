# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import os
import time
import argparse

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

import multiprocessing as mp
import numpy as np
import psutil

TARGET_CPU = 75  # percent
TIME_SLICE = 0.5  # seconds
MATRIX_SIZE = 2000
PRINT_EVERY = 10


def _format_bytes_per_sec(value: float) -> str:
    if value < 1024:
        return f"{value:.0f} B/s"
    if value < 1024 ** 2:
        return f"{value / 1024:.1f} KB/s"
    if value < 1024 ** 3:
        return f"{value / (1024 ** 2):.1f} MB/s"
    return f"{value / (1024 ** 3):.2f} GB/s"


def _system_metrics_snapshot(prev_disk, prev_net, prev_ts):
    now = time.time()
    elapsed = max(now - prev_ts, 1e-6)
    cpu = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    disk = psutil.disk_io_counters()
    net = psutil.net_io_counters()

    disk_read = (disk.read_bytes - prev_disk.read_bytes) / elapsed
    disk_write = (disk.write_bytes - prev_disk.write_bytes) / elapsed
    net_sent = (net.bytes_sent - prev_net.bytes_sent) / elapsed
    net_recv = (net.bytes_recv - prev_net.bytes_recv) / elapsed

    return (
        cpu,
        mem.percent,
        _format_bytes_per_sec(disk_read),
        _format_bytes_per_sec(disk_write),
        _format_bytes_per_sec(net_sent),
        _format_bytes_per_sec(net_recv),
        disk,
        net,
        now,
    )


def _busy_compute(rng, size):
    a = rng.random((size, size), dtype=np.float64)
    b = rng.random((size, size), dtype=np.float64)
    return np.dot(a, b)


def stress_worker(worker_id: int) -> None:
    print(f"[Worker {worker_id}] PID {os.getpid()} started")
    rng = np.random.default_rng(seed=4000 + worker_id)
    process = psutil.Process(os.getpid())

    prev_disk = psutil.disk_io_counters()
    prev_net = psutil.net_io_counters()
    prev_ts = time.time()

    tick = 0
    busy_target = TIME_SLICE * (TARGET_CPU / 100)
    while True:
        tick += 1
        slice_start = time.time()

        while (time.time() - slice_start) < busy_target:
            _busy_compute(rng, MATRIX_SIZE)

        sleep_time = TIME_SLICE - (time.time() - slice_start)
        if sleep_time > 0:
            time.sleep(sleep_time)

        if tick % PRINT_EVERY == 0:
            mem_mb = process.memory_info().rss / (1024 ** 2)
            msg = f"[Worker {worker_id}] ProcMem={mem_mb:.1f} MB"

            if worker_id == 0:
                (
                    cpu,
                    mem_pct,
                    disk_read,
                    disk_write,
                    net_sent,
                    net_recv,
                    prev_disk,
                    prev_net,
                    prev_ts,
                ) = _system_metrics_snapshot(prev_disk, prev_net, prev_ts)

                msg += (
                    " | "
                    f"CPU={cpu:.0f}% Mem={mem_pct:.0f}% "
                    f"Disk(R/W)={disk_read}/{disk_write} "
                    f"Net(S/R)={net_sent}/{net_recv}"
                )

            print(msg)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Background CPU stress load generator")
    parser.add_argument("--target-cpu", type=int, choices=[25, 50, 65, 75, 85], default=75)
    args = parser.parse_args()

    TARGET_CPU = int(args.target_cpu)
    WORKERS = max(1, int((os.cpu_count() or 1) * (TARGET_CPU / 100)))
    load_label = {25: "LOW", 50: "MEDIUM", 65: "MEDIUM-HIGH", 75: "HIGH", 85: "VERY-HIGH"}[TARGET_CPU]

    mp.freeze_support()
    print(f"Background stress {load_label} | Target CPU {TARGET_CPU}% | Workers {WORKERS}")
    print("Press Ctrl+C to stop\n")

    processes = []
    try:
        for w in range(WORKERS):
            p = mp.Process(target=stress_worker, args=(w,))
            p.start()
            processes.append(p)

        for p in processes:
            p.join()

    except KeyboardInterrupt:
        print("\nStopping load...")
        for p in processes:
            p.terminate()
