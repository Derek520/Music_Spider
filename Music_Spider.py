# -*- coding:utf-8 -*-
from multiprocessing import Process
import re,json,time
import requests
from threading import Thread
from lxml import etree
from pymongo import MongoClient
from fake_useragent import UserAgent

"""
网易云爬取全部音乐的歌词：
从语种入口爬取：'华语', '韩语', '粤语', '小语种','欧美', '日语'
每个语种开启一个子进程，
先获取每个语种的第一页url,提取最大页码
遍历最大页码，每页开启一个子线程
将每一首歌词存入mongo数据库
"""


client = MongoClient()
col = client["music"]

class Music_Spider(object):
    def __init__(self,cat):
        super().__init__()
        self.start_url = 'http://music.163.com/discover/playlist/?order=hot&cat='+cat+'&limit=35&offset={}' # 每个语种
        self.detail_url = 'http://music.163.com/api/song/lyric?id={}&lv=1&kv=1&tv=-1'  # 是歌词api接口
        self.session = requests.session()
        self.headers = {'User-Agent': UserAgent().random,
                        'Referer':'http://music.163.com/'}
        self.count = 0
        self.cat = cat  # 对象属性接收语种
        self.col = col[self.cat] #根据语种创建集合
        self.time = 60  #请求页面超时时间
        self.sing = re.compile(r'\[.*\](.*)')   #提取歌词的正则表达式


    def get_url_list(self,page=0):
        '''获取url_list'''
        resp = self.session.get(self.start_url.format(page*35),headers=self.headers,timeout=self.time) #请求每页url
        print(resp.request.url)
        html = etree.HTML(resp.content.decode())
        # 提取每页中的音乐url列表
        list_url = ['http://music.163.com' + url for url in html.xpath('//ul[@id="m-pl-container"]/li/div/a/@href')]
        if page == 0:  #首页  提取最大页码
            end_page = html.xpath('//div[@id="m-pl-pager"]/div/a[@class="zpgi"]/text()')[-1]
            return end_page, list_url

        # return list_url
        self.parse_url(list_url)


    def parse_url(self,list_url):
        '''获取每一首歌的id'''
        detail_url_list = []
        for url in list_url:
            # print(url)
            html = self.session.get(url,headers=self.headers,timeout=self.time)
            data = html.content.decode()
            '<a href="/song?id=532711051"><b title="Rewind">R<div class="soil">r4</div>ewind</b></a>'
            # 正则提取歌的id
            com = re.compile(r'<li><a href="/song\?id=(.*?)">.*?</a></li>')
            song_list = [url for url in com.findall(data)]
            detail_url_list.extend(song_list)

        print(len(detail_url_list))

        # return detail_url_list
        self.detail_url_list(detail_url_list)

    def detail_url_list(self,detail_url):
        '''根据歌id,获取歌词'''
        list_data = []
        for id in detail_url:
            resp = self.session.get(self.detail_url.format(id),headers=self.headers,timeout=self.time)
            # print(resp.request.url)
            resp_json = json.loads(resp.content.decode())
            try:

                data = resp_json['lrc']['lyric']
                sing = self.sing.findall(data)
                # print(sing)
                # self.save_data(data)
                self.count +=1
            except Exception as e:
                pass
            else:
                # 如果有歌词,则存入Mongo数据库
                self.col.insert({"content":sing})
                print('{}---第{}条'.format(self.cat,self.count))



    # def save_data(self,data):
    #     '''保存数据'''
    #     data = json.dumps(data,ensure_ascii=False,indent=2)
    #     # print(data)
    #     with open('网易云音乐.txt','a') as f:
    #         f.write(data)
    #         f.write('\n')

    def run(self,cat):

        print('-----开始--{}--下载-----'.format(self.cat))
        end_page,list_url = self.get_url_list()
        self.parse_url(list_url)

        # detail_url = self.parse_url(list_url)

        # self.detail_url_list(detail_url)
        thd_list=[]
        for page in (1,int(end_page)+1):

            # self.get_url_list(page)
            td = Thread(target=self.get_url_list, args=(page,))
            td.setDaemon(True)
            td.start()
            thd_list.append(td)

        for t in thd_list:
            t.join()


if __name__ == '__main__':
    cats = ['华语', '韩语', '粤语', '小语种','欧美', '日语']
    pro_list = []
    start_time = time.time()
    for cat in cats:
        ms = Music_Spider(cat)
        p = Process(target=ms.run,args=(cat,))
        p.start()
        pro_list.append(p)
        # ms.run()

    for p in pro_list:
        p.join()

    end_time = time.time()
    print('用时{}s'.format(end_time-start_time))