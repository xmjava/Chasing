#!/usr/bin/python3
# 自动追剧脚本 by suzh@xmjava

import yaml
import configparser
import datetime
from zoneinfo import ZoneInfo
from urllib.parse import quote
import requests
import xml.dom.minidom
import json
import os
import logging
from logging import handlers
import sys
import time

__DEBUG_MODE__ = True
MAX_NETWORK_ERROR_RETRY_COUNT = 3 # 网络错误最多重试3次
logger = None

test_mode = False

# yaml键值
GLOBAL = "global"
RSS = "rss"
PROXY = "proxy"
DRAMAS = "dramas"
DRAMA = "drama"
NAME = "name"
SEASON = "season"
EPISODES = "episodes"
KEYWORDS = "keywords"
SCHEDULES = "schedules"
START = "start"
QBITTORRENT = "qbittorrent"
ARIA2 = "aria2"
DOWNLOAD = "download"
USERNAME = "username"
PASSWORD = "password"
WEEK = "week"
WEEKS_DICT = {"mon" : 0, "tue" : 1, "wed" : 2, "thu" : 3, "fri" : 4, "sat" : 5, "sun" : 6}

CONFIG_FILE = "chasing.yml"
DRAMA_SEEN_FILE = "chasing.seen"
full_config_file_path = None
full_drama_seen_file_path = None

rss_base_url = None
proxy = None
download = None
drama_task_list = []
qbittorrent_config = None
aria2_config = None

# print文字颜色定义
ERROR = 31
VERBOSE = 32
WARNING = 33

# 加载并解析配置文件
def load_config(yaml_file):
    print_c("Loading config file...", VERBOSE)
    with open(yaml_file, encoding='utf-8') as file:
        content = file.read()
        # print(content)
        data = yaml.load(content, Loader=yaml.FullLoader)
        # print(data)

        global rss_base_url
        global proxy
        global download
        global drama_task_list
        global qbittorrent_config
        global aria2_config

        rss_base_url = data.get(GLOBAL).get(RSS)
        proxy = data.get(GLOBAL).get(PROXY)
        download = data.get(GLOBAL).get(DOWNLOAD)
        qbittorrent_config = data.get(GLOBAL).get(QBITTORRENT)
        aria2_config = data.get(GLOBAL).get(ARIA2)
        drama_task_list = data.get(DRAMAS)
        for i in range(len(drama_task_list)):
            drama = drama_task_list[i].get(DRAMA)
            print_c(f"drama: {drama.get(NAME)}", VERBOSE)

    print_c("Load config file done.", VERBOSE)

# 执行任务
def run_drama_task(task_data):
    print_c(f"========== Start task for drama: {task_data.get(NAME)} ==========", VERBOSE)
    # 如果设置了首播时间，判断是否在首播时间后 >= start
    now_date = datetime.datetime.now().date()
    start_date = task_data.get(START)
    if start_date and now_date < start_date:
        print_c("This season hasn't started yet, end this task!", WARNING)
        return

    # 获取已下载的集数
    episode_downloaded = get_drama_progress(task_data)
    # 判断剧集是否已结束
    if (episode_downloaded >= task_data.get(EPISODES)):
        print_c("This season has ended, please remove the configuration!", WARNING)
        return
    current_episode = episode_downloaded + 1

    # 判断是否设定了改集的上线时间
    current_episode_str = format_episode(current_episode)
    schedules = task_data.get(SCHEDULES)
    if schedules:
        is_in_episode_day = False
        is_in_episode_week = False
        for i in range(len(schedules)):
            for key, value in schedules[i].items():
                if key == current_episode_str:
                    if now_date >= value:
                        print_d(f"matched schedule day: {value}")
                        is_in_episode_day = True # 匹配到上线时间，按日期
                elif WEEK == key:
                    weeks = str(value).split(',')
                    for week in weeks:
                        if now_date.weekday() == WEEKS_DICT[week]:
                            print_d(f"matched schedule week: {value}")
                            is_in_episode_week = True # 匹配到上线时间，按周几
        if is_in_episode_day == False and is_in_episode_week == False:
            print_c("Not in the validity episode date, end this task!", WARNING)
            return

    current_season_episode_str = format_season(task_data.get(SEASON)) + current_episode_str
    print_c(f"Searching magnet link for {task_data.get(NAME)} {current_season_episode_str}", VERBOSE)
    # 拼接搜索URL
    keywords = task_data.get(KEYWORDS)
    if keywords == None:
        keywords = ""
    keywords_list = keywords.split('|') # 支持多组关键字，用|分隔，按顺序搜索，匹配到某一组就不再继续搜索下一组
    for keywords in keywords_list:
        search_url = rss_base_url + quote(task_data.get(NAME) + " " + current_season_episode_str + " " + keywords.replace(',', ' '))
        print_d(search_url)
        # 判断是否使用代理服务器
        proxies = None
        if proxy != None and proxy != '':
            print_c(f"Using proxy: {proxy}", VERBOSE)
            proxies = {
                'http': proxy,
                'https': proxy
            }

        # 搜索磁力链接
        search_result = None
        network_error_retry_count = 0
        while search_result == None and network_error_retry_count < MAX_NETWORK_ERROR_RETRY_COUNT:
            try:
                search_result = requests.get(search_url, headers={'User-Agent': 'Mozilla/5.0'}, proxies=proxies)
                search_result.raise_for_status()
            except:
                network_error_retry_count += 1
                if network_error_retry_count >= MAX_NETWORK_ERROR_RETRY_COUNT:
                    print_c(f"Network error, end '{task_data.get(NAME)}' task!", ERROR)
                    return
                search_result = None
                time.sleep(1) # 等待1秒重试

        # 解析rss结果
        try:
            # print(search_result.text)

            DOMTree = xml.dom.minidom.parseString(search_result.text)
            collection = DOMTree.documentElement
            items = collection.getElementsByTagName('item')
            if items and len(items) > 0:
                item = items[0]
                # print(item)
                title = item.getElementsByTagName('title')[0].childNodes[0].data
                magnet_link = item.getElementsByTagName('link')[0].childNodes[0].data
                print_c(f"Found: {title}", VERBOSE)
                print_c(f"Magnet link is: {magnet_link}", VERBOSE)

                if test_mode:
                    # 测试模式不进行下载
                    print_c("Ignore download in test mode.", WARNING)
                    return
                # 将磁力链接发送到设定的下载工具
                if download_magnet_link(task_data, magnet_link):
                    print_c("Download started.", VERBOSE)
                    # 添加下载成功，保存已下载进度
                    save_drama_progress(task_data, current_episode)
                else:
                    print_c("Download magnet link failed!", ERROR)
                return
            else:
                print_c("No any search result!", WARNING)
        except:
            print_c("Can not parse search result!", ERROR)

# 获取当前应下载的集数 / 已经下载到哪一集
def get_drama_progress(task_data):
    name = task_data.get(NAME)
    season = format_season(task_data.get(SEASON))
    config = configparser.RawConfigParser()
    config.optionxform = lambda option: option # 解决configparser自动变小写问题
    config.read(full_drama_seen_file_path)
    if name in config:
        if season in config[name]:
            episode_downloaded =config[name][season]
            # print(episode_downloaded)
            return int(episode_downloaded)
    return 0

# 保存当前下载到到哪一集
def save_drama_progress(task_data, episode_downloaded: int):
    season = format_season(task_data.get(SEASON))
    config = configparser.RawConfigParser()
    config.optionxform = lambda option: option # 解决configparser自动变小写问题
    config.read(full_drama_seen_file_path)
    config[task_data.get(NAME)] = {
        season: episode_downloaded
    }
    with open(full_drama_seen_file_path, 'w') as progress_file:
        config.write(progress_file)

# 下载磁力链接
def download_magnet_link(task_data, magnet_link):
    try:
        if task_data.get(DOWNLOAD) == QBITTORRENT and qbittorrent_config:
            return download_thru_qbittorrent(magnet_link)
        elif task_data.get(DOWNLOAD) == ARIA2 and aria2_config:
            return download_thru_aria2(magnet_link)
        elif download == QBITTORRENT and qbittorrent_config:
            return download_thru_qbittorrent(magnet_link)
        elif download == ARIA2 and aria2_config:
            return download_thru_aria2(magnet_link)
        else:
            print_c("Please set download config first!", ERROR)
    except:
        return False
    return False

# 往qBittorrent添加磁力下载任务
def download_thru_qbittorrent(magnet_link):
    if qbittorrent_config:
        cookies = None
        username = qbittorrent_config.get(USERNAME)
        password = qbittorrent_config.get(PASSWORD)
        if username and password:
            # 需要验证账号
            qbittorrent_api_url = "http://" + qbittorrent_config.get("host") + ":" + str(qbittorrent_config.get("port")) + "/api/v2/auth/login"
            print_d(qbittorrent_api_url)
            post_data = {'username' : username,
                         'password' : password}
            result = requests.post(qbittorrent_api_url, data = post_data)
            print_d(result.text)
            if result.text.find('Ok') == -1:
                print_c("qBittorrent auth failed!", ERROR)
                return False
            cookies = result.cookies
        print_d(cookies)
        
        qbittorrent_api_url = "http://" + qbittorrent_config.get("host") + ":" + str(qbittorrent_config.get("port")) + "/api/v2/torrents/add"
        post_data = {'urls' : magnet_link}
        print_d(qbittorrent_api_url)
        result = requests.post(qbittorrent_api_url, data = post_data, cookies = cookies)
        print_d(result.text)
        if result.text.find('Ok') != -1:
            return True
        else:
            print_c("qBittorrent call failed!", ERROR)
    return False

# 往Aria2添加磁力下载任务
def download_thru_aria2(magnet_link):
    if aria2_config:
        jsonreq = f'{{"jsonrpc":"2.0", "id":"xmjava", "method":"aria2.addUri", "params":[["{magnet_link}"]]}}'
        secret = aria2_config.get("secret")
        if secret:
            jsonreq = f'{{"jsonrpc":"2.0", "id":"xmjava", "method":"aria2.addUri", "params":["token:{secret}", ["{magnet_link}"]]}}'
        print_d(jsonreq)
        aria2_rpc_url = "http://" + aria2_config.get("host") + ":" + str(aria2_config.get("port")) + "/" + aria2_config.get("rpc_path")
        print_d(aria2_rpc_url)
        headers = {'Content-Type': 'application/json-rpc'}
        result = requests.post(aria2_rpc_url, headers = headers, data = jsonreq)
        print_d(result.text)
        result_data = json.loads(result.text)
        if 'error' in result_data:
            print_c("Aria2 call failed!", ERROR)
            return False
        return True
    return False

# 返回格式化的episode
def format_episode(episode: int):
    return "E" + "{:0>2d}".format(episode)

# 返回格式化的season
def format_season(season: int):
    return "S" + "{:0>2d}".format(season)

# 带颜色的print，日志输出
def print_c(content, color = 0):
    if color == VERBOSE:
        logger.info(content)
    elif color == WARNING:
        logger.warning(content)
    elif color == ERROR:
        logger.error(content)

    if isinstance(color, int):
        color = str(color)
    print(f"\033[1;{color}m{content}\033[0m")

# 调试输出，日志输出
def print_d(content):
    if __DEBUG_MODE__:
        logger.debug(content)
        print(content)

# 主代码
def main():
    # 处理命令行参数
    global test_mode
    if len(sys.argv) == 2:
        if "test" == sys.argv[1]:
            test_mode = True # 测试模式下不会进行下载

    global full_config_file_path
    global full_drama_seen_file_path
    # 获取脚本所在目录
    script_path = os.path.split(os.path.realpath(__file__))[0]
    full_config_file_path = script_path + "/" + CONFIG_FILE
    full_drama_seen_file_path = script_path + "/" + DRAMA_SEEN_FILE

    # 配置日志输出
    full_logging_file_path = script_path + "/" + "chasing.log"
    global logger
    logger = logging.getLogger("chasing")
    if __DEBUG_MODE__:
        logger.setLevel(level = logging.DEBUG)
    else:
        logger.setLevel(level = logging.INFO)
    formatter = logging.Formatter("%(asctime)s - [%(levelname)s]: %(message)s")
    formatter.converter = lambda *args: datetime.datetime.now(tz=ZoneInfo('Asia/Shanghai')).timetuple() # 处理日志时区问题
    # 按天分割日志
    time_rotating_file_handler = handlers.TimedRotatingFileHandler(filename = full_logging_file_path, when = 'MIDNIGHT', backupCount = 7)
    time_rotating_file_handler.setFormatter(formatter)
    logger.addHandler(time_rotating_file_handler)

    # 加载配置文件
    load_config(full_config_file_path)
    
    # 执行任务
    for i in range(len(drama_task_list)):
        drama_task_data = drama_task_list[i].get(DRAMA)
        run_drama_task(drama_task_data)

if __name__ == "__main__":
    main()
