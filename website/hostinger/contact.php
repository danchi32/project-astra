<?php
/**
 * Technomate contact form handler.
 *
 * Receives the inquiry form (JSON or form-encoded) and emails it to sales@
 * via authenticated SMTP. Self-contained — no external library required.
 *
 * Upload to public_html/ alongside the exported static site, and create
 * `mail-config.php` next to it (copy mail-config.example.php) with the real
 * sales@ mailbox password.
 */

header('Content-Type: application/json; charset=utf-8');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['ok' => false, 'error' => 'Method not allowed']);
    exit;
}

$configPath = __DIR__ . '/mail-config.php';
if (!is_file($configPath)) {
    http_response_code(500);
    echo json_encode(['ok' => false, 'error' => 'Mail is not configured on the server.']);
    exit;
}
$cfg = require $configPath;

// --- Read + sanitise input (JSON body or normal POST) ----------------------
$raw = file_get_contents('php://input');
$data = json_decode($raw, true);
if (!is_array($data)) {
    $data = $_POST;
}

function field(array $d, string $k, int $max = 2000): string {
    $v = isset($d[$k]) ? (string) $d[$k] : '';
    $v = trim(preg_replace('/[\r\n]+/', ' ', $v));
    return mb_substr($v, 0, $max);
}

// Honeypot: real users never fill this. Pretend success for bots.
if (field($data, 'website') !== '') {
    echo json_encode(['ok' => true]);
    exit;
}

$name     = field($data, 'name', 120);
$email    = field($data, 'email', 200);
$company  = field($data, 'company', 160);
$phone    = field($data, 'phone', 60);
$interest = field($data, 'interest', 60) ?: 'General';
$message  = field($data, 'message', 5000);
$landingPage = field($data, 'landing_page', 1000);
$referrer = field($data, 'referrer', 1000);
$utmSource = field($data, 'utm_source', 160);
$utmMedium = field($data, 'utm_medium', 160);
$utmCampaign = field($data, 'utm_campaign', 160);
$utmContent = field($data, 'utm_content', 160);
$utmTerm = field($data, 'utm_term', 160);

if ($name === '' || $message === '' || !filter_var($email, FILTER_VALIDATE_EMAIL)) {
    http_response_code(422);
    echo json_encode(['ok' => false, 'error' => 'Please provide your name, a valid email, and a message.']);
    exit;
}

$subject = "New inquiry: $interest — $name";
$bodyText = implode("\r\n", [
    "Name: $name",
    "Email: $email",
    "Company: " . ($company !== '' ? $company : '—'),
    "Phone: " . ($phone !== '' ? $phone : '—'),
    "Interested in: $interest",
    "Landing page: " . ($landingPage !== '' ? $landingPage : '—'),
    "Referrer: " . ($referrer !== '' ? $referrer : 'direct'),
    "Campaign: " . ($utmSource !== '' ? implode(' / ', array_filter([$utmSource, $utmMedium, $utmCampaign, $utmContent, $utmTerm])) : '—'),
    '',
    'Message:',
    $message,
]);

// --- Record the lead before mailing it ------------------------------------
// The email is a notification; this is the record. Until this existed, a lead was only
// ever an inbox item — nothing stored it, deduplicated it, scored it or followed it up,
// and a mailbox outage lost it outright. Now the API owns the lead and the email is the
// fast path to a human.
//
// Runs first because it is the durable half: if the intake succeeds we can honestly tell
// the visitor we have their enquiry even when SMTP is down.
$leadStored = intake_send($cfg, [
    'email'        => $email,
    'name'         => $name,
    'company'      => $company !== '' ? $company : null,
    'phone'        => $phone !== '' ? $phone : null,
    'source'       => field($data, 'source', 80) ?: 'contact_form',
    'interest'     => $interest,
    'message'      => $message,
    'landing_page' => $landingPage !== '' ? $landingPage : null,
    'referrer'     => $referrer !== '' ? $referrer : null,
    'utm_source'   => $utmSource,
    'utm_medium'   => $utmMedium,
    'utm_campaign' => $utmCampaign,
    'utm_content'  => $utmContent,
    'utm_term'     => $utmTerm,
    'consent_text' => field($data, 'consent_text', 500) ?: null,
]);

$err = '';
$mailSent = smtp_send($cfg, $email, $name, $subject, $bodyText, $err);
if (!$mailSent) {
    error_log('[contact.php] SMTP error: ' . $err);
}

// Success if EITHER path worked. Failing the form because the mailbox is down would now
// throw away a lead the API has already accepted — the visitor would retry or leave, and
// we would have their details either way but tell them we did not.
if ($leadStored || $mailSent) {
    echo json_encode(['ok' => true]);
} else {
    http_response_code(502);
    echo json_encode(['ok' => false, 'error' => 'Could not send your message right now.']);
}

/**
 * POST the lead to the ASTRA Marketing Service, signed so the endpoint can tell our
 * website from anyone who found the URL.
 *
 * Inert until `intake_url` and `intake_secret` are added to mail-config.php, so deploying
 * this file before the service exists changes nothing. Never throws and never blocks for
 * long: the visitor is waiting, and a lead recorded late beats a form that hangs.
 */
function intake_send(array $cfg, array $lead): bool {
    $url    = $cfg['intake_url'] ?? '';
    $secret = $cfg['intake_secret'] ?? '';
    if ($url === '' || $secret === '') {
        return false;
    }

    // Drop nulls so the API's optional fields stay absent rather than explicitly null.
    $body = json_encode(array_filter($lead, static fn($v) => $v !== null && $v !== ''),
                        JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    $ts   = (string) time();
    // The timestamp is signed together with the body, so a captured request cannot be
    // replayed tomorrow by pairing the old body with a fresh timestamp.
    $sig  = 'sha256=' . hash_hmac('sha256', $ts . '.' . $body, $secret);
    $headers = [
        'Content-Type: application/json',
        'X-Astra-Timestamp: ' . $ts,
        'X-Astra-Signature: ' . $sig,
    ];

    if (function_exists('curl_init')) {
        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_POST           => true,
            CURLOPT_POSTFIELDS     => $body,
            CURLOPT_HTTPHEADER     => $headers,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 6,
            CURLOPT_CONNECTTIMEOUT => 3,
        ]);
        $response = curl_exec($ch);
        $status   = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $curlErr  = curl_error($ch);
        curl_close($ch);

        if ($status >= 200 && $status < 300) {
            return true;
        }
        error_log('[contact.php] intake failed: status=' . $status
                  . ' err=' . $curlErr . ' body=' . substr((string) $response, 0, 300));
        return false;
    }

    // Shared hosting without cURL. Same request, no dependency.
    $context = stream_context_create(['http' => [
        'method'        => 'POST',
        'header'        => implode("\r\n", $headers),
        'content'       => $body,
        'timeout'       => 6,
        'ignore_errors' => true,
    ]]);
    $response = @file_get_contents($url, false, $context);
    if ($response === false) {
        error_log('[contact.php] intake failed: no response');
        return false;
    }
    // $http_response_header is populated by the stream wrapper, not by us.
    // Anchored at the status line's start: a reason-phrase match ("... 200 OK") would
    // also hit on a header that merely contains a number, and a trailing-space match
    // would miss a reason-less "HTTP/1.1 201".
    $statusLine = $http_response_header[0] ?? '';
    if (preg_match('#^HTTP/\S+\s+2\d\d#', $statusLine)) {
        return true;
    }
    error_log('[contact.php] intake failed: ' . $statusLine);
    return false;
}

/**
 * Minimal authenticated SMTP sender (SSL on 465, STARTTLS otherwise).
 */
function smtp_send(array $cfg, string $replyEmail, string $replyName, string $subject, string $body, string &$err): bool {
    $host = $cfg['host'];
    $port = (int) $cfg['port'];
    $user = $cfg['user'];
    $pass = $cfg['pass'];
    $from = !empty($cfg['from']) ? $cfg['from'] : $user;
    $to   = $cfg['to'];

    $endpoint = ($port === 465 ? 'ssl://' : '') . $host . ':' . $port;
    $fp = @stream_socket_client($endpoint, $errno, $errstr, 20);
    if (!$fp) {
        $err = "connect failed: $errstr ($errno)";
        return false;
    }
    stream_set_timeout($fp, 20);

    $read = function () use ($fp): string {
        $out = '';
        while (($line = fgets($fp, 515)) !== false) {
            $out .= $line;
            // Multi-line replies have a '-' after the code; ' ' marks the last line.
            if (strlen($line) < 4 || $line[3] === ' ') {
                break;
            }
        }
        return $out;
    };
    $send = function (string $cmd) use ($fp, $read): string {
        fwrite($fp, $cmd . "\r\n");
        return $read();
    };
    $ok = function (string $resp, array $codes) use (&$err): bool {
        $code = substr($resp, 0, 3);
        if (!in_array($code, $codes, true)) {
            $err = 'unexpected reply: ' . trim($resp);
            return false;
        }
        return true;
    };

    if (!$ok($read(), ['220'])) { fclose($fp); return false; }
    $send('EHLO technomateai.com');

    if ($port !== 465) {
        if (!$ok($send('STARTTLS'), ['220'])) { fclose($fp); return false; }
        if (!stream_socket_enable_crypto($fp, true, STREAM_CRYPTO_METHOD_TLS_CLIENT)) {
            $err = 'STARTTLS negotiation failed';
            fclose($fp);
            return false;
        }
        $send('EHLO technomateai.com');
    }

    if (!$ok($send('AUTH LOGIN'), ['334'])) { fclose($fp); return false; }
    if (!$ok($send(base64_encode($user)), ['334'])) { fclose($fp); return false; }
    if (!$ok($send(base64_encode($pass)), ['235'])) { $err = 'authentication failed'; fclose($fp); return false; }

    if (!$ok($send("MAIL FROM:<$from>"), ['250'])) { fclose($fp); return false; }
    if (!$ok($send("RCPT TO:<$to>"), ['250', '251'])) { fclose($fp); return false; }
    if (!$ok($send('DATA'), ['354'])) { fclose($fp); return false; }

    $headers = implode("\r\n", [
        'From: Technomate Website <' . $from . '>',
        'To: <' . $to . '>',
        'Reply-To: ' . mb_encode_mimeheader($replyName) . ' <' . $replyEmail . '>',
        'Subject: ' . mb_encode_mimeheader($subject),
        'MIME-Version: 1.0',
        'Content-Type: text/plain; charset=UTF-8',
        'Date: ' . date('r'),
    ]);
    // Dot-stuffing: lines starting with '.' must be escaped.
    $safeBody = preg_replace('/^\./m', '..', $body);
    $payload = $headers . "\r\n\r\n" . $safeBody . "\r\n.";

    if (!$ok($send($payload), ['250'])) { fclose($fp); return false; }
    $send('QUIT');
    fclose($fp);
    return true;
}
