#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
install -d -m 755 /opt/searchroom/host
install -m 755 control.py /opt/searchroom/host/control.py
install -m 644 compose.yml /opt/searchroom/host/compose.yml
curl --fail --silent --show-error --location https://truststore.pki.rds.amazonaws.com/eu-west-2/eu-west-2-bundle.pem -o /etc/searchroom/rds-ca.pem
chmod 644 /etc/searchroom/rds-ca.pem
cat > /etc/systemd/system/searchroom-firewall.service <<'UNIT'
[Unit]
After=docker.service
Requires=docker.service
Before=searchroom.service
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/sh -c '/usr/sbin/iptables -C DOCKER-USER -d 169.254.169.254/32 -j REJECT || /usr/sbin/iptables -I DOCKER-USER 1 -d 169.254.169.254/32 -j REJECT'
[Install]
WantedBy=multi-user.target
UNIT
cat > /etc/systemd/system/searchroom.service <<'UNIT'
[Unit]
After=network-online.target docker.service searchroom-firewall.service
Requires=docker.service searchroom-firewall.service
Wants=network-online.target
ConditionPathExists=/etc/searchroom/release.env
[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/searchroom/host
ExecStart=/usr/bin/docker compose --env-file /etc/searchroom/release.env up -d --remove-orphans
ExecStop=/usr/bin/docker compose --env-file /etc/searchroom/release.env stop
TimeoutStartSec=180
[Install]
WantedBy=multi-user.target
UNIT
for job in check cleanup backup; do
  cat > "/etc/systemd/system/searchroom-$job.service" <<UNIT
[Unit]
After=searchroom.service
ConditionPathExists=/etc/searchroom/release.env
[Service]
Type=oneshot
ExecStart=/opt/searchroom/host/control.py $job
TimeoutStartSec=1800
UMask=0077
UNIT
done
for job in cleanup backup; do
  if [ "$job" = cleanup ]; then schedule='*-*-* 01:00:00'; else schedule='*-*-* 01:30:00'; fi
  cat > "/etc/systemd/system/searchroom-$job.timer" <<UNIT
[Timer]
OnCalendar=$schedule
Persistent=true
RandomizedDelaySec=300
[Install]
WantedBy=timers.target
UNIT
done
cat > /etc/systemd/system/searchroom-check.timer <<'UNIT'
[Timer]
OnBootSec=5min
OnUnitActiveSec=15min
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now searchroom-firewall.service
systemctl enable searchroom.service
systemctl enable --now searchroom-check.timer searchroom-cleanup.timer searchroom-backup.timer
