"""Pure candidate adapter for already fetched Prometheus instant vectors.

No network, file publication, dashboard probe, or operational trust decision.
"""
from datetime import datetime, timezone
from math import isfinite


ROLES = ('service', 'monitoring')
METRICS = ('cpu', 'memory', 'disk')


class InvalidEvidence(ValueError):
    pass


def number(value):
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise InvalidEvidence('invalid numeric sample') from exc
    if not isfinite(result):
        raise InvalidEvidence('nonfinite sample')
    return result


def unique(rows, instance, label=None, expected=None):
    matches = [row for row in rows if row.get('metric', {}).get('instance') == instance
               and (label is None or row.get('metric', {}).get(label) == expected)]
    if len(matches) != 1:
        raise InvalidEvidence('missing or duplicate raw series')
    return matches[0]


def labels_for(row, role, instance, disk=False, idle=False):
    labels = row.get('metric', {})
    if (labels.get('job'), labels.get('server_role'), labels.get('instance')) != ('ec2-node', role, instance):
        raise InvalidEvidence('raw series identity mismatch')
    if idle and (labels.get('mode') != 'idle' or labels.get('cpu') is None):
        raise InvalidEvidence('invalid idle cpu series')
    if disk and (labels.get('mountpoint') != '/' or not labels.get('device')
                 or not labels.get('fstype') or labels['fstype'] in ('tmpfs', 'overlay')):
        raise InvalidEvidence('not a host root filesystem series')
    return labels


def paired(vectors, key, role, instance, disk=False):
    value = unique(vectors[key], instance)
    stamp = unique(vectors[key + '_time'], instance)
    left = labels_for(value, role, instance, disk=disk)
    right = labels_for(stamp, role, instance, disk=disk)
    # timestamp(raw) can drop __name__; all remaining source labels must match.
    if {k: v for k, v in left.items() if k != '__name__'} != {k: v for k, v in right.items() if k != '__name__'}:
        raise InvalidEvidence('value and source time labels differ')
    return value, stamp


def sample(row):
    try:
        return number(row['value'][1])
    except (KeyError, IndexError, TypeError) as exc:
        raise InvalidEvidence('invalid vector row') from exc


def source_time(row, now, max_age, future):
    stamp = sample(row)  # timestamp(raw_metric) yields source time as value[1]
    if stamp < now - max_age or stamp > now + future:
        raise InvalidEvidence('stale or future source sample')
    return stamp


def iso(stamp):
    return datetime.fromtimestamp(stamp, timezone.utc).isoformat().replace('+00:00', 'Z')


def build_snapshot(vectors, now, max_age, future, snapshot_id, dashboard_ok):
    """Validate unaggregated role/instance and per-input source times.

    Required keys: up, up_time, cpu_rate, cpu_time, memory_available, memory_total,
    memory_available_time, memory_total_time, disk_available, disk_size,
    disk_available_time, disk_size_time. CPU rate is grouped by instance;
    cpu_time contains one timestamp(raw idle counter) per cpu core.
    """
    if not all(type(value) in (int, float) and isfinite(value)
               for value in (now, max_age, future)) or not (max_age > 0 and future >= 0):
        raise InvalidEvidence('invalid clock policy')
    if dashboard_ok is not True or not isinstance(snapshot_id, str) or not snapshot_id:
        raise InvalidEvidence('dashboard evidence or snapshot id missing')
    try:
        up = vectors['up']
        if len(up) != 2 or len(vectors['up_time']) != 2:
            raise InvalidEvidence('expected exactly two raw up series')
        mapping = {}
        for row in up:
            labels = row['metric']
            role, instance = labels.get('server_role'), labels.get('instance')
            if role not in ROLES or not instance or role in mapping or instance in mapping.values():
                raise InvalidEvidence('ambiguous role or instance')
            if labels.get('job') != 'ec2-node' or sample(row) != 1:
                raise InvalidEvidence('host scrape failed')
            up_stamp = unique(vectors['up_time'], instance)
            if {k: v for k, v in labels_for(up_stamp, role, instance).items() if k != '__name__'} != {k: v for k, v in labels.items() if k != '__name__'}:
                raise InvalidEvidence('up and up_time labels differ')
            source_time(up_stamp, now, max_age, future)
            mapping[role] = instance
        if set(mapping) != set(ROLES):
            raise InvalidEvidence('role missing')
        hosts = {}
        for role, instance in mapping.items():
            idle = [row for row in vectors['cpu_time'] if row.get('metric', {}).get('instance') == instance]
            cores = [row.get('metric', {}).get('cpu') for row in idle]
            if not cores or None in cores or len(set(cores)) != len(cores):
                raise InvalidEvidence('missing or duplicate cpu core')
            for row in idle:
                labels_for(row, role, instance, idle=True)
            cpu_time = min(source_time(row, now, max_age, future) for row in idle)
            rate_row = unique(vectors['cpu_rate'], instance)
            labels_for(rate_row, role, instance)
            rate = sample(rate_row)
            if not 0 <= rate <= 1:
                raise InvalidEvidence('invalid cpu idle rate')
            host = {'instance': instance, 'up': True,
                    'cpu': {'pct': 100 * (1 - rate), 'sample_at_utc': iso(cpu_time)}}
            for name, available_key, total_key in (
                ('memory', 'memory_available', 'memory_total'),
                ('disk', 'disk_available', 'disk_size'),
            ):
                disk = name == 'disk'
                available_row, available_stamp = paired(vectors, available_key, role, instance, disk=disk)
                total_row, total_stamp = paired(vectors, total_key, role, instance, disk=disk)
                if disk and {k: available_row['metric'].get(k) for k in ('device', 'fstype', 'mountpoint')} != {k: total_row['metric'].get(k) for k in ('device', 'fstype', 'mountpoint')}:
                    raise InvalidEvidence('filesystem size and available labels differ')
                available = sample(available_row)
                total = sample(total_row)
                if total <= 0 or available < 0 or available > total:
                    raise InvalidEvidence('invalid capacity')
                times = [source_time(row, now, max_age, future)
                         for row in (available_stamp, total_stamp)]
                host[name] = {'pct': 100 * (1 - available / total),
                              'sample_at_utc': iso(min(times))}
            hosts[role] = host
        return {'schema_version': 'dual-host-health/v0.2-candidate',
                'snapshot_id': snapshot_id, 'generated_at_utc': iso(now),
                'source': 'prometheus', 'dashboard_ok': True, 'hosts': hosts}
    except (KeyError, TypeError, AttributeError, IndexError) as exc:
        raise InvalidEvidence('incomplete evidence') from exc
