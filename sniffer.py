
class Sniffer(object):
    _href = ''
    _source = ''

    def __init__(self, href, source):
        self._href = href
        self._source = source

    def start(self):
        if self._source == '91':
            return [self.getM3HrefFrom91(), None]

    def getM3HrefFrom91(self):
        return '123'
