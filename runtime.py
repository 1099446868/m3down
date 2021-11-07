import sys
import os
import random
import re
import threadpool

from PyQt5.QtCore import QThread, pyqtSignal, QBasicTimer
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox

from m3down import Ui_Form
from sniffer import Sniffer

import subprocess
from Crypto.Cipher import AES

sys.path.append(r"E:\python")

from arthur.url import parse as url
from arthur.request import request
from arthur.sys import command


class MyMainForm(QMainWindow, Ui_Form):
    _source = '91'
    _is_spider = True
    _href = ''
    _running = False
    step = 0
    total = 0

    def __init__(self, parent=None):
        super(MyMainForm, self).__init__(parent)
        # 构建一个计时器
        self.timer = QBasicTimer()
        self.setupUi(self)
        # m3u8_href = 'https://1252524126.vod2.myqcloud.com/9764a7a5vodtransgzp1252524126/91c29aad5285890807164109582/drm/v.f146750.m3u8'
        # self.lineEdit.setText(m3u8_href)
        self.pushButton.clicked.connect(self.getComboxBoxValue)

    def getComboxBoxValue(self):
        if self._running is True:
            QMessageBox.about(self, "警告", "任务执行中，请勿重复开启任务!")
            return
        # 计数, 调用一次+1
        self.step = 0
        self.total = 0
        self._source = self.comboBox.currentText()
        is_spider = self.comboBox_2.currentText()
        if is_spider == '不嗅探':
            self._is_spider = False
        self._href = self.lineEdit.text()
        if self._href == '':
            QMessageBox.about(self, "警告", "请输入网址或者视频地址!")
            return
        # # 开启线程执行耗时操作，防止GUI卡顿
        # t = threading.Thread(target=Runtime.start, args=(self._href,))
        # # 设置守护线程，进程退出不用等待子线程完成
        # t.setDaemon(True)
        # t.start()
        # 创建线程
        self.thread = Runtime(self._href, self._is_spider, self._source)
        # 连接信号
        self.thread.signal.connect(self.flush)
        # 启动线程
        self.thread.start()

    def flush(self, no, msg):
        if no == 200:
            self.alert(msg)
        if no == 201:
            self.alert("\n\n")
            self.stopTask()
        if no == 202:
            self._running = True
        elif no == 204:
            self.clear_alert()
        elif no == 300:
            # 判断是否处于激活状态
            if self.timer.isActive():
                self.timer.stop()
            else:
                self.timer.start(100, self)
        elif no == 301:
            self.total = int(msg)
        elif no == 400:
            self.stopTask()
            QMessageBox.about(self, "警告", msg)

    def alert(self, content):
        self.textEdit.setText(self.textEdit.toPlainText() + "\n" + content)

    def clear_alert(self):
        self.textEdit.setText('')
        self.lineEdit.setText('')

    def timerEvent(self, *args, **kwargs):
        s = round(self.step / self.total * 100)
        if s >= 100:
            # 停止进度条
            self.timer.stop()
            return
        self.step += 1
        # 把进度条每次充值的值赋给进图条
        self.progressBar.setValue(s)

    def stopTask(self):
        self.step = 0
        self.total = 0
        self.progressBar.setValue(0)
        self._running = False


class Runtime(QThread):
    signal = pyqtSignal(int, str)  # 括号里填写信号传递的参数
    _href = ''
    _m3u8_href = ''
    video_name = None
    key_content = None
    url_host = ''
    url_path = ''
    # 存放ts目录的目录
    ts_path = 'E:\\test\\m3\\'
    # 所有的ts链接列表
    url_list = []
    # 下载失败的链接列表
    down_fail_list = []

    def __init__(self, href, is_spider, source):
        super(Runtime, self).__init__()
        if is_spider:
            # 嗅探, 加载嗅探器
            sniffer = Sniffer(href, source)
            [m3u7_href, video_name] = sniffer.start()
            video_name = video_name.replace('[原创]', '')
            video_name = video_name.replace(' ', '')
            video_name = video_name.replace('，', '')
            video_name = video_name.replace('。', '')
            video_name = video_name.replace('！', '')
            video_name = video_name.replace('？', '')
            video_name = video_name.replace('（', '')
            video_name = video_name.replace('）', '')
            video_name = video_name.replace('“', '')
            video_name = video_name.replace('”', '')
            video_name = video_name.replace('<imgsrc="images/91.png">', '')
            video_name = video_name.strip()
            self._m3u8_href = m3u7_href
            self.video_name = video_name
        else:
            self._m3u8_href = href
        self.url_host = url.get_host(self._m3u8_href)
        self.url_path = url.get_path(self._m3u8_href)

    def __del__(self):
        self.wait()

    # 进行任务操作
    def run(self):
        self.signal.emit(202, '')  # 任务开始的标志
        if self.video_name is not None:
            self.signal.emit(200, "嗅探到: %s" % self.video_name)
        # 检查地址是否合法
        if self.check_href() is False:
            self.signal.emit(400, "请输入正确的m3u8地址")
            return
        # 随机文件名
        rand_name = self.get_rand_name()

        # 获取所有ts视频下载地址
        self.url_list = self.get_ts_add()
        if len(self.url_list) == 0:
            self.signal.emit(400, "获取地址失败")
            return
        if self.ts_path is None:
            # 获取程序所在目录
            self.ts_path = os.path.dirname(os.path.realpath(sys.argv[0]))
        ts_name = self.ts_path + "\\" + rand_name
        self.signal.emit(200, "ts_name: %s" % ts_name)
        if not os.path.exists(ts_name):
            os.makedirs(ts_name)
        self.signal.emit(200, "总计%s个视频" % str(len(self.url_list)))
        self.signal.emit(301, str(len(self.url_list)))
        # 拼接正确的下载地址开始下载
        if self.test_download_url(self.url_path + self.url_list[0]):
            params = self.get_download_params(head=self.url_path, dir_name=ts_name, key=self.key_content)
            # 线程池开启线程下载视频
            self.start_download_in_pool(params)

        elif self.test_download_url(self.url_host + self.url_list[0]):
            params = self.get_download_params(head=self.url_host, dir_name=ts_name, key=self.key_content)
            # 线程池开启线程下载视频
            self.start_download_in_pool(params)
        elif self.test_download_url(self.url_list[0]):
            params = self.get_download_params(head='', dir_name=ts_name, key=self.key_content)
            # 线程池开启线程下载视频
            self.start_download_in_pool(params)
        else:
            print("地址连接失败")
            return
        # 重新下载先前下载失败的视频
        self.download_fail_file()
        self.signal.emit(200, "下载完成")
        if self.check_file(ts_name) is not True:
            self.signal.emit(200, "请手动下载缺失文件并合并")
            print(self.down_fail_list)
            return
        self.merge_file(self.ts_path, rand_name)

    # 检查地址是否合法
    def check_href(self):
        if self._m3u8_href:
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
        self.signal.emit(200, "获取到ts下载地址")
        response = request.get(self._m3u8_href)
        if response is not None:
            response = response.text
        else:
            return []

        if "#EXTM3U" not in response:
            print("这不是一个m3u8的视频链接！")
            self.signal.emit(400, "这不是一个m3u8的视频链接")
            return []
        # 得到每一个ts视频链接
        ts_list = re.findall('EXTINF:(.*),\n(.*)\n#', response)
        ts_add = []
        for i in ts_list:
            ts_add.append(i[1])
        if "EXT-X-KEY" in response:
            if self.key_content is None:
                self.signal.emit(200, "视频文件已加密, 正在尝试解密")
                mi = re.findall('#EXT-X-KEY:(.*)\n', response)
                key = re.findall('URI="(.*)"', mi[0])
                # self.signal.emit(200, "加密key的链接是: %s" % key[0])
                print(key)
                key_url = key[0]
                key_response = request.get(key_url)
                self.signal.emit(200, "加密key的值是: %s" % key_response.content)
                self.key_content = key_response.content
                # key_content = key_response.text.encode('utf-8')
                # key_content = bytes(key_response.content, 'utf-8')

                # key_content = key_content.encode('raw_unicode_escape')
                # key_content = key_content.decode()

        return ts_add

    # 测试下载地址
    def test_download_url(self, url):
        self.signal.emit(200, "尝试下载视频")
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
        self.signal.emit(200, "已确认正确地址，开始下载")
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
        # view = command.Command()
        # command.Command.num += 1
        # view.view_bar(command.Command.num, len(self.url_list))
        self.signal.emit(300, '')

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
        import time
        if len(self.down_fail_list) > 0:
            for info in self.down_fail_list:
                url = info[0]
                file_name = info[1]
                key = info[2]
                self.signal.emit(200, "正在尝试重新下载%s" % file_name)
                response = request.get(url=url, max_retry_time=3)
                if response is None:
                    # self.signal.emit(200, "%s下载失败，请手动下载:\n%s" % (file_name, url))
                    time.sleep(1)
                    self.down_fail_list.append((url, file_name, key))
                    continue
                cont = response.content
                if key is not None:
                    # 如果需要解密
                    crypto = AES.new(key, AES.MODE_CBC, b'0000000000000000')
                    # crypto = AES.new(key, AES.MODE_CBC, key)
                    cont = crypto.decrypt(cont)
                with open(file_name, 'wb') as file:
                    file.write(cont)
                self.signal.emit(300, '')
                self.down_fail_list.remove(info)
            if len(self.down_fail_list) > 0:
                self.download_fail_file()

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
        if self.video_name is not None:
            video_name = ts_path + '\\' + self.video_name
        else:
            video_name = ts_name
        cmd = 'cd %s && ls *.ts > %s' % (ts_name, file1)
        self.signal.emit(200, cmd)
        result = subprocess.run(cmd, shell=True, timeout=10, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        f = open(file1, "r")
        c = f.read()
        f.close()
        c = c.split("\n")
        for i in c:
            if i != '':
                with open(file2, 'a+') as file:
                    i = "file '" + ts_name + "\\" + i + "'\n"
                    file.write(i)
        self.signal.emit(200, "正在合并, 请稍后...")
        cmd = "ffmpeg -f concat -safe 0 -i %s -c copy %s.mp4" % (file2, video_name)
        print(cmd)
        self.signal.emit(200, cmd)
        result = subprocess.run(cmd, shell=True, timeout=100, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        if "Impossible to open" in str(result) or "Invalid" in str(result):
            self.signal.emit(200, "合并失败!")
            return
        # print(ts_name + '.mp4')
        # print(video_name + '.mp4')
        if self.video_name is not None:
            # os.rename(ts_name + '.mp4', video_name + '.mp4')
            os.rename(ts_name, video_name)
        os.remove(file1)
        os.remove(file2)
        self.del_file(ts_name)
        self.signal.emit(200, "合并成功!, 新文件是: %s" % video_name)
        self.signal.emit(201, "finished")  # 任务完成
        self.signal.emit(204, '')

    def del_file(self, filepath):
        """
        删除某一目录下的所有文件或文件夹
        :param filepath: 路径
        :return:
        """
        del_list = os.listdir(filepath)
        import shutil
        for f in del_list:
            file_path = os.path.join(filepath, f)
            if os.path.isfile(file_path):
                os.remove(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        shutil.rmtree(filepath)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    myWin = MyMainForm()
    myWin.show()
    sys.exit(app.exec_())
