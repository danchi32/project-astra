# Hostinger deploy files (Premium / shared hosting)

The site is exported as static files; the contact form emails via this small PHP
handler using your sales@ mailbox SMTP.

## Files
- `contact.php` — receives the form and sends the email (self-contained SMTP).
- `mail-config.example.php` — template. Copy to `mail-config.php`, add the real
  sales@ mailbox password. **Never commit `mail-config.php`.**

## Deploy
1. Build the static site: `cd website && npm run build` → produces `out/`.
2. In hPanel → File Manager, open **public_html**.
3. Upload **everything inside `out/`** into `public_html/`.
4. Upload **`contact.php`** into `public_html/`.
5. Copy `mail-config.example.php` → `mail-config.php`, fill in the sales@
   password, and upload it into `public_html/` too.
6. Done — the form at /contact posts to /contact.php and emails
   sales@technomateai.com.

The form falls back to opening the visitor's mail client if `contact.php` isn't
reachable, so it never loses a message.
