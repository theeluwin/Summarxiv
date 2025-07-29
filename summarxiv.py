import os
import time
import smtplib
import logging
import argparse

import yaml
import arxiv
import requests
import schedule

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from dotenv import load_dotenv
from litellm import completion
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def get_args():

    # load env
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Summarxiv: daily latest arXiv paper summary digest.",
    )

    # configuration
    parser.add_argument(
        '--config_file',
        type=str,
        default=os.getenv('CONFIG_FILE', './config.yaml'),
        help="Path to the config file.",
    )
    parser.add_argument(
        '--prompt_file',
        type=str,
        default=os.getenv('PROMPT_FILE', './templates/prompt.txt'),
        help="Path to the prompt file.",
    )
    parser.add_argument(
        '--block_template_file',
        type=str,
        default=os.getenv('BLOCK_TEMPLATE_FILE', './templates/block.html'),
        help="Path to the block file.",
    )
    parser.add_argument(
        '--footer_template_file',
        type=str,
        default=os.getenv('FOOTER_TEMPLATE_FILE', './templates/footer.html'),
        help="Path to the footer file.",
    )
    parser.add_argument(
        '--log_file',
        type=str,
        default=os.getenv('LOG_FILE', './logs/summarxiv.log'),
        help="Path to the log file.",
    )
    parser.add_argument(
        '--cache_dir',
        type=str,
        default=os.getenv('CACHE_DIR', './cache/'),
        help="Path to the cache directory.",
    )

    # llm
    parser.add_argument(
        '--llm_model',
        type=str,
        default=os.getenv('LLM_MODEL', 'openai/gpt-4o-mini'),
        help="LLM model to use.",
    )
    parser.add_argument(
        '--llm_temperature',
        type=float,
        default=float(os.getenv('LLM_TEMPERATURE', 0.3)),
        help="LLM temperature.",
    )

    # email
    parser.add_argument(
        '--smtp_server',
        type=str,
        default=os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
        help="SMTP server.",
    )
    parser.add_argument(
        '--smtp_port',
        type=int,
        default=int(os.getenv('SMTP_PORT', 587)),
        help="SMTP port.",
    )
    parser.add_argument(
        '--email_address',
        type=str,
        default=os.getenv('EMAIL_ADDRESS'),
        help="Sender email address.",
    )
    parser.add_argument(
        '--email_password',
        type=str,
        default=os.getenv('EMAIL_PASSWORD'),
        help="Sender email app password.",
    )

    # summarize
    parser.add_argument(
        '--max_num_papers',
        type=int,
        default=int(os.getenv('MAX_NUM_PAPERS', 10)),
        help="Number of papers to search.",
    )
    parser.add_argument(
        '--max_num_search_trials',
        type=int,
        default=int(os.getenv('MAX_NUM_SEARCH_TRIALS', 5)),
        help="Maximum number of trials for the search API.",
    )
    parser.add_argument(
        '--page_limit',
        type=int,
        default=int(os.getenv('PAGE_LIMIT', 8)),
        help="Number of pages to extract.",
    )
    parser.add_argument(
        '--max_content_length',
        type=int,
        default=int(os.getenv('MAX_CONTENT_LENGTH', 12000)),
        help="Maximum content length.",
    )

    # schedule
    parser.add_argument(
        '--everyday_at',
        type=str,
        default=os.getenv('EVERYDAY_AT', '08:00'),
        help="Time to run everyday.",
    )
    parser.add_argument(
        '--timezone',
        type=str,
        default=os.getenv('TIMEZONE', 'UTC'),
        help="Timezone.",
    )
    parser.add_argument(
        '--sleep_interval',
        type=float,
        default=float(os.getenv('SLEEP_INTERVAL', 5.0)),
        help="Sleep interval in seconds.",
    )

    # parse
    args = parser.parse_args()

    # resolve paths
    args.config_file = Path(args.config_file)
    args.config_file.parent.mkdir(parents=True, exist_ok=True)
    args.prompt_file = Path(args.prompt_file)
    args.prompt_file.parent.mkdir(parents=True, exist_ok=True)
    args.block_template_file = Path(args.block_template_file)
    args.block_template_file.parent.mkdir(parents=True, exist_ok=True)
    args.footer_template_file = Path(args.footer_template_file)
    args.footer_template_file.parent.mkdir(parents=True, exist_ok=True)
    args.log_file = Path(args.log_file)
    args.log_file.parent.mkdir(parents=True, exist_ok=True)
    args.cache_dir = Path(args.cache_dir)
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    (args.cache_dir / 'content').mkdir(parents=True, exist_ok=True)
    (args.cache_dir / 'summary').mkdir(parents=True, exist_ok=True)

    # resolve values
    args.email_password = args.email_password.replace(' ', '')

    return args


class Summarxiv:

    def __init__(self, args):

        # arguments
        self.args = args

        # init stuffs
        self.init_logger()
        self.init_smtp()
        self.init_client()
        self.init_config()
        self.init_templates()

    def init_client(self):
        self.arxiv_client = arxiv.Client()

    def init_config(self):
        with open(self.args.config_file, 'r') as fpi:
            self.config = yaml.safe_load(fpi)

    def init_templates(self):
        with open(self.args.block_template_file, 'r') as fpi:
            self.block_template = fpi.read()
        with open(self.args.footer_template_file, 'r') as fpi:
            self.footer_template = fpi.read()

    def init_logger(self):

        # set logger
        self.logger = logging.getLogger('summarxiv')
        self.logger.setLevel(logging.INFO)

        # set formatter
        formatter = logging.Formatter(
            "<%(asctime)s>"
            " "
            "%(message)s"
        )

        # set handlers
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        file_handler = logging.FileHandler(self.args.log_file)
        file_handler.setFormatter(formatter)

        # attach handlers
        self.logger.addHandler(stream_handler)
        self.logger.addHandler(file_handler)

    def init_smtp(self):
        self.email_server = smtplib.SMTP(
            self.args.smtp_server,
            self.args.smtp_port,
        )
        self.email_server.starttls()
        self.email_server.login(
            self.args.email_address,
            self.args.email_password,
        )

    def send_email(self, send_to, subject, body):

        # create message
        message = MIMEMultipart()
        message['From'] = self.args.email_address
        message['To'] = send_to
        message['Subject'] = subject
        message.attach(MIMEText(body, 'html'))

        # send email
        self.email_server.sendmail(
            self.args.email_address,
            send_to,
            message.as_string(),
        )

    def search_recent_papers(self, query, num_papers):
        search = arxiv.Search(
            query=query,
            max_results=min(num_papers, self.args.max_num_papers),
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )
        results = self.arxiv_client.results(search)
        return list(results)

    def get_xid_from_url(self, url):
        return url.split('/')[-1].split('v')[0]

    def get_content_from_url(self, url):
        if 'abs' in url:
            url = url.replace('abs', 'pdf') + '.pdf'
        res = requests.get(url)
        res.raise_for_status()
        content_type = res.headers.get('content-type', '').lower()
        if not content_type.startswith('application/pdf'):
            raise ValueError(
                "URL did not return a PDF file."
                " "
                f"Content type: {content_type}"
            )
        reader = PdfReader(BytesIO(res.content))
        content = ""
        for page in reader.pages[:self.args.page_limit]:
            content += page.extract_text()
        return content

    def chat(self, message):
        response = completion(
            model=self.args.llm_model,
            messages=[{
                'role': 'user',
                'content': message,
            }],
            temperature=self.args.llm_temperature,
        )
        return (
            response
            .choices[0]
            .message
            .content
            .strip()
            .strip('```')
            .strip('html')
            .strip()
        )

    def summarize_paper(self, title, content):
        with open(self.args.prompt_file, 'r') as fpi:
            template = fpi.read()
        content = content[:self.args.max_content_length]
        message = template.format(title=title, content=content)
        return self.chat(message)

    def get_cache(self, key):
        if key.exists():
            with open(key, 'r') as fpi:
                value = fpi.read()
        else:
            value = None
        return value

    def set_cache(self, key, value):
        with open(key, 'w') as fpo:
            fpo.write(value)

    def sleep(self):
        time.sleep(self.args.sleep_interval)

    def digest(self):
        self.init_config()
        self.init_templates()
        for row in self.config:

            # prepare
            topic = row['topic']
            query = row['query']
            receivers = row['receivers']
            num_papers = row['num_papers']
            body = ""

            # search papers
            self.logger.info(f"Searching for topic: {topic}")
            num_trials = 0
            papers = None
            while True:
                num_trials += 1
                try:
                    papers = self.search_recent_papers(query, num_papers)
                    break
                except requests.RequestException as e:
                    self.logger.error(f"- failed to search papers (requests error: {e})")
                    self.sleep()
                except Exception as e:
                    self.logger.error(f"- failed to search papers (error: {e})")
                    self.sleep()
                if num_trials >= self.args.max_num_search_trials:
                    self.logger.error("- too many trials, giving up today")
                    return
            if not len(papers):
                self.logger.error(f"- no papers found for {topic}")
                self.sleep()
                continue
            self.logger.info(f"- found {len(papers)} papers")

            for index, paper in enumerate(papers, start=1):

                self.logger.info(
                    f"[{index:2d}/{len(papers):2d}]"
                    " "
                    f"working on {paper.entry_id}"
                )

                # get title
                title = paper.title

                # get xid
                url = paper.pdf_url
                xid = self.get_xid_from_url(url)

                # get content
                self.logger.info(f"- achieving content for {xid}")
                key = self.args.cache_dir / 'content' / f'{xid}.txt'
                content = self.get_cache(key)
                if content:
                    self.logger.info("- using cached content")
                else:
                    try:
                        content = self.get_content_from_url(url)
                        self.set_cache(key, content)
                        self.sleep()
                    except ValueError as e:
                        self.logger.error(f"- failed to download content (value error: {e})")
                        self.sleep()
                        continue
                    except requests.RequestException as e:
                        self.logger.error(f"- failed to download content (requests error: {e})")
                        self.sleep()
                        continue
                    except Exception as e:
                        self.logger.error(f"- failed to download content (exception: {e})")
                        self.sleep()
                        continue

                # summarize
                self.logger.info(f"- summarizing {xid}")
                key = self.args.cache_dir / 'summary' / f'{xid}.txt'
                summary = self.get_cache(key)
                if summary:
                    self.logger.info("- using cached summary")
                else:
                    try:
                        summary = self.summarize_paper(title, content)
                        self.set_cache(key, summary)
                    except UnicodeEncodeError as e:
                        self.logger.error(f"- summarizing failed (unicode encode error: {e})")
                        self.sleep()
                        continue
                    except Exception as e:
                        self.logger.error(f"- summarizing failed (exception: {e})")
                        self.sleep()
                        continue

                # add to body
                body += self.block_template.format(
                    href=paper.entry_id,
                    title=title,
                    summary=summary,
                )
                self.sleep()

            # add footer
            body += self.footer_template

            # send email
            self.logger.info("- sending email")
            for receiver in receivers:

                self.logger.info(f"- sending to {receiver}")
                self.send_email(
                    receiver,
                    f"Summarxiv - {topic}",
                    body,
                )
                self.sleep()

            self.logger.info("- done!")


if __name__ == '__main__':

    args = get_args()
    summarxiv = Summarxiv(args)

    (
        schedule
        .every()
        .day
        .at(args.everyday_at, args.timezone)
        .do(summarxiv.digest)
    )
    summarxiv.logger.info("Scheduler started.")

    while True:
        schedule.run_pending()
        time.sleep(2)
