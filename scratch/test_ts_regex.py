import re

line_str = '2026-09-16T08:52:59Z {"severity":"DEBUG","logger":"security_service","service":"security_service","instance":"security-5","pod":"security-c548","region":"ap-south-1","trace_id":"tr-9028396","resource_id":"audit_record_4902","event":"audit_record_read_completed","integrity_check":"passed","rows":"1"}'
ts_match = re.search(r"^\s*([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z)", line_str)
print("Matched timestamp:", ts_match.group(1) if ts_match else None)
