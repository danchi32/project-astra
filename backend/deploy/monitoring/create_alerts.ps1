# Creates the ASTRA production alert policies via the Monitoring v3 REST API.
#
# The API is used directly because `gcloud alpha monitoring policies` needs the alpha
# component, which cannot be installed non-interactively on this machine.
#
# Deliberately few policies. Alert fatigue is the failure mode of monitoring: a page that
# fires for something nobody acts on trains everyone to ignore pages. Each of these means
# "a human should look now".
#
# Idempotent-ish: re-running creates duplicates, so delete the old ones first if you re-run.
param(
  [string]$Project   = "astra-prod-503923",
  [string]$Region    = "asia-southeast1",
  [string]$Service   = "astra-backend",
  [string]$UptimeId  = "astra-backend-health-0xSpamUo6Os",
  [string]$ChannelId = "4290460197084807706",
  [string]$Gcloud    = "C:\Users\Danish\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
)

$tok = (& $Gcloud auth print-access-token 2>$null).Trim()
$H   = @{ Authorization = "Bearer $tok" }
$P   = "projects/$Project"
$ch  = @("$P/notificationChannels/$ChannelId")

function New-Policy($policy) {
  $body = $policy | ConvertTo-Json -Depth 12
  try {
    $r = Invoke-RestMethod -Uri "https://monitoring.googleapis.com/v3/$P/alertPolicies" `
      -Method POST -Headers $H -ContentType "application/json" -Body $body -TimeoutSec 60
    "  OK   $($policy.displayName)"
  } catch {
    "  FAIL $($policy.displayName): $($_.ErrorDetails.Message)"
  }
}

$runFilter = 'resource.type="cloud_run_revision" AND resource.labels.service_name="' + $Service + '"'

# 1. The one that matters most: the customer-facing host is not answering. Checked from
#    three continents, so a single probe glitch can't page anyone — it needs a real majority
#    of checks to fail.
New-Policy @{
  displayName = "ASTRA: backend is DOWN (uptime check failing)"
  combiner = "OR"
  conditions = @(@{
    displayName = "api.astra.technomateai.com/health failing from most regions"
    conditionThreshold = @{
      filter = 'metric.type="monitoring.googleapis.com/uptime_check/check_passed" AND resource.type="uptime_url" AND metric.label.check_id="' + $UptimeId + '"'
      aggregations = @(@{ alignmentPeriod = "300s"; perSeriesAligner = "ALIGN_FRACTION_TRUE"; crossSeriesReducer = "REDUCE_MEAN" })
      comparison = "COMPARISON_LT"
      thresholdValue = 0.5
      duration = "60s"
      trigger = @{ count = 1 }
    }
  })
  notificationChannels = $ch
  alertStrategy = @{ autoClose = "1800s" }
  documentation = @{ content = "The backend is not answering /health on the custom domain. Check the Cloud Run revision, then DNS and the certificate — the check validates SSL, so an expired cert also trips this."; mimeType = "text/markdown" }
}

# 2. Serving, but erroring. Catches a bad revision or a database problem that a health check
#    (which touches no tables) would sail straight past.
New-Policy @{
  displayName = "ASTRA: elevated 5xx responses"
  combiner = "OR"
  conditions = @(@{
    displayName = "5xx > 1/s for 5 minutes"
    conditionThreshold = @{
      filter = 'metric.type="run.googleapis.com/request_count" AND ' + $runFilter + ' AND metric.label.response_code_class="5xx"'
      aggregations = @(@{ alignmentPeriod = "300s"; perSeriesAligner = "ALIGN_RATE"; crossSeriesReducer = "REDUCE_SUM" })
      comparison = "COMPARISON_GT"
      thresholdValue = 1
      duration = "300s"
      trigger = @{ count = 1 }
    }
  })
  notificationChannels = $ch
  alertStrategy = @{ autoClose = "1800s" }
  documentation = @{ content = "Requests are reaching the service and failing. Check Cloud Run logs for tracebacks and Neon for connection or capacity errors."; mimeType = "text/markdown" }
}

# 3. Slow rather than broken. The threshold is generous on purpose: normal p95 is well under
#    a second, so 3s means something is genuinely wrong (usually the database), not just a
#    busy minute.
New-Policy @{
  displayName = "ASTRA: p95 latency above 3s"
  combiner = "OR"
  conditions = @(@{
    displayName = "p95 request latency > 3000ms for 10 minutes"
    conditionThreshold = @{
      filter = 'metric.type="run.googleapis.com/request_latencies" AND ' + $runFilter
      aggregations = @(@{ alignmentPeriod = "300s"; perSeriesAligner = "ALIGN_PERCENTILE_95"; crossSeriesReducer = "REDUCE_MEAN" })
      comparison = "COMPARISON_GT"
      thresholdValue = 3000
      duration = "600s"
      trigger = @{ count = 1 }
    }
  })
  notificationChannels = $ch
  alertStrategy = @{ autoClose = "3600s" }
  documentation = @{ content = "Latency is degraded. Most likely the database: check Neon compute utilisation and whether autoscale has hit its ceiling."; mimeType = "text/markdown" }
}

# 4. Capacity warning, not an outage. max-instances is 20 (bounded by the regional CPU
#    quota), so sustained 15+ means the fleet has outgrown the current ceiling and the quota
#    increase needs requesting BEFORE requests start being queued.
New-Policy @{
  displayName = "ASTRA: instance count near max (capacity)"
  combiner = "OR"
  conditions = @(@{
    displayName = "15+ of 20 instances active for 15 minutes"
    conditionThreshold = @{
      filter = 'metric.type="run.googleapis.com/container/instance_count" AND ' + $runFilter
      aggregations = @(@{ alignmentPeriod = "300s"; perSeriesAligner = "ALIGN_MEAN"; crossSeriesReducer = "REDUCE_SUM" })
      comparison = "COMPARISON_GT"
      thresholdValue = 15
      duration = "900s"
      trigger = @{ count = 1 }
    }
  })
  notificationChannels = $ch
  alertStrategy = @{ autoClose = "3600s" }
  documentation = @{ content = "Approaching max-instances (20, capped by CpuAllocPerProjectRegion = 20 vCPU). Request a quota increase, and consider the agent chattiness reduction before raising cost."; mimeType = "text/markdown" }
}
