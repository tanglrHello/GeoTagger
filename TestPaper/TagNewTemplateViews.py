# coding=utf-8
from django.shortcuts import render, render_to_response
from django.http import HttpResponse, HttpResponseRedirect

from . import getConfig
from . import geoProcessor

import pymongo
import time, json
import traceback


# Create your views here.
def tagNewTemplate(request):
    # 连接数据库
    configFile = open("static/config.txt", 'r')
    mongoIP = configFile.readline().split("\t")[1].strip()
    mongoPort = int(configFile.readline().split("\t")[1].strip())
    conn = pymongo.Connection(mongoIP, mongoPort)

    GeopaperDB = conn['GeoPaper']

    papername = request.GET['papername']
    papertype = request.GET['papertype']

    nextIndex = None  # 下一句的index，用于“保存并下一句”的功能中

    template_Info = None
    dataCollection = None
    globalIndex = None
    globalIndexFieldName = None
    if papertype == "choice":
        template_Info = getConfig.getNewTemplateConfig("choice")
        dataCollection = GeopaperDB['ChoiceData']
        globalIndexFieldName = "combinedChoiceIndex"
        globalIndex = request.GET['combinedChoiceIndex']
        textFieldName = "combinedTexts"
    elif papertype == "subjective":
        return HttpResponse("主观题没有新模板标注")
        template_Info = getConfig.getTemplateConfig("subjective")
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
        lastTextNewTemplateInfos = result[5]
        fullQuestion = result[6]
        if papertype == "choice":
            # 将text拆成题面和选项，供前端显示
            textInfo['timian'] = textInfo['text'].split("\t")[0]
            textInfo['xuanxiang'] = textInfo['text'].split("\t")[1]
            textInfo['combinedTextWithoutTab'] = textInfo['text'].replace("\t", "")
            textInfo['posinfo'] = " ".join([seg + "_" + pos for seg, pos in zip(textInfo['segres'], textInfo['posres'])])

    username = request.COOKIES.get("username", "")

    tagtype = ""
    if request.method == 'GET':
        if textInfo['segres'] == []:
            return HttpResponse("请先完成对该句的分词标注")

        # 分词结果
        textInfo['segres'] = " ".join(
            [w + "_" + str(i) for w, i in zip(textInfo['segres'], range(len(textInfo['segres'])))])

        if textInfo['secondTemplate'] != "":
            tagtype = u"人工标注"
        elif textInfo['auto_secondTemplate'] != "":
            tagtype = u"自动标注"
            textInfo['secondTemplate'] = textInfo['auto_secondTemplate']
            textInfo['secondTemplateTypes'] = textInfo['auto_secondTemplateTypes']
            textInfo['secondTemplateCueword'] = textInfo['auto_secondTemplateCueword']
            textInfo['topTemplate'] = textInfo['auto_topTemplate']
            textInfo['topTemplateTypes'] = textInfo['auto_topTemplateTypes']
            textInfo['topTemplateCueword'] = textInfo['auto_topTemplateCueword']

        return render_to_response("TagNewTemplate.html",
                                  {'textInfoJson': json.dumps(textInfo),
                                   'textInfo': textInfo,
                                   'lastTextNewTemplateInfos': json.dumps(lastTextNewTemplateInfos),
                                   'questionIndex': questionIndex,
                                   'lastIndex': lastIndex,
                                   'thisIndex': globalIndex,
                                   'nextIndex': nextIndex,
                                   'papername': papername,
                                   'papertype': papertype,
                                   'allValidIndex': json.dumps(allValidIndex),
                                   'template_config': template_Info,
                                   'template_config_json': json.dumps(template_Info),
                                   'tagtype': tagtype,
                                   'fullQuestion': json.dumps(fullQuestion),
                                   'username': username
                                   })

    elif request.method == "POST" and "generateTemplate" in request.POST:  # 自动生成整张试卷所有试题文本的模板标注
        input_text = []
        input_seg = []

        for question in paperInfo['Questions']:
            for ctext in question[textFieldName]:
                input_text.append(ctext['text'])
                input_seg.append(ctext['segres'])

        # 自动生成模板信息（如果没有自动成分句法，还会生成自动句法分析结果）
        geo_processor = geoProcessor.geo_Processor()
        autoTemplate = geo_processor.process_template(input_text, input_seg, papertype)

        # 将自动分析结果写回数据库
        paperInfo = dataCollection.find_one({'testpaperName': papername})

        index = 0
        for question in paperInfo['Questions']:
            for ctext in question[textFieldName]:
                ctext['auto_topTemplate'] = autoTemplate['auto_topTemplate'][index]
                ctext['auto_topTemplateTypes'] = autoTemplate['auto_topTemplateTypes'][index]
                ctext['auto_topTemplateCueword'] = autoTemplate['auto_topTemplateCueword'][index]
                ctext['auto_secondTemplate'] = autoTemplate['auto_secondTemplate'][index]
                ctext['auto_secondTemplateTypes'] = autoTemplate['auto_secondTemplateTypes'][index]
                ctext['auto_secondTemplateCueword'] = autoTemplate['auto_secondTemplateCueword'][index]
                index += 1
                if 'auto_template_valid' in ctext:
                    del ctext['auto_template_valid']
                if ctext[globalIndexFieldName] == globalIndex:
                    textInfo['secondTemplate'] = ctext['auto_secondTemplate']
                    textInfo['secondTemplateTypes'] = " ".join(ctext['auto_secondTemplateTypes'])
                    textInfo['secondTemplateCueword'] = " ".join(ctext['auto_secondTemplateCueword'])
                    textInfo['topTemplate'] = ctext['auto_topTemplate']
                    textInfo['topTemplateTypes'] = " ".join(ctext['auto_topTemplateTypes'])
                    textInfo['topTemplateCueword'] = " ".join(ctext['auto_topTemplateCueword'])

        paperInfo['States']['autoNewTemplate'] = True

        dataCollection.save(paperInfo)

        # 分词结果
        textInfo['segres'] = " ".join(
            [w + "_" + str(i) for w, i in zip(textInfo['segres'], range(len(textInfo['segres'])))])

        tagtype = u"自动标注"

        return render_to_response("TagNewTemplate.html",
                                  {'textInfoJson': json.dumps(textInfo),
                                   'textInfo': textInfo,
                                   'lastTextNewTemplateInfos': json.dumps(lastTextNewTemplateInfos),
                                   'questionIndex': questionIndex,
                                   'lastIndex': lastIndex,
                                   'thisIndex': globalIndex,
                                   'nextIndex': nextIndex,
                                   'papername': papername,
                                   'papertype': papertype,
                                   'allValidIndex': json.dumps(allValidIndex),
                                   'template_config': template_Info,
                                   'template_config_json': json.dumps(template_Info),
                                   'tagtype': tagtype,
                                   'fullQuestion': json.dumps(fullQuestion),
                                   'username': username
                                   })

    elif request.method == 'POST':
        tagInfo = {}
        tagInfo['topTemplate'] = request.POST.get("ST_input_name")
        tagInfo['topTemplateCueword'] = request.POST.get("STC_input_name")
        tagInfo['topTemplateTypes'] = " ".join(list(set(request.POST.get("STT_input_name").split())))

        tagInfo['choiceQuestionSentence'] = request.POST.get("CQ_input_name")
        tagInfo['secondTemplate'] = request.POST.get("FT_input_name")
        tagInfo['secondTemplateCueword'] = request.POST.get("FTC_input_name")
        tagInfo['secondTemplateTypes'] = " ".join(list(set(request.POST.get("FTT_input_name").split())))

        tagInfo['seg'] = request.POST.get("seg_name")
        username = request.POST.get("username_name")

        tagInfo['hastop'] = request.POST.get("hastop")

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
                    './TagNewTemplate?papername=' + papername + "&papertype=" + papertype + "&" + globalIndexFieldName + "=" + globalIndex)
                response.set_cookie('username', username.strip(), 3600)
                return response
            else:
                return HttpResponse("保存出错")
        elif "saveAndNext_btn" in request.POST:
            if saveTagInfoToDB(papername, papertype, globalIndex, tagInfo, username, request):
                checkGlobalTagState(papername, papertype)
                nextIndex = checkAndFindTextInfoInDB(papername, papertype, globalIndex)[3]
                response = HttpResponseRedirect(
                    './TagNewTemplate?papername=' + papername + "&papertype=" + papertype + "&" + globalIndexFieldName + "=" + nextIndex)
                response.set_cookie('username', username.strip(), 3600)
                return response
            else:
                return HttpResponse("保存出错")


def checkTagInfo(tagInfo):
    types = ['top', 'second']
    chn_tname = {"top": u"高阶模板", "second": u"二阶模板"}

    seg = tagInfo['seg']

    if tagInfo["topTemplate"].strip() == "" and tagInfo['secondTemplate'].strip()=="":
        return u"一级模板和二级模板至少要填写一个"

    if tagInfo['hastop']=="true" and tagInfo['topTemplate'].strip()=="":
        return u"一级模板需要填写"

    for t in types:
        template = tagInfo[t + "Template"]
        ttype = tagInfo[t + "TemplateTypes"]
        cueword = tagInfo[t + "TemplateCueword"]

        cq = tagInfo["choiceQuestionSentence"]

        # 检查模板下标是否重复
        for i in range(10):
            if template.count("_" + str(i)) > 1:
                return chn_tname[t] + u"标注中存在重复的模板下标：" + str(i)

        # 检查模板标注中是否有英文逗号
        if template.find(",") != -1:
            return chn_tname[t] + u"标注中存在英文逗号"

        # 检查每个线索词项格式是否正确
        cwList = cueword.split()
        templateIndex = []
        for cw in cwList:
            if cw.count("_") != 1:
                return chn_tname[t] + u"线索词标注中，'" + cw + u"'这一项应该有且仅有一个下划线"
            cw = cw.split("_")
            templateIndex.append(cw[0])
            if "_" + cw[0] not in template:
                return chn_tname[t] + u"线索词标注中，'" + cw + u"'这一项的模板下标在模板标注中不存在"

            if len(list(set(cw[1].split("-")))) != len(cw[1].split('-')):
                return chn_tname[t] + u"线索词标注中，'" + cw + u"'这一项的线索词下标存在重复"

            for wi in cw[1].split("-"):
                if not 0 <= int(wi) < len(seg):
                    return chn_tname[t] + u"线索词标注中，'" + cw + u"'这一项对应的线索词下标不是有效的词语下标"

        # 检查选项问句格式是否正确
        if len(cq.split("-"))!=2:
            return u"选项问句中应该有且仅有一个-"
        cq_index = cq.split("-")
        for index in cq_index:
            try:
                i = int(index)
                if i >= len(seg):
                    return u"选项问句的下标范围超过了最大下标"
            except:
                return u"选项问句的下标范围不是有效数字"
        if int(cq_index[1]) <= int(cq_index[0]):
            return u"选项问句的起始下标不应该大于终止下标"

        # 是否有重复标注线索词的模板下标
        if len(set(templateIndex)) != len(templateIndex):
            return chn_tname[t] + u"线索词标注中，存在重复的模板下标"
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

    lastOriTextNewTemplateInfos = {}

    allValidIndex = []

    relativeFieldNames = ['secondTemplate',
                          'topTemplate',
                          "choiceQuestionSentence",
                          'secondTemplateCueword',
                          'secondTemplateTypes',
                          'topTemplateCueword',
                          'topTemplateTypes']
    autoFieldNames = ["auto_" + n for n in relativeFieldNames]

    fullQuestion = None

    for question in paperInfo['Questions']:
        for ctext in question[textFieldName]:
            allValidIndex.append(ctext[globalIndexFieldName])
            if findFlag == True and nextFlag == False:  # 只有在nextFlag为False的时候才对nextIndex赋值
                nextIndex = ctext[globalIndexFieldName]
                nextFlag = True
            if findFlag == True:
                continue
            if globalIndex == ctext[globalIndexFieldName]:
                # 一些预处理
                for f in relativeFieldNames[3:] + autoFieldNames[3:]:
                    if f in ctext:
                        ctext[f] = " ".join(ctext[f])
                    else:
                        ctext[f] = ""
                for f in relativeFieldNames[:3] + autoFieldNames[:3]:
                    if f not in ctext:
                        ctext[f] = ""

                res.append(ctext)
                if papertype == "choice":
                    res.append(question['QuestionIndex'])
                elif papertype == "subjective":
                    res.append(question['number'])
                findFlag = True

                if papertype == "choice":
                    # generate full question text
                    fullQuestionInfo = []
                    fullQuestionInfo.append(question['timian'])
                    for sc in question['smallChoices']:
                        fullQuestionInfo.append(sc['choiceIndex'] + " " + sc['choiceContent'])
                    for c in question['choices']:
                        fullQuestionInfo.append(c['choiceIndex'] + " " + c['choiceContent'])
                    fullQuestion = "\n".join(fullQuestionInfo)
                else:
                    fullQuestion = ""
            else:
                lastIndex = ctext[globalIndexFieldName]
                if papertype == "choice" and (ctext['number'] in "ABCD" or ctext['number'] in u"①②③④⑤⑥⑦⑧⑨"):  # 只有选择题需要从上一题同步的功能
                    for f in relativeFieldNames[:3]:
                        lastOriTextNewTemplateInfos[f] = ctext.get(f,"")

                    for f in relativeFieldNames[3:]:
                        lastOriTextNewTemplateInfos[f] = " ".join(ctext.get(f,[]))

    if findFlag:
        res.append(lastIndex)
        res.append(nextIndex)
        res.append(allValidIndex)
        res.append(lastOriTextNewTemplateInfos)
        res.append(fullQuestion)
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
                    ctext['new_template_tagger'] = username
                    ctext['topTemplate'] = tagInfo['topTemplate']
                    ctext['topTemplateTypes'] = tagInfo['topTemplateTypes'].split()
                    ctext['topTemplateCueword'] = tagInfo['topTemplateCueword'].split()
                    ctext['choiceQuestionSentence'] = tagInfo['choiceQuestionSentence']
                    ctext['secondTemplate'] = tagInfo['secondTemplate']
                    ctext['secondTemplateTypes'] = tagInfo['secondTemplateTypes'].split()
                    ctext['secondTemplateCueword'] = tagInfo['secondTemplateCueword'].split()

                    if 'template_valid' in ctext:
                        del ctext['template_valid']

        i = 0
        saveok = False
        while True:
            if i > 0:
                try:
                    logfile = open("/static/log/TemplateSaveLog.txt", "a")
                    logfile.write(
                        time.strftime('%Y-%m-%d %H:%M:%S') + "\t" + str(i) + "\t" + request.META['REMOTE_ADDR'])
                except Exception, e:
                    errorlog = open("/static/log/errorlog.txt", "w")
                    errorlog.write(e + "\n")
                    errorlog.write(traceback.format_exc())
                    errorlog.write("\n\n")
                    errorlog.write(time.strftime('%Y-%m-%d %H:%M:%S'))

            dataCollection.save(paperInfo)

            real_paperInfo = dataCollection.find_one({'testpaperName': papername})
            for question in real_paperInfo['Questions']:
                for ctext in question[textFieldName]:
                    if globalIndex == ctext[globalIndexFieldName]:
                        if 'topTemplate' not in ctext or (ctext['topTemplate'] == "" and ctext['secondTemplate'] == ""):
                            dataCollection.save(paperInfo)
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

    second_template_state = True
    top_template_state = True

    taggers = {}
    for question in paperInfo['Questions']:
        for ctext in question[textFieldName]:
            if 'secondTemplate' not in ctext or ctext['secondTemplate'] == "" or 'template_valid' in ctext and ctext[
                'template_valid'] == False:
                second_template_state = False

            if 'topTemplate' not in ctext or ctext['topTemplate'] == "" or 'template_valid' in ctext and \
                            ctext['template_valid'] == False:
                top_template_state = False

            if 'new_template_tagger' in ctext:
                if ctext['new_template_tagger'] not in taggers:
                    taggers[ctext['new_template_tagger']] = 1
                else:
                    taggers[ctext['new_template_tagger']] += 1

    paperInfo['relativeUsernames']['new_template_tagger'] = list(taggers)

    paperInfo['States']['topTemplate'] = top_template_state
    paperInfo['States']['secondTemplate'] = second_template_state

    dataCollection.save(paperInfo)

    return paperInfo['States']