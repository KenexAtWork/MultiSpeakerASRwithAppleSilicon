#!/usr/bin/env python3
"""計算 benchmark 平均值並附加到 CSV"""
import csv
from collections import defaultdict

INPUT = "asr/benchmark_results/benchmark_final.csv"

rows = []
with open(INPUT) as f:
    for r in csv.DictReader(f):
        rows.append(r)

groups = defaultdict(list)
for r in rows:
    groups[(r['file'], r['duration'], r['mode'])].append(r)

with open(INPUT, 'a') as f:
    f.write('\nfile,duration,mode,run,asr_sec,diarization_sec,total_sec,asr_realtime_x,diarization_realtime_x,overall_realtime_x\n')
    for (file, duration, mode), items in sorted(groups.items()):
        n = len(items)
        avg_asr = sum(float(r['asr_sec']) for r in items) / n
        avg_diar = sum(float(r['diarization_sec']) for r in items) / n
        avg_total = sum(float(r['total_sec']) for r in items) / n
        avg_asr_x = sum(float(r['asr_realtime_x']) for r in items) / n
        avg_diar_x = sum(float(r['diarization_realtime_x']) for r in items) / n
        avg_overall_x = sum(float(r['overall_realtime_x']) for r in items) / n
        f.write(f'{file},{duration},{mode},AVG({n}),{avg_asr:.1f},{avg_diar:.1f},{avg_total:.1f},{avg_asr_x:.2f},{avg_diar_x:.2f},{avg_overall_x:.2f}\n')

print("✓ 平均值已附加到", INPUT)
