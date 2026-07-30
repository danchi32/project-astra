#!/bin/sh
# Read-only diagnostic: where are a device's remediation tasks stuck?
#
# Answers the question "I pushed a fix and nothing happened" by showing the status of each
# task and how long it has sat there. Status tells you which half is broken:
#   pending_approval -> nobody approved it (the portal should approve inline)
#   approved         -> created and cleared, but the AGENT never claimed it
#   dispatched       -> the agent took it and never reported back (execution hung/crashed)
#   succeeded/failed -> it ran; read the result
#
# Needs MIGRATE_DST_URL. Optional DEVICE_HOSTNAME filters to one machine.
set -eu

: "${MIGRATE_DST_URL:?MIGRATE_DST_URL is required}"
HOST="${DEVICE_HOSTNAME:-}"

if [ -n "$HOST" ]; then
  echo "=== device: $HOST ==="
  psql "$MIGRATE_DST_URL" -P pager=off -c "
    select hostname, agent_version, last_seen_at,
           (now() - last_seen_at) as since_last_seen
    from devices where hostname = '$HOST';
  "
  WHERE="and d.hostname = '$HOST'"
else
  WHERE=""
fi

echo "=== recent remediation tasks (newest first) ==="
psql "$MIGRATE_DST_URL" -P pager=off -c "
  select d.hostname,
         t.action_id,
         t.status,
         t.tier,
         to_char(t.created_at,   'MM-DD HH24:MI') as created,
         to_char(t.completed_at, 'MM-DD HH24:MI') as completed,
         (now() - t.created_at)                   as age,
         left(coalesce(t.result->>'output', ''), 60) as result
  from remediation_tasks t
  join devices d on d.id = t.device_id
  where t.created_at > now() - interval '6 hours' $WHERE
  order by t.created_at desc
  limit 25;
"

echo "=== stuck: approved but never claimed by an agent ==="
psql "$MIGRATE_DST_URL" -P pager=off -c "
  select d.hostname, d.agent_version, t.action_id, t.tier,
         (now() - t.created_at) as waiting
  from remediation_tasks t
  join devices d on d.id = t.device_id
  where t.status = 'approved' and t.created_at > now() - interval '24 hours' $WHERE
  order by t.created_at desc limit 15;
"

echo "=== pending Windows updates known for this device ==="
psql "$MIGRATE_DST_URL" -P pager=off -c "
  select d.hostname, u.kb_article_id, left(u.title, 50) as title, u.is_installed
  from device_windows_updates u
  join devices d on d.id = u.device_id
  where u.is_installed = false $WHERE
  order by d.hostname limit 20;
"
