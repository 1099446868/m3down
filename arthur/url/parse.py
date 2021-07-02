# 获取域名
def get_host(url):
    url_param = url.split("//")
    return url_param[0] + "//" + url_param[1].split("/")[0] + "/"


# 获取目录
def get_dir(url):
    host = get_host(url)
    url = url.replace(host, '')
    return ("/" + url[0:url.rfind("/")] + "/").replace("//", "/")


# 获取域名+路径
def get_path(url):
    if url.rfind("/") != -1:
        return url[0:url.rfind("/")] + "/"
    else:
        return url[0:url.rfind("\\")] + "\\"