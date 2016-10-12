# coding=utf-8
from django.shortcuts import render, render_to_response
from django.http import HttpResponse

import pymongo
import time

from . import geoProcessor


# Create your views here.
def tagBackground(request):
    # 连接数据库
    configFile = open("static/config.txt", 'r')
    mongoIP = configFile.readline().split("\t")[1].strip()
    mongoPort = int(configFile.readline().split("\t")[1].strip())
    conn = pymongo.Connection(mongoIP, mongoPort)

    GeopaperDB = conn['GeoPaper']

    papername = request.GET['papername']
    papertype = request.GET['papertype']

    dataCollection = None
    textFieldName = None
    if papertype == "choice":
        dataCollection = GeopaperDB['ChoiceData']
        textFieldName = "combinedTexts"
    elif papertype == "subjective":
        dataCollection = GeopaperDB['SubjectiveData']
        textFieldName = "subQuestions"

    paperInfo = dataCollection.find_one({'testpaperName': papername})

    if not paperInfo:
        return HttpResponse("没有这份试卷")
    # 必须是手动分词标注完了才来标注时间地点(这里使用粗粒度的版本)
    if paperInfo['States']['seg'] == False:
        return HttpResponse("请先完成对改试卷的分词标注")


    if request.method == 'POST' and "submitBackground" in request.POST:  # 提交标注结果
        paperInfo = dataCollection.find_one({'testpaperName': papername})

        segs = []
        delete_part = []
        context = []

        # 保存标注者信息
        username = request.POST['username_name']
        paperInfo['relativeUsernames']['background_tagger'] = username

        index = 0
        for question in paperInfo['Questions']:
            for ctext in question[textFieldName]:
                segs.append(" ".join([w + "_" + str(i) for w, i in zip(ctext['segres'], range(len(ctext['segres'])))]))

                ctext["delete_part"] = request.POST[str(index) + "_delete_part"]
                ctext["context"] = request.POST[str(index) + "_context"]

                delete_part.append(ctext['delete_part'])
                context.append(ctext['context'])

                index += 1

        # 修改试卷标注状态
        paperInfo['States']['background'] = True

        dataCollection.save(paperInfo)
        return render_to_response("TagBackground.html",
                                  {'background_tagger': username,
                                   'States': paperInfo['States'],
                                   "restype": u"人工标注",
                                   "seg_taohua_context": zip(segs, delete_part, context),
                                   'papername': papername,
                                   'papertype': papertype})
    else:  # 直接显示页面
        paperInfo = dataCollection.find_one({'testpaperName': papername})

        # 标注者信息
        username = None
        if 'relativeUsernames' in paperInfo and 'background_tagger' in paperInfo['relativeUsernames']:
            username = paperInfo['relativeUsernames']['background_tagger']
        segs = []
        delete_part = []
        context = []

        restype = ""

        for question in paperInfo['Questions']:
            for ctext in question[textFieldName]:
                # 给分词结果加上index
                segs.append(" ".join([w + "_" + str(i) for w, i in zip(ctext['segres'], range(len(ctext['segres'])))]))

                if 'background' in paperInfo['States'] and paperInfo['States']['background'] == True:  # 有人工标注的
                    restype = u"人工标注"
                    if 'delete_part' in ctext:
                        delete_part.append(ctext['delete_part'])
                    else:
                        delete_part.append("")

                    if "context" in ctext:
                        context.append(ctext['context'])
                    else:
                        context.append("")
                else:
                    delete_part.append("")
                    context.append("")
                    restype = u"无标注"

        if username == None:
            return render_to_response("TagBackground.html",
                                      {'States': paperInfo['States'],
                                       "restype": restype,
                                       "seg_taohua_context": zip(segs, delete_part, context),
                                       'papername': papername,
                                       'papertype': papertype})
        else:
            return render_to_response("TagBackground.html",
                                      {'background_tagger': username,
                                       'States': paperInfo['States'],
                                       "restype": restype,
                                       "seg_taohua_context": zip(segs, delete_part, context),
                                       'papername': papername,
                                       'papertype': papertype})
