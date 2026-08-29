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
    // `intake_secret` must be byte-identical to ASTRA_MKT_INTAKE_SECRET on the marketing
    // service. It signs the request; it is never sent, so a leaked access log does not
    // hand anyone a working credential.
    'intake_url'    => 'https://marketing.astra.technomateai.com/api/v1/leads/intake',
    'intake_secret' => 'REPLACE_WITH_A_LONG_RANDOM_STRING',
];
