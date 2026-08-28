# JAY Private API Telegram Bot

Railway-ready Telegram bot for **authorized API/payment testing**.

## Features
- Private access keys such as `JAY-7A2K-X9QF`
- Keys are stored in SQLite
- Admin generation/revocation
- Key expiry
- Authorized HTTP test endpoint
- Optional HTTP proxy
- Railway worker process

## Railway setup

1. Create a new Railway project.
2. Deploy this repository/project.
3. Add these Variables:

```text
BOT_TOKEN=your_BotFather_token
ADMIN_IDS=123456789
KEY_DAYS=30
TEST_API_URL=https://your-authorized-test-api.example.com/test
HTTP_PROXY=
```

`ADMIN_IDS` can contain multiple Telegram numeric IDs separated by commas.

4. Start the worker. Railway uses the included `Procfile`.

## Telegram commands

```text
/start
/activate JAY-XXXX-XXXX
/test hello
/msp TEST1\nTEST2\n...\n```

Admin:

```text
/generate
/keys
/revoke JAY-XXXX-XXXX
```

The `/msp` command accepts up to 30 newline-separated test inputs and sends each to the configured authorized endpoint. The `/test` command sends JSON like:

```json
{"test_input":"hello"}
```

to your own/authorized test endpoint.

## Important

This project intentionally does **not** implement real credit-card/CVV validation, charging, BIN testing, stolen-card checking, or payment-security bypasses. For payment integration, use the provider's official sandbox/test environment and test credentials.


## Added commands

```text
/key DAYS QUANTITY
/ban USER_ID
/site
/site add NAME URL
/site del ID
/gen QUANTITY
/chk
```

`/gen` creates non-payment test IDs (up to 20,000). `/chk` batch-tests those IDs against the configured authorized `TEST_API_URL`; it does not validate or charge real payment cards.


## Message style

Bot responses use Telegram HTML formatting with bold headings, italic/Unicode-styled labels, separators, and compact status sections inspired by the supplied source's visual style.
