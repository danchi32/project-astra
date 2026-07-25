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
    '',
    'Message:',
    $message,
]);

$err = '';
if (smtp_send($cfg, $email, $name, $subject, $bodyText, $err)) {
    echo json_encode(['ok' => true]);
} else {
    error_log('[contact.php] SMTP error: ' . $err);
    http_response_code(502);
    echo json_encode(['ok' => false, 'error' => 'Could not send your message right now.']);
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
