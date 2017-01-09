# coding=utf-8
from django.shortcuts import render, render_to_response
from django.http import HttpResponse

import mongoConnection
from . import geoProcessor

# Create your views here.
def tagTerm(request):
    # 连接数据库
    conn = mongoConnection.connect_mongodb()

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

    if request.method == 'POST' and "submitTerm" in request.POST:  # 提交术语标注结果
        paperInfo = dataCollection.find_one({'testpaperName': papername})

        segs = []
        termres = []

        # 保存标注者信息
        username = request.POST['username_name']
        paperInfo['relativeUsernames']['term_tagger'] = username

        index = 0
        for question in paperInfo['Questions']:
            for ctext in question[textFieldName]:
                segs.append(" ".join([w + "_" + str(i) for w, i in zip(ctext['segres'], range(len(ctext['segres'])))]))
                ctext['goldterms'] =  request.POST[str(index) + "_term"]
                termres.append(ctext['goldterms'])
                index += 1

        # 修改试卷标注状态
        paperInfo['States']['term'] = True

        dataCollection.save(paperInfo)
        return render_to_response("TagTerm.html",
                                  {'term_tagger': username,
                                   'States': paperInfo['States'],
                                   "restype": u"人工标注",
                                   "seg_term": zip(segs, termres),
                                   'papername': papername,
                                   'papertype': papertype})

    elif request.method == 'POST' and "generateTimeLoc" in request.POST:  # 自动生成时间地点候选标注
        return HttpResponse("暂不支持")

    else:  # 直接显示页面
        paperInfo = dataCollection.find_one({'testpaperName': papername})

        # 标注者信息
        username = None
        if 'relativeUsernames' in paperInfo and 'term_tagger' in paperInfo['relativeUsernames']:
            username = paperInfo['relativeUsernames']['term_tagger']
        elif 'relativeUsernames' in paperInfo and 'timeloc_tagger' in paperInfo['relativeUsernames']:
            username = paperInfo['relativeUsernames']['timeloc_tagger']

        seg = []

        restype = ""
        termres = []

        autoTagFlag = False
        for question in paperInfo['Questions']:
            for ctext in question[textFieldName]:
                # 给分词结果加上index
                seg.append(" ".join([w + "_" + str(i) for w, i in zip(ctext['segres'], range(len(ctext['segres'])))]))

                if paperInfo['States']['term'] == True:  # 有人工标注的时间地点
                    if 'goldterms' in ctext:
                        termres.append(ctext['goldterms'])
                    else:
                        termres.append("")
                else:
                    # 如果没有人工标注的时间，查找是否有自动标注的时间
                    if "auto_term" in ctext:
                        autoTagFlag = True
                        termres.append(" ".join([str(i) for i in ctext['auto_term']]))
                    else:
                        termres.append("")

        if paperInfo['States']['term'] == True:
            restype = u"人工标注"
        elif autoTagFlag == True:
            restype = u"自动标注"
        else:
            restype = u"无标注"

        return render_to_response("TagTerm.html",
                                    {'term_tagger': username,
                                   'States': paperInfo['States'],
                                   "restype": restype,
                                   "seg_term": zip(seg, termres),
                                   'papername': papername,
                                   'papertype': papertype})
