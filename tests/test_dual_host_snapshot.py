import copy
import importlib.util
from pathlib import Path
import unittest


path = Path(__file__).resolve().parents[1] / 'scripts/dual_host_snapshot.py'
spec = importlib.util.spec_from_file_location('dual_host_snapshot', path)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)

NOW = 1800000000.0


def row(instance, value, **labels):
    return {'metric': {'instance': instance, **labels}, 'value': [NOW, str(value)]}


def fixture():
    data = {'up': [], 'up_time': [], 'cpu_rate': [], 'cpu_time': []}
    for key in ('memory_available', 'memory_total', 'disk_available', 'disk_size'):
        data[key] = []
        data[key + '_time'] = []
    for role in ('service', 'monitoring'):
        data['up'].append(row(role, 1, job='ec2-node', server_role=role))
        data['up_time'].append(row(role, NOW - 3, job='ec2-node', server_role=role))
        data['cpu_rate'].append(row(role, 0.8, job='ec2-node', server_role=role))
        for cpu in ('0', '1'):
            data['cpu_time'].append(row(role, NOW - 3, cpu=cpu, mode='idle', job='ec2-node', server_role=role))
        for key, value in [('memory_available', 40), ('memory_total', 100),
                           ('disk_available', 70), ('disk_size', 100)]:
            labels={'job':'ec2-node','server_role':role}
            if key.startswith('disk'):
                labels.update(mountpoint='/',fstype='ext4',device='/dev/root')
            data[key].append(row(role, value, **labels))
            data[key + '_time'].append(row(role, NOW - 4, **labels))
    return data


class SnapshotTests(unittest.TestCase):
    def build(self, data):
        return adapter.build_snapshot(data, NOW, 15, 5, 'local-fixture-1', True)

    def test_two_hosts_and_oldest_input_source_time(self):
        data = fixture()
        data['memory_total_time'][0]['value'] = [NOW + 100, str(NOW - 10)]
        snapshot = self.build(data)
        self.assertEqual(set(snapshot['hosts']), {'service', 'monitoring'})
        self.assertEqual(snapshot['hosts']['service']['memory']['sample_at_utc'], adapter.iso(NOW - 10))
        self.assertAlmostEqual(snapshot['hosts']['service']['cpu']['pct'], 20)

    def test_duplicate_role_or_instance_fails(self):
        for change in ('role', 'instance'):
            data = fixture()
            data['up'][1]['metric']['server_role' if change == 'role' else 'instance'] = 'service'
            with self.assertRaises(adapter.InvalidEvidence):
                self.build(data)

    def test_duplicate_raw_metric_and_cpu_core_fail(self):
        for key in ('memory_total', 'disk_available_time', 'cpu_time'):
            data = fixture()
            data[key].append(copy.deepcopy(data[key][0]))
            with self.assertRaises(adapter.InvalidEvidence):
                self.build(data)

    def test_stale_future_missing_or_failed_input_fails_closed(self):
        for key, value in [('cpu_time', NOW - 16), ('memory_total_time', NOW + 6),
                           ('disk_size_time', 'NaN')]:
            data = fixture()
            data[key][0]['value'][1] = str(value)
            with self.assertRaises(adapter.InvalidEvidence):
                self.build(data)
        data = fixture()
        data['up'][0]['value'][1] = '0'
        with self.assertRaises(adapter.InvalidEvidence):
            self.build(data)
        data = fixture()
        data['up_time'][0]['value'][1] = str(NOW - 16)
        with self.assertRaises(adapter.InvalidEvidence):
            self.build(data)
        data = fixture()
        data['up'][0]['value'][0] = NOW
        data['up_time'][0]['value'][1] = str(NOW - 16)
        with self.assertRaises(adapter.InvalidEvidence):
            self.build(data)
        data = fixture()
        del data['memory_available']
        with self.assertRaises(adapter.InvalidEvidence):
            self.build(data)

    def test_invalid_capacity_rate_or_dashboard_fails(self):
        for key, value in [('disk_size', 0), ('memory_available', 101), ('cpu_rate', 1.2)]:
            data = fixture()
            data[key][0]['value'][1] = str(value)
            with self.assertRaises(adapter.InvalidEvidence):
                self.build(data)
        with self.assertRaises(adapter.InvalidEvidence):
            adapter.build_snapshot(fixture(), NOW, 15, 5, 'local-fixture-1', False)

    def test_bad_dashboard_policy_and_source_labels_rejected(self):
        for value in ('false', 1, [], {}):
            with self.assertRaises(adapter.InvalidEvidence):
                adapter.build_snapshot(fixture(), NOW, 15, 5, 'local-fixture-1', value)
        for age, future in [(float('inf'), 5), (15, float('inf')), ('15', 5)]:
            with self.assertRaises(adapter.InvalidEvidence):
                adapter.build_snapshot(fixture(), NOW, age, future, 'local-fixture-1', True)
        for key, label, value in [('memory_total', 'job', 'foreign-job'),
                                  ('cpu_rate', 'server_role', 'foreign-role'),
                                  ('disk_available', 'mountpoint', '/data'),
                                  ('disk_size_time', 'fstype', 'tmpfs'),
                                  ('cpu_time', 'mode', 'system'),
                                  ('up_time', 'server_role', 'monitoring')]:
            data = fixture()
            data[key][0]['metric'][label] = value
            with self.assertRaises(adapter.InvalidEvidence, msg=key):
                self.build(data)


if __name__ == '__main__':
    unittest.main()
