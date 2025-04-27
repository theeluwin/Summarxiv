# Daily Paper Summary Digest

Search arXiv with given query, fetch recent papers, summarize it, and send it to your email.

---

### Prompt

Edit `prompt.txt` file.

### Query

Edit `topic2query.json` file.

```json
{
    "Recommendation": "\"recommendation\" OR \"recommender\""
}
```

---

### Environment Setting

`.env` file:

```
OPENAI_API_KEY=openai_api_key
EMAIL_ADDRESS=sender_email@email.com
EMAIL_PASSWORD=gmail_app_password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SEND_TO=receiver_email@email.com
NUM_PAPERS=10
PAGE_LIMIT=8
MAX_CONTENT_LENGTH=120000
EVERYDAY_AT=23:00
```

`EVERYDAY_AT` should consider timezone (GMT+0 by default, maybe).

### Gmail App Password

See [gmail apppasswords](https://myaccount.google.com/apppasswords).

Remove blanks.

### OpenAI API Key

See [API Keys](https://platform.openai.com/api-keys).

---

### Run:

```bash
nohup python -u entry.py >> output.log 2>&1 &
```

To see logs:

```bash
tail -f output.log
```
