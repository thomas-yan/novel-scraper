#!/usr/bin/env python3

import re
import time
import random
import argparse
import pathlib
import os
import hashlib
import sys
import json
import logging
from random import shuffle

import requests
from pymongo import MongoClient
import sentry_sdk
from concurrent.futures import ProcessPoolExecutor, as_completed

from Configs import MONGODB_URI, DOWNLOAD_DIR, LOG_DIR, SENTRY_INIT_URL, MAX_WORKERS


def parse_arguments():
    parser = argparse.ArgumentParser(description='Novel Scraper')
    parser.add_argument('-u', '--url')
    parser.add_argument('-f', '--file')
    parser.add_argument('-s', '--search')
    parser.add_argument('-c', '--concurrent', action='store_true')
    parser.add_argument('-D', '--download-all', action='store_true')
    return parser, parser.parse_args()


def search_book(book_name):
    search_url = f'https://www.biquge5200.com/modules/article/search.php?searchkey={book_name}'
    try:
        novel_source = requests.get(search_url).text
        regex = r'<td class="odd"><a href="(.*?)">(.*?)</a></td>.*?<td class="odd">(.*?)</td>'
        novel_list = re.findall(regex, novel_source, re.S)
        if len(novel_list) == 0:
            logger.error('Found no novel.')
    except Exception as e:
        logger.error(e)
    for novel_url, novel_name, novel_author in novel_list:
        if novel_name == book_name:
            logger.info(f'Found novel：{novel_name} author：{novel_author}')
            return novel_url


def create_local_folders(novel):
    novel_root = os.path.join(DOWNLOAD_DIR, novel['id'])
    if not os.path.exists(novel_root):
        os.mkdir(novel_root)
        logger.info(f"\"{novel['title']}\" folder is created.\n")
    else:
        logger.info(f"\"{novel['title']}\" folder already exists.\n")


def create_info_original(original_novel):
    novel_root = os.path.join(DOWNLOAD_DIR, original_novel["id"])
    original_json_name = original_novel['id'] + '.json'
    original_json_path = os.path.join(novel_root, original_json_name)
    with open(original_json_path, 'w') as f:
        json.dump(original_novel, f)

    try:
        client = MongoClient(MONGODB_URI)
        db = client.novel
        col = db.novelOriginal
        original_novel.pop('chapters', None)
        inserted_id = col.insert_one(original_novel).inserted_id
        logger.info(f"Original novel Inserted ID: {str(inserted_id)}")
    except Exception as e:
        logger.error(e)
    finally:
        client.close()


def is_exist(url):
    try:
        client = MongoClient(MONGODB_URI)
        db = client.novel
        col = db.novelOriginal
        if col.count_documents({"url": url}) == 0:
            return False
        return True
    except Exception as e:
        logger.error(e)
    finally:
        client.close()


def download_novel(novel_url):
    if is_exist(novel_url):
        logger.info("Novel already exists.")
        return
    start_time = time.perf_counter()
    if not os.path.exists(DOWNLOAD_DIR):
        os.mkdir(DOWNLOAD_DIR)
    novel_data = get_novel_data(novel_url)
    create_local_folders(novel_data)
    create_info_original(novel_data)
    end_time = time.perf_counter()
    used_time = (end_time - start_time) / 60
    logger.info(f"used {used_time:0.2f} minutes")
    return novel_data


def get_novel_data(url):
    novel = {}
    html = requests.get(url).text
    title_regex = r'<h1>(.*?)</h1>'
    author_regex = r'<p style="width:200px">作&nbsp;&nbsp;&nbsp;&nbsp;者：(.*?)</p>'
    intro_regex = r'<div id="intro">(.*?)</div>'
    title = re.search(title_regex, html, re.S).group(1).strip()
    author = re.search(author_regex, html, re.S).group(1).strip()
    intro = re.search(intro_regex, html, re.S).group(1).replace('<p>', '').replace(
        '</p>', '').replace('<br/>', '').replace(' ', '').replace('&#12288;&#12288;', '').strip()
    novel['title'] = title or ''
    novel['author'] = author or ''
    novel['intro'] = intro or ''
    novel['url'] = url
    novel['id'] = hashlib.md5(
        novel['title'].encode(encoding='UTF-8')).hexdigest()
    if title:
        logger.info(f"Novel data gathered: {title}")
    chapter_regex = r'<dd><a href="(.*?)">(.*?)</a></dd>'
    chapter_list = re.findall(chapter_regex, html)
    chapters = []
    logger.info(f"{title} has {len(chapter_list)} chapters.")
    count = 0
    for chapter_url, chapter_name in chapter_list:
        if ('第' not in chapter_name) and ('章' not in chapter_name):
            continue
        time.sleep(0.1)
        content_source = requests.get(chapter_url).text
        reg = r'<div id="content">(.*?)</div>'
        try:
            content = re.findall(reg, content_source, re.S)[0]
        except IndexError:
            logger.error(f"{chapter_name} Find no content")
            continue
        content = content.replace('<br/>', '').replace(' ', '').replace(
            '<p>', '').replace('</p>', '').replace('\u3000', '').strip()
        chapters.append((chapter_name, content))
        count += 1
        logger.info(
            f"Chapter {chapter_name} finished. {count}/{len(chapter_list)}")
    novel['chapters'] = chapters
    return novel


CATEGORIES = [{'title': '玄幻小说', 'url': 'https://www.biquge5200.com/xuanhuanxiaoshuo/'}, {'title': '修真小说',
                                                                                         'url': 'https://www.biquge5200.com/xiuzhenxiaoshuo/'}, {'title': '都市小说', 'url': 'https://www.biquge5200.com/dushixiaoshuo/'}, {'title': '穿越小说', 'url': 'https://www.biquge5200.com/chuanyuexiaoshuo/'}, {'title': '网游小说', 'url': 'https://www.biquge5200.com/wangyouxiaoshuo/'}, {'title': '科幻小说', 'url': 'https://www.biquge5200.com/kehuanxiaoshuo/'}, {'title': '言情小说', 'url': 'https://www.biquge5200.com/yanqingxiaoshuo/'}, {'title': '同人小说', 'url': 'https://www.biquge5200.com/tongrenxiaoshuo/'}]


def get_all_novels():
    try:
        client = MongoClient(MONGODB_URI)
        db = client.novel
        db.novelAll.drop()
        col = db.novelAll
        all_urls = []
        for category in CATEGORIES:
            html = requests.get(category['url']).text
            regex = r'<li><span class="s2"><a href="(.*?)">(.*?)</a></span><span class="s5">.*?</span></li>'
            novel_list = re.findall(regex, html, re.S)
            category['novels'] = novel_list
            inserted_id = col.insert_one(category).inserted_id
            logger.info(
                f"Novel {category['title']} Inserted ID: {str(inserted_id)}")
            for url, _ in novel_list:
                all_urls.append(url)
        return all_urls
    except Exception as e:
        logger.error(e)
    finally:
        client.close()


def fetch_all_novels():
    try:
        client = MongoClient(MONGODB_URI)
        db = client.novel
        col = db.novelAll
        all_novels = list(col.find())
        return all_novels
    except Exception as e:
        logger.error(e)
    finally:
        client.close()


def download_executor(filtered_urls, is_concurrent, max_workers=MAX_WORKERS):
    print(f"{len(filtered_urls)} urls to download.")
    shuffle(filtered_urls)
    if is_concurrent:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(download_novel, url)
                       for url in filtered_urls]
            results = []
            for result in as_completed(futures):
                results.append(result)
            return results
    else:
        results = []
        for url in filtered_urls:
            result = download_novel(url)
            results.append(result)
            time.sleep(3)
        return results


def main():
    parser, arguments = parse_arguments()
    if arguments.url:
        download_novel(arguments.url.strip())
    elif arguments.file:
        with open(arguments.file) as urls:
            for url in urls:
                download_novel(url.strip())
    elif arguments.search:
        if not arguments.search:
            logger.error('Please input novel title')
        book_name = arguments.search.strip()
        novel_url = search_book(book_name)
        download_novel(novel_url)
    elif arguments.download_all:
        urls = get_all_novels()
        is_concurrent = arguments.concurrent
        download_executor(urls, is_concurrent)
    else:
        parser.print_usage()
        sys.exit(0)


if __name__ == '__main__':
    # Init sentry
    sentry_sdk.init(SENTRY_INIT_URL)

    # Init logger
    logger = logging.getLogger('main.py')
    logger.setLevel(logging.INFO)
    if not os.path.exists(LOG_DIR):
        os.mkdir(LOG_DIR)
    log_path = os.path.join(LOG_DIR, 'main.py.log')
    fh = logging.FileHandler(log_path)
    fh.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    logger.addHandler(fh)
    logger.addHandler(ch)
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Shutdown requested...exiting")
