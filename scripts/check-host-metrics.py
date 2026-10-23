#!/usr/bin/env python3
"""Alloy의 측정값을 실행 중인 Linux 호스트와 비교합니다. 상태를 변경하지 않습니다."""
import argparse
import math
import re
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--url", default="http://127.0.0.1:19100/api/v0/component/prometheus.exporter.unix.host/metrics")
args = parser.parse_args()
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open(args.url, timeout=15) as response:
    lines = response.read(16 * 1024 * 1024).decode().splitlines()

def samples(name, **wanted):
    result = []
    for line in lines:
        match = re.fullmatch(r"([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(.*)\})?\s+(\S+)(?:\s+\S+)?", line)
        if not match or match[1] != name:
            continue
        labels = dict(re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)="([^"]*)"', match[2] or ""))
        if all(labels.get(key) == value for key, value in wanted.items()):
            value = float(match[3])
            if not math.isfinite(value):
                raise SystemExit("유효하지 않은 수치: " + name)
            result.append((labels, value))
    if not result:
        raise SystemExit("필수 호스트 지표 없음: " + name)
    return result

def single(name, **labels):
    result = samples(name, **labels)
    if len(result) != 1:
        raise SystemExit("지표가 단일 값이 아님: " + name)
    return result[0][1]

def check(ok, message):
    if not ok:
        raise SystemExit("검증 실패: " + message)
    print("확인: " + message)

host_cpus = {line.split()[0][3:] for line in Path("/proc/stat").read_text().splitlines()
             if re.match(r"cpu[0-9]+\s", line)}
metric_cpus = {labels["cpu"] for labels, _ in samples("node_cpu_seconds_total", mode="idle")}
check(host_cpus == metric_cpus, "CPU 식별자와 개수")

memory = {line.split(":")[0]: int(line.split()[1]) * 1024
          for line in Path("/proc/meminfo").read_text().splitlines()
          if line.startswith(("MemTotal:", "MemAvailable:"))}
check(single("node_memory_MemTotal_bytes") == memory["MemTotal"], "호스트 전체 메모리")
check(abs(single("node_memory_MemAvailable_bytes") - memory["MemAvailable"]) <
      max(128 * 1024 * 1024, memory["MemTotal"] * 0.05), "호스트 가용 메모리 허용 오차")

import os
disk = os.statvfs("/")
check(single("node_filesystem_size_bytes", mountpoint="/") ==
      disk.f_blocks * disk.f_frsize, "호스트 루트 파일시스템 크기")
check(abs(single("node_filesystem_avail_bytes", mountpoint="/") -
          disk.f_bavail * disk.f_frsize) < max(128 * 1024 * 1024, disk.f_blocks * disk.f_frsize * 0.02),
      "호스트 루트 파일시스템 가용 공간")

host_devices = {line.split(":")[0].strip() for line in Path("/proc/net/dev").read_text().splitlines()
                if ":" in line} - {"lo"}
metric_devices = {labels["device"] for labels, _ in samples("node_network_receive_bytes_total")}
check(bool(host_devices) and host_devices <= metric_devices, "호스트 네트워크 인터페이스")
for collector in ("cpu", "meminfo", "filesystem", "netdev"):
    check(single("node_scrape_collector_success", collector=collector) == 1,
          "수집 성공: " + collector)
print("ALLOY_HOST_METRICS_VERIFIED")
