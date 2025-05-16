import os
import yaml
import time
import smtplib
import argparse

import arxiv  # type: ignore
import requests  # type: ignore
import schedule

from io import BytesIO
from pathlib import Path
from datetime import datetime

from pypdf import PdfReader
from openai import OpenAI
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# load env
load_dotenv()

# clients
arxiv_client = arxiv.Client()
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# alias
now = datetime.now

# constants
OPENAI_MODEL = str(os.getenv('OPENAI_MODEL', 'gpt-4o-mini'))
PAGE_LIMIT = int(os.getenv('PAGE_LIMIT', 8))
MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 12000))
TIMEZONE = str(os.getenv('TIMEZONE', 'UTC'))
EVERYDAY_AT = str(os.getenv('EVERYDAY_AT', '00:00'))

# paths
TEMPLATE_DIR = Path(__file__).parent / 'templates'


def log(message):
    print(f"[{now()}] {message}")


def search_recent_papers(query, num_papers=10):
    search = arxiv.Search(
        query=query,
        max_results=num_papers,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )
    return list(arxiv_client.results(search))


# first ~8 pages usually sufficient
def url2content(url, page_limit=8):
    if 'abs' in url:
        url = url.replace('abs', 'pdf') + '.pdf'
    response = requests.get(url)
    response.raise_for_status()
    if not response.headers.get('content-type', '').lower().startswith('application/pdf'):
        raise ValueError(f"URL did not return a PDF file. Content type: {response.headers.content-type}")
    pdfreader = PdfReader(BytesIO(response.content))
    content = ""
    for page in pdfreader.pages[:page_limit]:
        content += page.extract_text()
    return content


def chat(message):
    response = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{
            'role': 'user',
            'content': message,
        }],
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


def summarize(title, content, prompt_file, max_content_length=12000):
    with open(prompt_file, 'r') as fpi:
        template = fpi.read()
    content = content[:max_content_length]
    return chat(template.format(title=title, content=content))


def send_email(subject, content, send_to):
    email_address = os.getenv('EMAIL_ADDRESS')
    email_password = os.getenv('EMAIL_PASSWORD')
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = os.getenv('SMTP_PORT')
    msg = MIMEMultipart()
    msg['From'] = email_address
    msg['To'] = send_to
    msg['Subject'] = subject
    msg.attach(MIMEText(content, 'html'))
    server = smtplib.SMTP(smtp_server, smtp_port)
    server.starttls()
    server.login(email_address, email_password)
    server.sendmail(email_address, send_to, msg.as_string())
    server.quit()


def daily_arxiv_digest(config_file: str, prompt_file: str):
    with open(config_file, 'r') as fpi:
        config = yaml.safe_load(fpi)
    with open(TEMPLATE_DIR / 'block.html', 'r') as fpi:
        block = fpi.read()
    for row in config:
        topic = row['topic']
        query = row['query']
        receivers = row['receivers']
        num_papers = row['num_papers']
        html = ""
        log(f"searching for {query}...")
        papers = search_recent_papers(query, num_papers=num_papers)
        log(f"found {len(papers)} papers")
        for index, paper in enumerate(papers):
            log(f"[{index + 1:2d}/{len(papers):2d}] working on {paper.entry_id}...")
            title = paper.title
            pdf_url = paper.pdf_url
            log("- downloading")
            content = url2content(pdf_url, page_limit=PAGE_LIMIT)
            log("- summarizing")
            try:
                summary = summarize(title, content, prompt_file, MAX_CONTENT_LENGTH).strip('```').strip('html').strip()
                html += block.format(href=paper.entry_id, title=title, summary=summary)
            except UnicodeEncodeError:
                log("- summary failed (UnicodeEncodeError)")
                continue
        log("sending email...")
        for receiver in receivers:
            log(f"- sending to {receiver}")
            send_email(f"Daily ArXiv {topic} Papers Digest", html, receiver)
        log("done!")


def main():
    parser = argparse.ArgumentParser(description='Daily ArXiv Digest')
    parser.add_argument('--config', type=str, default='config.yaml', help='Path to the config file')
    parser.add_argument('--prompt', type=str, default='templates/prompt.txt', help='Path to the prompt file')
    args = parser.parse_args()

    schedule.every().day.at(EVERYDAY_AT, TIMEZONE).do(daily_arxiv_digest, args.config, args.prompt)
    log("scheduler started")
    while True:
        schedule.run_pending()
        time.sleep(31)  # gcd(60, 31) = 1


if __name__ == '__main__':
    main()
