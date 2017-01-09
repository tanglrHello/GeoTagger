# coding=utf-8
from django.shortcuts import render_to_response
import pymongo
import mongoConnection

from . import getConfig


def statistic(request):
    # 连接数据库
    conn = mongoConnection.connect_mongodb()

    geopaper_db = conn['GeoPaper']

    papertype = request.GET['papertype']

    data_collection = None
    text_field_name = None
    template_info = None
    if papertype == "choice":
        data_collection = geopaper_db['ChoiceData']
        text_field_name = "combinedTexts"
        # 获取模板配置信息
        template_info = getConfig.getNewTemplateConfig(papertype)
    elif papertype == "subjective":
        data_collection = geopaper_db['SubjectiveData']
        text_field_name = "subQuestions"
        # 获取模板配置信息
        template_info = getConfig.getTemplateConfig(papertype)

    # extract template chinese names
    template_names = [info[0].decode('utf-8') for info in template_info]

    # maintain the statistic data
    paper_info = []
    template_dict = {}

    for tn in template_names:
        template_dict[tn] = 0  # record the number of each template

    for paper in data_collection.find().sort("uploadTimestamp", pymongo.DESCENDING):
        paper_name = paper['testpaperName']

        # the first record the total combinedChoice number; the second is for tagged number
        paper_info.append([paper_name, 0, 0])

        for question in paper['Questions']:
            for text_info in question[text_field_name]:
                paper_info[-1][1] += 1
                if 'topTemplate' in text_info and text_info['topTemplate'] != "" or \
                   'secondTemplate' in text_info and text_info['secondTemplate'] != "":
                    paper_info[-1][2] += 1

                if 'topTemplate' in text_info and text_info['topTemplate'] != "":
                    ttype = text_info['topTemplateTypes']
                    for tname in ttype:
                        if tname in template_names:
                            template_dict[tname] += 1

                if 'secondTemplate' in text_info and text_info['secondTemplate'] != "":
                    ttype = text_info['secondTemplateTypes']
                    for tname in ttype:
                        if tname in template_names:
                            template_dict[tname] += 1

    # count the total combinedChoice number
    total_num = 0
    total_tagged_num = 0
    for info in paper_info:
        total_num += info[1]
        total_tagged_num += info[2]
    paper_info.append([u'所有试卷总计', total_num, total_tagged_num])

    template_info = [[template_name, num, '%.2f%%' % (num*100.0/total_tagged_num)]
                     for template_name, num in template_dict.items()]

    return render_to_response("Statistic.html", {'paper_info': paper_info,
                                                 'template_info': template_info})
