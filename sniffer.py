from arthur.request import request
import re
import urllib


class Sniffer(object):
    _href = ''
    _source = ''

    def __init__(self, href, source):
        self._href = href
        self._source = source

    def start(self):
        if self._source == '91':
            return self.getM3HrefFrom91()

    def getM3HrefFrom91(self):
        url = self._href
        response = request.get(url=url, max_retry_time=2)

        if '请点击以下链接访问，以验证你不是机器人！' in response.text:
            response = request.get(url=url, max_retry_time=2)
            print(response.text)
        a = re.findall('document.write(.*);', response.text)[0]
        m3u8_href = a[13:-3]
        m3u8_href = urllib.parse.unquote(m3u8_href)
        m3u8_href = m3u8_href[13:-31]
        video_name = re.findall('<h4 class="login_register_header" align=left>(.*)\n', response.text)[0]
        return [m3u8_href, video_name]