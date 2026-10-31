"""Guard candidate-only monitoring configuration against accidental drift."""
from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
MON = ROOT / 'monitoring'


class DualHostCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = yaml.safe_load((ROOT / 'tests/fixtures/prometheus.ec2.pre-dual-host.yaml').read_text())
        cls.canonical = yaml.safe_load((MON / 'prometheus.ec2.yaml').read_text())
        cls.candidate = yaml.safe_load((MON / 'prometheus.dual-host-candidate.yaml').read_text())
        cls.overlay = yaml.safe_load((MON / 'compose.monitoring-host-candidate.yaml').read_text())
        cls.operational_overlay = yaml.safe_load((MON / 'compose.monitoring-host.yaml').read_text())

    def test_canonical_config_preserves_the_deployed_dual_host_content(self):
        self.assertEqual(self.canonical, self.candidate)
        self.assertEqual((MON / 'prometheus.ec2.yaml').read_bytes(),
                         (MON / 'prometheus.dual-host-candidate.yaml').read_bytes())

    def test_operational_overlay_only_defines_host_exporter(self):
        self.assertEqual(set(self.operational_overlay['services']), {'monitoring-host-metrics'})
        self.assertEqual(self.operational_overlay['services']['monitoring-host-metrics'],
                         self.overlay['services']['monitoring-host-metrics'])
        self.assertEqual(self.operational_overlay['volumes'], self.overlay['volumes'])
        self.assertEqual(self.operational_overlay['networks'], self.overlay['networks'])

    def test_existing_prometheus_mount_still_uses_canonical_file(self):
        compose = yaml.safe_load((MON / 'compose.prometheus-only.yaml').read_text())
        self.assertIn('./monitoring/prometheus.ec2.yaml:/etc/prometheus/prometheus.yaml:ro',
                      compose['services']['prometheus']['volumes'])

    def test_only_node_scrape_job_changes(self):
        def without_node(config):
            return {**config, 'scrape_configs': [job for job in config['scrape_configs']
                                                 if job['job_name'] != 'ec2-node']}
        self.assertEqual(without_node(self.original), without_node(self.candidate))
        old_node = [job for job in self.original['scrape_configs'] if job['job_name'] == 'ec2-node']
        new_node = [job for job in self.candidate['scrape_configs'] if job['job_name'] == 'ec2-node']
        self.assertEqual(len(old_node), 1)
        self.assertEqual(len(new_node), 1)
        self.assertEqual({k: v for k, v in old_node[0].items() if k != 'static_configs'},
                         {k: v for k, v in new_node[0].items() if k != 'static_configs'})

    def test_service_target_preserved_and_roles_unique(self):
        old = next(job for job in self.original['scrape_configs'] if job['job_name'] == 'ec2-node')
        new = next(job for job in self.candidate['scrape_configs'] if job['job_name'] == 'ec2-node')
        old_targets = [target for group in old['static_configs'] for target in group['targets']]
        role_targets = [(group['labels']['server_role'], target)
                        for group in new['static_configs'] for target in group['targets']]
        self.assertEqual(len(role_targets), 2)
        self.assertEqual(dict(role_targets).keys(), {'service', 'monitoring'})
        self.assertEqual([target for role, target in role_targets if role == 'service'], old_targets)
        self.assertEqual(len({target for _, target in role_targets}), 2)

    def test_overlay_is_isolated_and_does_not_publish_port(self):
        services = self.overlay['services']
        self.assertEqual(set(services), {'monitoring-host-metrics', 'prometheus'})
        exporter = services['monitoring-host-metrics']
        self.assertNotIn('ports', exporter)
        self.assertNotIn('network_mode', exporter)
        self.assertIn('/:/host:ro,rslave', exporter['volumes'])
        self.assertEqual(services['prometheus']['volumes'],
                         ['./monitoring/prometheus.dual-host-candidate.yaml:/etc/prometheus/prometheus.yaml:ro'])
        self.assertTrue(self.overlay['networks']['default']['external'])


if __name__ == '__main__':
    unittest.main()
