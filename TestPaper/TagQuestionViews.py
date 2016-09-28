# coding=utf-8
from django.shortcuts import render, render_to_response
from django.http import HttpResponse, HttpResponseRedirect

from . import getConfig
from . import geoProcessor

import pymongo
import time, json
import traceback


# Create your views here.
def tagQuestion(request):
    # 连接数据库
    configFile = open("static/config.txt", 'r')
    mongoIP = configFile.readline().split("\t")[1].strip()
    mongoPort = int(configFile.readline().split("\t")[1].strip())
    conn = pymongo.Connection(mongoIP, mongoPort)

    GeopaperDB = conn['GeoPaper']

    papername = request.GET['papername']
    papertype = request.GET['papertype']

    nextIndex = None  # 下一句的index，用于“保存并下一句”的功能中

    paperInfo = None
    dataCollection = None
    globalIndex = None
    globalIndexFieldName = None
    if papertype == "choice":
        dataCollection = GeopaperDB['ChoiceData']
        globalIndexFieldName = "combinedChoiceIndex"
        globalIndex = request.GET['combinedChoiceIndex']
        textFieldName = "combinedTexts"
    elif papertype == "subjective":
        dataCollection = GeopaperDB['SubjectiveData']
        globalIndexFieldName = "subQuestionIndex"
        globalIndex = request.GET['subQuestionIndex']
        textFieldName = "subQuestions"

    paperInfo = dataCollection.find_one({'testpaperName': papername})

    if not paperInfo:
        return HttpResponse("没有这份试卷")

    result = checkAndFindTextInfoInDB(papername, papertype, globalIndex)
    if result == False:
        return HttpResponse("<h1>非法访问，该试卷没有这个选项文本")
    else:
        textInfo = result[0]
        questionIndex = result[1]
        lastIndex = result[2]
        nextIndex = result[3]
        allValidIndex = result[4]
        fullQuestion = result[5]
        isFirstSubQuestion = result[6]
        if papertype == "choice":
            # 将text拆成题面和选项，供前端显示
            textInfo['timian'] = textInfo['text'].split("\t")[0]
            textInfo['xuanxiang'] = textInfo['text'].split("\t")[1]
            textInfo['combinedTextWithoutTab'] = textInfo['text'].replace("\t", "")

    username = request.COOKIES.get("username", "")

    if request.method == 'GET':
        if textInfo['segres'] == []:
            return HttpResponse("请先完成对该句的分词标注")

        # 分词结果
        textInfo['segres'] = " ".join(
            [w + "_" + str(i) for w, i in zip(textInfo['segres'], range(len(textInfo['segres'])))])

        if 'choice_type' not in textInfo:
            textInfo['choice_type']=""
        if 'qiandao_type' not in textInfo:
            textInfo['qiandao_type']=""
        if 'core_type' not in textInfo:
            textInfo['core_type']=""
        if 'delete_part' not in textInfo:
            textInfo['delete_part']=""

        return render_to_response("TagQuestion.html",
                                  {'textInfoJson': json.dumps(textInfo),
                                   'textInfo': textInfo,
                                   'questionIndex': questionIndex,
                                   'lastIndex': lastIndex,
                                   'thisIndex': globalIndex,
                                   'nextIndex': nextIndex,
                                   'papername': papername,
                                   'papertype': papertype,
                                   'allValidIndex': json.dumps(allValidIndex),
                                   'fullQuestion': json.dumps(fullQuestion),
                                   'username': username,
                                   'isFirstSubQuestion':isFirstSubQuestion
                                   })

    elif request.method == 'POST':
        tagInfo = {}
        tagInfo['choice_type'] = request.POST.get("choice_type_input_name")
        tagInfo['qiandao_type'] = request.POST.get("qiandao_type_input_name")
        tagInfo['core_type'] = request.POST.get("core_type_input_name")
        tagInfo['core_verb'] = request.POST.get("core_verb_input_name")
        tagInfo['delete_part'] = request.POST.get("delete_part_input_name")
        tagInfo['seg'] = request.POST.get("seg_name")
        username = request.POST.get("username_name")

        if username.strip() == "":
            return HttpResponse(u"提交出错，用户名为空")

        checkres = checkTagInfo(tagInfo)
        if checkres != "":
            return HttpResponse(u"提交出错，标注中存在错误：" + checkres + \
                                u"<br>可能是因为浏览器问题，前端检查没有正确执行" +
                                u"<br>可以使用浏览器退回功能回到刚刚的标注状态中")

        # print tagInfo
        if "save_btn" in request.POST:
            if saveTagInfoToDB(papername, papertype, globalIndex, tagInfo, username, request):
                checkGlobalTagState(papername, papertype)
                response = HttpResponseRedirect(
                    './TagQuestion?papername=' + papername + "&papertype=" + papertype + "&" + globalIndexFieldName + "=" + globalIndex)
                response.set_cookie("username", username.strip(),3600)
                return response
            else:
                return HttpResponse("保存出错")
        elif "saveAndNext_btn" in request.POST:
            if saveTagInfoToDB(papername, papertype, globalIndex, tagInfo, username, request):
                checkGlobalTagState(papername, papertype)
                nextIndex = checkAndFindTextInfoInDB(papername, papertype, globalIndex)[3]
                response = HttpResponseRedirect(
                    './TagQuestion?papername=' + papername + "&papertype=" + papertype + "&" + globalIndexFieldName + "=" + nextIndex)
                response.set_cookie("username", username.strip(), 3600)
                return response
            else:
                return HttpResponse("保存出错")


def checkTagInfo(tagInfo):
    seg = tagInfo['seg']

    if tagInfo['choice_type']=="":
        return u"请选择:选项类别"
    if tagInfo['qiandao_type']=="":
        return u"请选择:题干前导部分分类"
    if tagInfo['core_type']=="":
        return u"请选择:题干核心成分分类"

    if tagInfo["core_type"]==u"名词短语+动词短语" or tagInfo['core_type']==u"动词短语":
        if tagInfo["core_verb"]=="":
            return u"当题干核心成分分类为<动词短语>时,请填写动词"
        else:
            seglen=len(seg)
            if "-" in tagInfo['core_verb']:
                indexs=[int(x) for x in tagInfo['core_verb'].split('-')]
            else:
                indexs=[int(tagInfo['core_verb'])]

            for i in indexs:
                if i=="":
                    return u"题干核心动词下标格式错误(有空下标)"
                if i>=seglen:
                    return u"题干核心动词下标格式错误(超过最大下标)"
    return ""


def checkAndFindTextInfoInDB(papername, papertype, globalIndex):
    # 连接数据库
    configFile = open("static/config.txt", 'r')
    mongoIP = configFile.readline().split("\t")[1].strip()
    mongoPort = int(configFile.readline().split("\t")[1].strip())
    conn = pymongo.Connection(mongoIP, mongoPort)

    GeoPaperDB = conn['GeoPaper']
    dataCollection = None
    textFieldName = None
    globalIndexFieldName = None
    if papertype == "choice":
        dataCollection = GeoPaperDB['ChoiceData']
        textFieldName = "combinedTexts"
        globalIndexFieldName = "combinedChoiceIndex"
    elif papertype == "subjective":
        dataCollection = GeoPaperDB['SubjectiveData']
        textFieldName = "subQuestions"
        globalIndexFieldName = "subQuestionIndex"

    paperInfo = dataCollection.find_one({'testpaperName': papername})
    if paperInfo == None:
        return False

    res = []
    lastIndex = None
    nextIndex = None

    findFlag = False
    nextFlag = False

    allValidIndex = []

    fullQuestion = None
    isFirstSubQuestion = True

    for question in paperInfo['Questions']:
        for index,ctext in enumerate(question[textFieldName]):
            allValidIndex.append(ctext[globalIndexFieldName])
            if findFlag == True and nextFlag == False:  # 只有在nextFlag为False的时候才对nextIndex赋值
                nextIndex = ctext[globalIndexFieldName]
                nextFlag = True
            if findFlag == True:
                continue
            if globalIndex == ctext[globalIndexFieldName]:
                if index > 0:
                    isFirstSubQuestion = False
                    
                res.append(ctext)
                if papertype == "choice":
                    res.append(question['QuestionIndex'])
                elif papertype == "subjective":
                    res.append(question['number'])
                findFlag = True

                if papertype=="choice":
                    # generate full question text
                    fullQuestionInfo=[]
                    fullQuestionInfo.append(question['timian'])
                    for sc in question['smallChoices']:
                        fullQuestionInfo.append(sc['choiceIndex']+" "+sc['choiceContent'])
                    for c in question['choices']:
                        fullQuestionInfo.append(c['choiceIndex']+" "+c['choiceContent'])
                    fullQuestion = "\n".join(fullQuestionInfo)
                else:
                    fullQuestion = ""
            else:
                lastIndex = ctext[globalIndexFieldName]

    if findFlag:
        res.append(lastIndex)
        res.append(nextIndex)
        res.append(allValidIndex)
        res.append(fullQuestion)
        res.append(isFirstSubQuestion)
        return res
    else:
        # 如果遍历后没有找到则返回False
        return False


def saveTagInfoToDB(papername, papertype, globalIndex, tagInfo, username, request):
    # 连接数据库
    configFile = open("static/config.txt", 'r')
    mongoIP = configFile.readline().split("\t")[1].strip()
    mongoPort = int(configFile.readline().split("\t")[1].strip())
    conn = pymongo.Connection(mongoIP, mongoPort)
    GeoPaperDB = conn['GeoPaper']

    dataCollection = None
    textFieldName = None
    globalIndexFieldName = None
    if papertype == "choice":
        dataCollection = GeoPaperDB['ChoiceData']
        textFieldName = "combinedTexts"
        globalIndexFieldName = "combinedChoiceIndex"
    elif papertype == "subjective":
        dataCollection = GeoPaperDB['SubjectiveData']
        textFieldName = "subQuestions"
        globalIndexFieldName = "subQuestionIndex"

    try:
        paperInfo = dataCollection.find_one({'testpaperName': papername})
        if paperInfo == None:
            return False

        for question in paperInfo['Questions']:
            for ctext in question[textFieldName]:
                if globalIndex == ctext[globalIndexFieldName]:
                    ctext['question_tagger'] = username
                    ctext['choice_type'] = tagInfo['choice_type']
                    ctext['qiandao_type'] = tagInfo['qiandao_type']
                    ctext['core_type'] = tagInfo['core_type']
                    ctext['core_verb'] = tagInfo['core_verb']
                    ctext['delete_part'] = tagInfo['delete_part']

        i = 0
        saveok = False
        while True:
            if i > 0:
                try:
                    logfile = open("static/log/TemplateSaveLog.txt", "a")
                    logfile.write(
                        time.strftime('%Y-%m-%d %H:%M:%S') + "\t" + str(i) + "\t" + request.META['REMOTE_ADDR'])
                except Exception, e:
                    errorlog = open("static/log/errorlog.txt", "w")
                    errorlog.write(e + "\n")
                    errorlog.write(traceback.format_exc())
                    errorlog.write("\n\n")
                    errorlog.write(time.strftime('%Y-%m-%d %H:%M:%S'))

            dataCollection.save(paperInfo)

            real_paperInfo = dataCollection.find_one({'testpaperName': papername})
            for question in real_paperInfo['Questions']:
                for ctext in question[textFieldName]:
                    if globalIndex == ctext[globalIndexFieldName]:
                        if 'choice_type' not in ctext or ctext['choice_type'] != tagInfo['choice_type']:
                            saveok=False
                        else:
                            saveok = True
            if saveok:
                break
            else:
                i += 1

    except Exception, e:
        print e
        print traceback.format_exc()
        return False
    return True


def checkGlobalTagState(papername, papertype):
    # 连接数据库
    configFile = open("static/config.txt", 'r')
    mongoIP = configFile.readline().split("\t")[1].strip()
    mongoPort = int(configFile.readline().split("\t")[1].strip())
    conn = pymongo.Connection(mongoIP, mongoPort)
    GeoPaperDB = conn['GeoPaper']

    dataCollection = None
    textFieldName = None
    if papertype == "choice":
        dataCollection = GeoPaperDB['ChoiceData']
        textFieldName = "combinedTexts"
    elif papertype == "subjective":
        dataCollection = GeoPaperDB['SubjectiveData']
        textFieldName = "subQuestions"
    paperInfo = dataCollection.find_one({'testpaperName': papername})

    question_info_state = True

    taggers = {}
    for question in paperInfo['Questions']:
        for ctext in question[textFieldName]:
            if 'choice_type' not in ctext or ctext['choice_type'] == "":
                question_info_state = False

            if 'question_tagger' in ctext:
                if ctext['question_tagger'] not in taggers:
                    taggers[ctext['question_tagger']] = 1
                else:
                    taggers[ctext['question_tagger']] += 1

    paperInfo['relativeUsernames']['question_tagger'] = list(taggers)

    paperInfo['States']['questionInfo'] = question_info_state

    dataCollection.save(paperInfo)

    return paperInfo['States']