-- Données de test AIOps Sentinel

INSERT INTO servers (name, ip_address, os, role, status) VALUES
('web-prod-01', '10.0.1.10', 'Ubuntu 22.04', 'web', 'active'),
('web-prod-02', '10.0.1.11', 'Ubuntu 22.04', 'web', 'active'),
('db-prod-01', '10.0.2.10', 'RHEL 9', 'database', 'active'),
('monitoring-01', '10.0.3.10', 'RHEL 9', 'monitoring', 'active'),
('backup-01', '10.0.4.10', 'RHEL 9', 'backup', 'maintenance');

INSERT INTO services (name, server_id, port, status) VALUES
('nginx', 1, 80, 'running'),
('nginx', 2, 80, 'running'),
('postgresql', 3, 5432, 'running'),
('pgbouncer', 3, 6432, 'running'),
('grafana', 4, 3000, 'running'),
('rsync-daemon', 5, 873, 'stopped');

INSERT INTO incidents (title, description, server_id, service_id, severity, status, created_at, resolved_at) VALUES
('Connexions PostgreSQL refusées', 'Mémoire saturée sur db-prod-01, connexions rejetées', 3, 3, 'high', 'resolved', '2026-09-05 08:12:00', '2026-09-05 10:45:00'),
('Espace disque faible', 'Partition /var à 92% sur web-prod-01', 1, NULL, 'medium', 'open', '2026-09-09 14:30:00', NULL),
('Service rsync arrêté', 'rsync-daemon down sur backup-01 après redémarrage', 5, 6, 'low', 'open', '2026-09-10 09:00:00', NULL);
