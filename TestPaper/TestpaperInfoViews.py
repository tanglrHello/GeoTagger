#coding=utf-8
from django.shortcuts import render,render_to_response
from django.http import HttpResponse

import pymongo

from . import getConfig

# Create your views here.
def testpaperInfo(request):

    papername=request.GET.get("papername")
    papertype=request.GET.get("papertype")

    #获取标注字段配置信息
    tagFields_Info=getConfig.getTagFieldConfig(papertype)
    sortedTagFieldsForTable=tagFields_Info[:]
    sortedTagFieldsForTable.sort(key=lambda x:x[-1])

    if request.method=='GET':
        #检查GET参数中的试卷类型
        globalIndexFieldName=None
        papertype_chn=None
        textFieldName=None
        questionIndexFieldName=None
        if papertype=="choice":
            globalIndexFieldName="combinedChoiceIndex"
            papertype_chn=u"选择题"
            textFieldName="combinedTexts"
            questionIndexFieldName="QuestionIndex"
        elif papertype=="subjective":
            globalIndexFieldName="subQuestionIndex"
            papertype_chn=u"主观题"
            textFieldName="subQuestions"
            questionIndexFieldName="number"
        else:
            return HttpResponse("<h1>非法访问，没有提供试卷类型！</h1><br><a href='./BrowseByPaper.html'>返回试卷列表页面</a>")

        #在数据库中查找试卷信息
        paperdata=checkAndReadPaperFromDB(papername,papertype)

        queryRes=[]
        
        #没有在数据库中找到相应的试卷数据
        if paperdata==False:
            return HttpResponse("<h1>非法访问，没有相应试卷信息！</h1><br><a href='./BrowseByPaper.html'>返回试卷列表页面</a>")
        else:                        
            #数据预处理，将列表类型的数据修改为拼接好的字符串供前端直接使用
            for question in paperdata['Questions']:
                for ctext in question[textFieldName]:
                    segres=ctext['segres']

                    may_empty_fields=['segres_fg','auto_seg',"auto_seg_fg","auto_time","auto_loc","auto_pos","auto_bpres"]
                    for mef in may_empty_fields:
                        if mef not in ctext:
                            ctext[mef]=""

                    for tagField in sortedTagFieldsForTable:               
                        if tagField[2]=="string":
                            if tagField[0] in ctext:
                                ctext[tagField[0]]=ctext[tagField[0]]
                            else:
                                ctext[tagField[0]]=""
                        elif tagField[2]=="list_num":
                            if tagField[0] in ctext:
                                info_str1=""
                                info_str2=""
                                for index in ctext[tagField[0]]:
                                    try:
                                        info_str1 += segres[int(index)]+" "
                                        info_str2 += str(index)+" "
                                    except:
                                        info_str2 += str(index)+" "

                                ctext[tagField[0]]=info_str1+"\n("+info_str2+")"
                            else:
                                ctext[tagField[0]]=""
                        elif tagField[2]=="list_string_index":
                            if tagField[0] in ctext:
                                ctext[tagField[0]]=" ".join([w+"/"+str(index) for w,index in zip(ctext[tagField[0]],range(len(ctext[tagField[0]])))])
                            else:
                                ctext[tagField[0]]=""
                        elif tagField[2]=="list_string":
                            if tagField[0] in ctext:
                                ctext[tagField[0]]=" ".join(ctext[tagField[0]])
                            else:
                                ctext[tagField[0]]=""

                    if papertype=="choice":
                        ctext['number']=str(question[questionIndexFieldName])+"-"+ctext['number']
                    else:
                        ctext['number']=str(question[questionIndexFieldName])+"-"+str(ctext['number'])
                    
                    validList=['template_valid','conpparse_valid',"auto_conpparse_valid",'auto_template_valid']
                    for v in validList:
                        if v in ctext and ctext[v]==False:
                            ctext[v]="false"
                        else:
                            ctext[v]="true"

                    ctext['text'] = "@".join(ctext['text'].split())
                    
                    queryRes.append(ctext)

            #将queryRes转换成便于前端显示的形式
            #每个元素是一个列表，对应一个句子的各个字段
            #每个标注字段表示成三元组，其中第一个元素表示该字段当前是否有效，第二个为内容，第三个为字段名
            tranformedRes = []
            textIndexes = []
            
            for res in queryRes:
                newres = []

                textIndexes.append(res[globalIndexFieldName])
                for field in sortedTagFieldsForTable:
                    if field[3]==None:
                        newres.append((True,res[field[0]],field[0]))
                    else:
                        if res[field[3]]=="true":
                            newres.append((True,res[field[0]],field[0]))
                        else:
                            newres.append((False,res[field[0]],field[0]))
                tranformedRes.append(newres)

            return render_to_response("TestpaperInfo.html",
                                    {'papername':papername,
                                    'papertype_chn':papertype_chn,
                                    'papertype':papertype,
                                    'sortedTagFieldsForTable':sortedTagFieldsForTable,
                                    'tagFields_config':tagFields_Info,
                                    'queryRes':zip(textIndexes,tranformedRes)})
       


#在数据库中查找试卷信息
def checkAndReadPaperFromDB(papername,papertype):
    #连接数据库
    configFile=open("static/config.txt",'r')
    mongoIP=configFile.readline().split("\t")[1].strip()
    mongoPort=int(configFile.readline().split("\t")[1].strip())
    conn=pymongo.Connection(mongoIP,mongoPort)
    geoData=conn['GeoPaper']
    if papertype=="choice":
        choiceDB=geoData['ChoiceData']
        result=choiceDB.find_one({'testpaperName':papername})
        if result==None:
            return False
        else:
            return result
        
    elif papertype=="subjective":
        subjectiveDB=geoData['SubjectiveData']
        result=subjectiveDB.find_one({'testpaperName':papername})
        if result==None:
            return False
        else:
            return result
    else:
        return False
