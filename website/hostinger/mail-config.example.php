<?php
/**
 * Copy to `mail-config.php` on the server and fill in the real values.
 *
 * `mail-config.php` is gitignored and excluded from the FTP deploy, so it survives every
 * release and never enters the repository. This example file is the only copy that is
 * tracked — keep the two in step whenever a key is added.
 */
return [
    // --- SMTP (sales@ notification email) ---
    'host' => 'smtp.hostinger.com',
    'port' => 465,                       // 465 = implicit SSL, 587 = STARTTLS
    'user' => 'sales@technomateai.com',
    'pass' => 'REPLACE_WITH_MAILBOX_PASSWORD',
    'from' => 'sales@technomateai.com',
    'to'   => 'sales@technomateai.com',

    // --- ASTRA Marketing Service (lead record) ---
    // Leave both empty to disable lead recording entirely; contact.php then behaves
    // exactly as it did before, mailing the enquiry and nothing else.
    //
    // This is the REAL, live URL — not a placeholder. An earlier version of this file
    // showed `marketing.astra.technomateai.com`, a host that was never created, and
    // copying it verbatim sent every lead to a domain that does not resolve. There is no
    // custom domain: the Cloud Run URL is the address.
    'intake_url'    => 'https://astra-marketing-fmuizr4sda-as.a.run.app/api/v1/leads/intake',

    // Must be byte-identical to ASTRA_MKT_INTAKE_SECRET on the marketing service, which
    // is NOT the value in any developer's local .env — production has its own. The secret
    // signs the request and is never transmitted, so a leaked access log does not hand
    // anyone a working credential.
    'intake_secret' => 'REPLACE_WITH_THE_PRODUCTION_INTAKE_SECRET',
];
