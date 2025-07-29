# Summarxiv

Daily latest arXiv paper summary digest.

Search arXiv with given query, fetch recent papers, summarize it, and send it to your email.

## Configuration

### Prompt

Edit `./templates/prompt.txt` file.

### Quering & Mail To

Edit `./config.yaml` file.

```yaml
- topic: RecSys
  query: (cat:cs.CV OR cat:cs.LG OR cat:cs.AI OR cat:cs.IR) AND ("recommendation" OR "recommender")
  num_papers: 5
  receivers:
    - test@test.com
```

* `topic` is just a verbose title.
* `query` will be applied directly to the arXiv API.

## Environment Setting

Rename `.env.example` to `.env` and edit it.

The file contains the following variable:

```bash
# configuration
CONFIG_FILE=./config.yaml
PROMPT_FILE=./templates/prompt.txt
BLOCK_TEMPLATE_FILE=./templates/block.html
FOOTER_TEMPLATE_FILE=./templates/footer.html
LOG_FILE=./logs/summarxiv.log
CACHE_DIR=./cache/

# llm
LLM_MODEL=openai/gpt-4o-mini
LLM_TEMPERATURE=0.3
OPENAI_API_KEY=your_openai_api_key

# email
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_ADDRESS=sender.email@gmail.com
EMAIL_PASSWORD=senderapppassword

# summarize
MAX_NUM_PAPERS=10
MAX_NUM_SEARCH_TRIALS=5
PAGE_LIMIT=8
MAX_CONTENT_LENGTH=120000

# schedule
EVERYDAY_AT=08:00
TIMEZONE=UTC
SLEEP_INTERVAL=5.0
```

If you want to use Claude instead of OpenAI, set as follows:

```bash
LLM_MODEL=anthropic/claude-3-sonnet-20240229
ANTHROPIC_API_KEY=your_anthropic_api_key
```

For the other providers, please see [LiteLLM](https://docs.litellm.ai/docs/#litellm-python-sdk) documentations.

### Gmail App Password

See [Gmail apppasswords](https://myaccount.google.com/apppasswords).

### OpenAI API Key

See [API Keys](https://platform.openai.com/api-keys).

## Run

```bash
uv sync
source .venv/bin/activate
nohup python -u summarxiv.py >> nohup.out 2>&1 &
```

To use Docker:

```bash
docker build \
    --tag summarxiv \
    .
docker run \
    --detach \
    --name summarxiv-container \
    --env-file .env \
    --publish 587:587 \
    --volume $(pwd)/config.yaml:/app/config.yaml \
    --volume $(pwd)/templates/prompt.txt:/app/templates/prompt.txt \
    --volume $(pwd)/cache:/app/cache \
    --volume $(pwd)/logs:/app/logs \
    summarxiv
```
