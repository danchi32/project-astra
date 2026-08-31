# ASTRA Controlled Endpoint Pilot — Draft Offer

Updated: 2026-08-30
Status: Internal draft; not approved for public publication

## Offer summary

The ASTRA Controlled Endpoint Pilot helps an IT team evaluate evidence-first Windows automation on a limited device group before committing to a wider rollout.

The pilot is designed to answer four questions:

1. Can ASTRA collect useful endpoint evidence before a technician investigates?
2. Do the code-enforced action tiers match the organization’s risk policy?
3. Can selected routine issues be remediated and verified without weakening human control?
4. What needs to change before ASTRA expands to more devices or workflows?

## Recommended scope

| Item | Recommended pilot term |
| --- | --- |
| Duration | 14 calendar days after the first pilot device reports successfully |
| Device group | Up to 10 supported Windows endpoints |
| Supported operating systems | 64-bit Windows 10 and Windows 11 |
| Issue catalogue | Three to five frequent, agreed Windows issue types |
| Primary owner | One named customer IT owner |
| Approvers | Named approver for approval-required actions and named administrator for admin-only actions |
| Review cadence | Kickoff, midpoint review and final decision review |
| Commercial status | Software trial requires no credit card; guided-service pricing still requires founder approval |

The device limit is deliberately small enough to control risk and broad enough to include representative users, hardware and working locations.

## What Technomate provides

- Pilot-planning session covering devices, current tools, frequent issues and action boundaries.
- ASTRA software access for the agreed pilot period.
- Guidance for deploying and removing the Windows agent.
- Fleet visibility for enrolled devices, including available telemetry and inventory.
- Evidence-first diagnosis using live endpoint context and approved knowledge.
- Automatic, approval-required and admin-only remediation tiers.
- Endpoint command allowlisting and parameter validation.
- Audit history for actions, approvals and execution results.
- Midpoint review covering exceptions and policy adjustments.
- Final review with findings, limitations and a rollout recommendation.

## What the customer provides

- A named pilot owner with authority to coordinate the device group.
- Approved Windows endpoints and permission to install the ASTRA agent.
- A list of frequent issue types and existing support process.
- Named people authorized to approve sensitive actions.
- Current tool and coexistence requirements.
- Timely access to pilot users when an issue requires confirmation.
- Prompt reporting of unexpected device or business impact.

## Action boundaries

### Automatic

Only frequent, reversible and explicitly permitted actions should begin in this tier. Examples may include restarting Explorer or an approved application, flushing DNS, clearing permitted temporary files, or restarting an allowlisted service.

### Approval required

Actions with broader operational impact must wait for an authorized person. Examples include Office repair, driver updates or network reset.

### Administrator only

Sensitive changes remain restricted to an authorized administrator. Examples include registry, BIOS, firmware or Windows reinstallation work.

The model cannot promote an action into a lower tier. Backend authorization and endpoint allowlists remain the enforcement boundaries.

## Pilot success criteria

The final decision should use evidence, not an activity count. Recommended criteria:

1. All intended pilot devices either report successfully or have a documented enrollment exception.
2. Selected issue types produce enough live evidence for the IT owner to review the diagnosis.
3. Automatic actions execute only when explicitly permitted.
4. Approval-required actions remain blocked until the named approver authorizes them.
5. Admin-only actions remain restricted to the authorized administrator.
6. The endpoint agent rejects unknown actions or invalid parameters.
7. Every attempted remediation retains an attributable audit record.
8. Verification distinguishes a resolved outcome from a failed or inconclusive attempt.
9. No critical business workflow is disrupted by the agreed action catalogue.
10. The final review identifies which workflows should expand, remain approval-gated or be removed.

Optional operational measures should be baselined before the pilot:

- Technician time spent gathering evidence
- Median and mean resolution time for selected issue types
- Repeat-issue rate
- Number of technician interventions
- Employee interruption required for diagnosis

No improvement percentage should be promised before a real baseline exists.

## Out of scope unless agreed in writing

- Unsupported operating systems
- Unrestricted shell or arbitrary command execution
- Registry, BIOS, firmware or reinstallation automation
- Identity, ticketing or third-party tool integrations not validated before kickoff
- Guaranteed response or resolution times
- On-site coverage outside an agreed service area
- Hardware replacement, licensing or procurement charges
- A production-wide rollout during the pilot

## Exit and risk reversal

The customer can stop the evaluation before wider rollout. At exit:

- New remediation activity is stopped.
- Pilot devices are unenrolled and the agent removal process is provided.
- The customer retains any records available under the agreed data-retention terms.
- Exceptions and unresolved issues are documented.
- No paid rollout begins without separate approval.

This is a controlled evaluation commitment, not a performance guarantee.

## Final decision review

The closing review should record one of four outcomes:

1. Expand to a larger Windows device group.
2. Continue the limited pilot with specific changes.
3. Use ASTRA alongside an existing endpoint platform for selected workflows.
4. End the pilot and remove the agent.

## Founder decisions required before publication

1. Confirm the public device limit: **10 devices** or another number.
2. Confirm whether guided kickoff and review support are free or separately priced.
3. Confirm support hours and a serviceable response-time expectation.
4. Confirm whether the 14 days begin at account creation or first successful device report. This draft recommends first device report.
5. Confirm the default data-retention and deletion language for ended pilots.
6. Confirm whether optional managed/on-site support is mentioned in the public offer.

Until these items are approved, the website should continue offering a 14-day software trial and a 30-minute pilot-planning session without publishing unsupported service commitments.
