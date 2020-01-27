# -*- coding: utf-8 -*-
from pydiscourse.client import DiscourseClient
from bs4 import BeautifulSoup
from pyquery import PyQuery as pq
import codecs
import os
import sys
import re
import json
import glob
import time
import datetime
import hashlib
import os
import sys
import re
import requests
import threading
import json
import time
import traceback
import calendar
from turndown import Turndown

DATA_ROOT = 'data'


# TODO: add to utils
def exception_trace(single_line=True):
    trace = traceback.format_exc()
    if single_line:
        trace = trace.replace('\n', '\\n').replace('\r', '\\r')
    return trace


def total_seconds(d):
    return d.seconds + d.microseconds / 1000000.0


def md5(s):
    return hashlib.md5(s.encode('utf8')).hexdigest()


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)


class Http:
    def __init__(self, headers={}, cache_folder=None, pages_per_second=2, timeout=10):
        self.timeout = timeout
        self.http_start = datetime.datetime.now()
        self.request_count = 0
        self.lock = threading.Lock()
        self.session = requests.Session()
        self.session.headers.update({
            'Connection': 'keep-alive',
            'X-CSRF-Token': '1XgplmbGp9rIHG2Ett31L49C+CHY9guaRkbTHNBT+h4=',
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.124 Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': '*/*',
            'X-Requested-With': 'XMLHttpRequest',
            'Accept-Encoding': 'gzip,deflate,sdch',
            'Accept-Language': 'en-US,en;q=0.8,zh-CN;q=0.6,zh;q=0.4',
            # 'Cookie': 'bdshare_firstime=1406304787067; __utma=151708859.627205429.1406304700.1406304700.1406423690.2; destination_url=http%3A%2F%2Fsuanfazu.com%2Fc%2Fz%2Fl%2Flatest.json%3F_%3D1431722643892; _t=77e7871697fcfad27b7eb78646ae8fa8; Hm_lvt_9b0738ab1116d7971e6048c2c63c1da4=1431722166; Hm_lpvt_9b0738ab1116d7971e6048c2c63c1da4=1431780588; _forum_session=cWkzTUFBenVQaGpBS2ZqazVJQkpTelZvSDhJVE56RDgwYkVsWVZNWmlFNkZYTzdSUmNBWEpidGtMQmVpcGVJMG9PZXRYY1pQMStFVjhjcWlZQjNzVjZmMlhiNjVmZ2M4bFUrNjJEUlhGNHV4K0lxSXNkSnhHWitmeGdLczQ2anUxMjRvSTZLVmhjR1pQZ0FBYUJqcTlGN1g5a3BXSEhuTm1Bdi9FRUszZUJDVGc4LzZNY0dOY3JIbDdnV1RFODJoYjY2Vm53NzlTdlhpYWRvcnVRWW5IZS9TWm5OTlVRbklEUThPVmV6UzIrbitYbm9CZmRqaXo1MWljYzh4dWV4MkFRNEdnaDA1WUJKeGZCaTR5RVozd1Azdlgvbnd0RmNEdGZDU0pqdkw4aE1GbFRWS09HZktFZWIwNXpoSHVMMVMtLTJ0ME1aK0FPNlA1dU12MTltZk9WQmc9PQ%3D%3D--46300389706c07fa40888e017c5352bff81450ef',
        })
        self.session.headers.update(headers)
        self.cache_folder = cache_folder
        if cache_folder:
            ensure_dir(cache_folder)
        self.sleep_per_page = 1 / pages_per_second
        self.last_page_time = datetime.datetime.now()

    def get(self, url):
        return self._get_with_cache(url)

    def post(self, url, data):
        print(datetime.datetime.now(), 'post to: ', url)
        return self.session.post(url, data=data, timeout=self.timeout).text

    def put(self, url, data):
        print(datetime.datetime.now(), 'put to: ', url)
        for retry in range(0, 10):
            try:
                return self.session.put(url, data=data, timeout=self.timeout).text
            except Exception as e:
                print(e)
                print(exception_trace(single_line=False))
                time.sleep(1 << retry)

    def get_soup(self, url):
        result = self._get_with_cache(url)
        return BeautifulSoup(result)

    # def post(self, url, data):
    #     return self.session.post(url, data=data)

    def _web_get(self, url):
        print('get %s' % url)
        start = datetime.datetime.now()
        interval = total_seconds(start - self.last_page_time)
        if interval < self.sleep_per_page:
            time.sleep(self.sleep_per_page - interval)
        self.last_page_time = start

        for retry in range(0, 10):
            try:
                result = self.session.get(url, timeout=self.timeout)
                break
            except Exception as e:
                print(e)
                print(exception_trace(single_line=False))
                time.sleep(1 << retry)
        end = datetime.datetime.now()
        self.lock.acquire()
        self.request_count += 1
        self.lock.release()
        print(datetime.datetime.now(), '[%s] [%ss] [total=%s|net=%.2f/s], %s' % (
            start,
            total_seconds(end - start),
            self.request_count,
            self.request_count / max(1, total_seconds(end - self.http_start)),
            url
        ))

        return result

    def _get_with_cache(self, url):
        cache_path = None
        if self.cache_folder:
            cache_path = os.path.join(self.cache_folder, md5(url))

        if cache_path and os.path.exists(cache_path):
            print('got %s from cache %s' % (url, cache_path))
            return open(cache_path, encoding='utf-8').read()

        text = self._web_get(url).text
        if 'This IP has been automatically blocked' in text:
            raise Exception('This IP has been automatically blocked.')

        if cache_path:
            with codecs.open(cache_path, 'w', 'utf-8') as writer:
                writer.write(text)

        return text


class CommunityClient:
    def __init__(self):
        pass

    def _posted_path(self, title):
        posted = os.path.join(DATA_ROOT, 'posted')
        if not os.path.exists(posted):
            os.makedirs(posted)
        return os.path.join(posted, '%s.posted' % md5(title))

    def is_posted(self, title):
        path = self._posted_path(title)
        return os.path.exists(path)

    def post(self, user, title, content):
        client = DiscourseClient(
            'https://community.bigquant.com/',
            api_username=user,
            api_key='ceaa79d2386bfbe83cdd1b71f6e7be3861c26dfb9d1c1982614aed7176db03a8')
        for i in range(0, 3):
            try:
                client.create_post(
                    content=content,
                    category=u"AI量化百科",
                    skip_validations=True,
                    auto_track=False,
                    title=title
                )
                path = self._posted_path(title)
                print(title, path)
                with codecs.open(path, 'w', 'utf-8') as writer:
                    writer.write(title + '\n')
                    writer.write('\n\n')
                    writer.write(content)
                return
            except Exception as e:
                print(e)
                print(exception_trace(single_line=False))
                time.sleep(1 << i)


class Parser:
    def __init__(self):
        self.turndown = Turndown()

    def _remove_ad(self, line):
        if line.startswith('欢迎加入'):
            return None
        if line.startswith('50篇干货链接'):
            return None
        if line.startswith('原创不易，请保护版权'):
            return None
        return line

    def _clean_ads(self, content_markdown):
        lines = content_markdown.split('\n')
        lines = [self._remove_ad(line) for line in lines]
        lines = [line for line in lines if line is not None]
        return '\n'.join(lines)

    def parse(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        #title = soup.select_one('.Post-Title').get_text()
        #content_html = soup.select_one('.Post-RichText').extract()
        title = soup.select_one('h2').get_text()
        content_html = soup.select_one('.rich_media_content').extract()
        content_markdown = self.turndown.convert(str(content_html))
        
        # content_markdown = tomd.Tomd(str(content_html)).markdown
        # print(content_markdown)
        content_markdown = self._clean_ads(content_markdown).strip()

        return {
            'title': title,
            'content_markdown': content_markdown,
        }

    def close(self):
        self.turndown.close()


def get_wecat_text(url):
    header = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        #'Cookie': 'ptisp=ctc; RK=zfDABNZRSi; ptcz=33f03644a9d86a0d2e64e10effa4a04c750665c6f47a249bd29f0758ff3481a3; pgv_pvid=6430701156; pgv_pvi=4470067200; pgv_si=s823112704; _qpsvr_localtk=0.08680180862085729; eas_sid=o1u5d3J2d5B0v6z7U5S4A9w1X8; pgv_info=ssid=s1131877332&pgvReferrer=; o_cookie=3379343948; pac_uid=1_3379343948; rewardsn=; wxtokenkey=777; luin=null; lskey=null; user_id=null; session_id=null; qqmusic_uin=; qqmusic_key=; qqmusic_fromtag=; wxuin=0; pt2gguin=o0429753097; uin=o0429753097; ptui_loginuin=429753097; skey=@c7IolWcWp',
        'Host': 'mp.weixin.qq.com',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36'
    }
    try:
        ret = requests.get(url, timeout=10, headers=header)
    except Exception as e:
        print(e, 'get wecat err')
        return False
    pq_html = pq(ret.text)
    title = pq_html('h2').text()
    text = pq_html('div.rich_media_content').html()
    return {'title': title, 'content_markdown': text}

def main():
    # url to crawl, e.g. https://zhuanlan.zhihu.com/p/31241469
#     print(sys.argv[0], sys.argv[1])
#     url = sys.argv[1]
#     user = sys.argv[2]
    url = 'https://mp.weixin.qq.com/s?timestamp=1534853922&src=3&ver=1&signature=ivA8bcwhCMzdNPwg1cMwMm5GeL2KMzDU5OsUpoG7K*jIYxUbwFaHR*Qz32ObSp4pcZz5lzdeWpFI2GYgEJdRFM0Z*DLC5NmED*xXt5lH-rRZYChTU8hsVbPVGlnhlxNCg3yLsPOsimjR1iO6aCxlvOgmM066QgfFu2V7o0A9uPw='
    user = 'yishui'
    http = Http(cache_folder=os.path.join(DATA_ROOT, 'cache'))
    html = http.get(url)

    parser = Parser()
    data = parser.parse(html)
    parser.close()

    community = CommunityClient()
    if not community.is_posted(data['title']):
        print('post to community')
        community.post('omnia', data['title'], data['content_markdown'])
    else:
        print('alreay posted')


def main_wecat(url, user):
    data = get_wecat_text(url)
    community = CommunityClient()
    if not community.is_posted(data['title']):
        print('post to community')
        community.post(user, data['title'], data['content_markdown'])
    else:
        print('alreay posted')


if __name__ == "__main__":
    # python3 zhihu.py https://zhuanlan.zhihu.com/p/31241469 omnia
#     main()
#     exit(0)
    url = 'https://mp.weixin.qq.com/s?timestamp=1534853922&src=3&ver=1&signature=ivA8bcwhCMzdNPwg1cMwMm5GeL2KMzDU5OsUpoG7K*jIYxUbwFaHR*Qz32ObSp4pcZz5lzdeWpFI2GYgEJdRFOC7IG3bIF9Lk5jYHrPyGYAcl0qloMwdXgsiyw9htziXc0hbD2w9R3d3MMqJTOcwSKmgCWS7ydHtsZNaTIO1d0U='
    user = 'yishui'
    main_wecat(url, user)
