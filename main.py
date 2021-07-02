import random
import re
import sys
import os
import threadpool
import subprocess
from Crypto.Cipher import AES

sys.path.append(r"E:\python")

from arthur.url import parse as url
from arthur.request import request
from arthur.sys import command


class M3(object):
    m3u8_href = ''
    key_content = None
    video_name = ''
    url_host = ''
    url_path = ''
    # 存放ts目录的目录
    ts_path = ''
    # 所有的ts链接列表
    url_list = []
    # 下载失败的链接列表
    down_fail_list = []

    # 初始化
    def __init__(self, m3u8_href, key_content, video_name, ts_path):
        self.m3u8_href = m3u8_href
        self.key_content = key_content
        self.video_name = video_name
        self.ts_path = ts_path
        self.url_host = url.get_host(m3u8_href)
        self.url_path = url.get_path(m3u8_href)

    # 开始运行
    def start(self):
        # 检查地址是否合法
        if self.check_href() is False:
            print("请输入正确的m3u8地址")
            return

        # 随机文件名
        rand_name = self.get_rand_name()

        # 获取所有ts视频下载地址
        self.url_list = self.get_ts_add()
        if len(self.url_list) == 0:
            print("获取地址失败")
            return
        if self.ts_path is None:
            # 获取程序所在目录
            self.ts_path = os.path.dirname(os.path.realpath(sys.argv[0]))
        ts_name = ts_path + "\\" + rand_name
        print(ts_name)
        if not os.path.exists(ts_name):
            os.makedirs(ts_name)
        print("总计%s个视频" % str(len(self.url_list)))
        # 拼接正确的下载地址开始下载
        if self.test_download_url(self.url_list[0]):
            params = self.get_download_params(head='', dir_name=ts_name, key=self.key_content)
            # 线程池开启线程下载视频
            self.start_download_in_pool(params)
        elif self.test_download_url(self.url_host + self.url_list[0]):
            params = self.get_download_params(head=self.url_host, dir_name=ts_name, key=self.key_content)
            # 线程池开启线程下载视频
            self.start_download_in_pool(params)
        elif self.test_download_url(self.url_path + self.url_list[0]):
            params = self.get_download_params(head=self.url_path, dir_name=ts_name, key=self.key_content)
            # 线程池开启线程下载视频
            self.start_download_in_pool(params)
        else:
            print("地址连接失败")
            running = False
            return
        # 重新下载先前下载失败的视频
        self.download_fail_file()
        print("下载完成")
        if self.check_file(ts_name) is not True:
            print("请手动下载缺失文件并合并")
            print(self.down_fail_list)
            return
        self.merge_file(ts_path, rand_name)

        # 清空下载失败视频列表
        download_fail_list = []
        # 重置任务开始标志
        running = False

    # 检查地址是否合法
    @staticmethod
    def check_href():
        if m3u8_href:
            return True
        else:
            return False

    # 获取随机文件名
    @staticmethod
    def get_rand_name():
        a = "1234567890"
        b = "abcdefghijklmnopqrstuvwxyz"
        aa = []
        bb = []
        for i in range(6):
            aa.append(random.choice(a))
            bb.append(random.choice(b))
        res = "".join(i + j for i, j in zip(aa, bb))
        return res

    # 获取视频下载地址, 该方法可能修改了key_content
    def get_ts_add(self):
        print("获取ts下载地址，m3u8地址:\n%s" % m3u8_href)
        response = request.get(m3u8_href)
        if response is not None:
            response = response.text
        else:
            return []

        if "#EXTM3U" not in response:
            print("这不是一个m3u8的视频链接！")
            return []
        # 得到每一个ts视频链接
        ts_list = re.findall('EXTINF:(.*),\n(.*)\n#', response)
        ts_add = []
        for i in ts_list:
            ts_add.append(i[1])
        if "EXT-X-KEY" in response:
            if self.key_content is None:
                print("视频文件已加密, 正在尝试解密")
                mi = re.findall('#EXT-X-KEY:(.*)\n', response)
                key = re.findall('URI="(.*)"', mi[0])
                print("加密key的链接是: %s" % key[0])
                key_url = key[0]
                key_response = request.get(key_url)
                print("加密key的值是: %s" % key_response.content)
                self.key_content = key_response.content
                # key_content = key_response.text.encode('utf-8')
                # key_content = bytes(key_response.content, 'utf-8')
                print(self.key_content)

                # key_content = key_content.encode('raw_unicode_escape')
                # key_content = key_content.decode()

        return ts_add

    # 测试下载地址
    @staticmethod
    def test_download_url(url):
        print("尝试使用%s下载视频" % url)
        res = request.get(url, max_retry_time=5)
        return res is not None

    # 拼接下载用的参数
    def get_download_params(self, head, dir_name, key):
        i = 0
        params = []
        while i < len(self.url_list):
            index = "%05d" % i
            param = ([head + self.url_list[i], dir_name + "\\" + index + ".ts", key], None)
            params.append(param)
            i += 1
        return params

    # 设置线程池开始下载
    def start_download_in_pool(self, params):
        print("已确认正确地址，开始下载")
        pool = threadpool.ThreadPool(10)
        thread_requests = threadpool.makeRequests(self.download_to_file, params)
        [pool.putRequest(req) for req in thread_requests]
        pool.wait()

    # 下载视频并保存为文件
    def download_to_file(self, url, file_name, key):
        response = request.get(url)
        if response is None:
            self.down_fail_list.append((url, file_name, key))
            return

        # 显示进度条
        view = command.Command()
        command.Command.num += 1
        view.view_bar(command.Command.num, len(self.url_list))

        cont = response.content
        if key is not None:
            # 如果需要解密
            crypto = AES.new(key, AES.MODE_CBC, b'0000000000000000')
            # crypto = AES.new(key, AES.MODE_CBC, key)
            cont = crypto.decrypt(cont)
        with open(file_name, 'wb') as file:
            file.write(cont)

    # 重新下载视频
    def download_fail_file(self):
        if len(self.down_fail_list) > 0:
            for info in self.down_fail_list:
                url = info[0]
                file_name = info[1]
                key = info[2]
                print("正在尝试重新下载%s" % file_name)
                response = request.get(url=url, max_retry_time=50)
                if response is None:
                    print("%s下载失败，请手动下载:\n%s" % (file_name, url))
                    continue
                cont = response.content
                if key is not None:
                    # 如果需要解密
                    crypto = AES.new(key, AES.MODE_CBC, b'0000000000000000')
                    # crypto = AES.new(key, AES.MODE_CBC, key)
                    cont = crypto.decrypt(cont)
                with open(file_name, 'wb') as file:
                    file.write(cont)

    # 检查视频文件是否全部下载完成
    def check_file(self, dir_name):
        path = dir_name
        file_num = 0
        for f_path, f_dir_name, f_names in os.walk(path):
            for name in f_names:
                if name.endswith(".ts"):
                    file_num += 1
        return file_num == len(self.url_list)

    def merge_file(self, ts_path, rand_name):
        file1 = ts_path + 'file1.txt'
        file2 = ts_path + 'file2.txt'
        ts_name = ts_path + '\\' + rand_name
        video_name = ts_path + '\\' + self.video_name
        cmd = 'cd %s && ls *.ts > %s' % (ts_name, file1)
        result = subprocess.run(cmd, shell=True, timeout=10, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        print(result)
        f = open(file1, "r")
        c = f.read()
        f.close()
        c = c.split("\n")
        for i in c:
            if i != '':
                with open(file2, 'a+') as file:
                    i = "file '" + ts_name + "\\" + i + "'\n"
                    file.write(i)
        print("正在合并, 请稍后...")
        cmd = "ffmpeg -f concat -safe 0 -i %s -c copy %s.mp4" % (file2, ts_name)
        print(cmd)
        result = subprocess.run(cmd, shell=True, timeout=100, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        if "Impossible to open" in str(result) or "Invalid" in str(result):
            print("合并失败!")
            return
        # shutil.rmtree(ts_name)
        os.remove(file1)
        os.remove(file2)
        if self.video_name is not None:
            os.rename(ts_name + '.mp4', video_name + '.mp4')
            os.rename(ts_name, video_name)
        print("合并成功!")


if __name__ == "__main__":
    m3u8_href = 'https://1252524126.vod2.myqcloud.com/9764a7a5vodtransgzp1252524126/91c29aad5285890807164109582/drm/v.f146750.m3u8'
    key_content = None
    video_name = '123'
    ts_path = 'E:\\test\\m3\\'
    m3 = M3(m3u8_href, key_content, video_name, ts_path)
    m3.start()
