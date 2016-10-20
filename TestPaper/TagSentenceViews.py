#coding=utf-8
from django.shortcuts import render,render_to_response
from django.http import HttpResponse,HttpResponseRedirect

import pymongo
import traceback
import json

# Create your views here.
def tagSentence(request):
    #连接数据库
    configFile=open("static/config.txt",'r')
    mongoIP=configFile.readline().split("\t")[1].strip()
    mongoPort=int(configFile.readline().split("\t")[1].strip())
    conn=pymongo.Connection(mongoIP,mongoPort)

    GeopaperDB=conn['GeoPaper']

    papername=request.GET.get("papername")
    
    papertype=None    
    if 'papertype' not in request.GET:
        papertype="choice"
    else:
        papertype=request.GET['papertype']
       
    dataCollection=None
    globalIndexFieldName=None
    globalIndex=None
    textFieldName=None
    if papertype=="choice":
        dataCollection=GeopaperDB['ChoiceData']
        globalIndexFieldName="combinedChoiceIndex"
        globalIndex=request.GET['combinedChoiceIndex']
        textFieldName="combinedTexts"
    elif papertype=="subjective":
        dataCollection=GeopaperDB['SubjectiveData']
        globalIndexFieldName="subQuestionIndex"
        globalIndex=request.GET['subQuestionIndex']
        textFieldName="subQuestions"

    else:
        return HttpResponse("<h1>非法访问，没有提供试卷类型！</h1><br><a href='./BrowseByPaper.html'>返回试卷列表页面</a>")

    if request.method=='GET':
        paperInfo=dataCollection.find_one({'testpaperName':papername})
        if not paperInfo:
            return HttpResponse("没有这份试卷")

        #必须是手动分词、时间、地点词性标注完了才来标注时间地点
        if paperInfo['States']['seg']==False:
            return HttpResponse("请先完成对改试卷的分词标注")
        elif paperInfo['States']['time']==False:
            return HttpResponse("请先完成对改试卷的时间、地点标注")
        elif paperInfo['States']['pos']==False:
            return HttpResponse("请先完成对改试卷的词性标注")

        result=checkAndFindTextInfoInDB(papername,papertype,globalIndex)
        
        if result==False:
            return HttpResponse("<h1>非法访问，该试卷没有这个选项文本！</h1><br><a href='./BrowseByPaper.html'>返回试卷列表页面</a>")
        else:
            textInfo=result[0]
            questionIndex=result[1]
            lastIndex=result[2]
            nextIndex=result[3]
            allValidIndex=result[4]

            if papertype=="choice":
                #将text拆成题面和选项，供前端显示
                textInfo['timian']=textInfo['text'].split("\t")[0]
                textInfo['xuanxiang']=textInfo['text'].split("\t")[1]
                textInfo['combinedTextWithoutTab']=textInfo['text'].replace("\t","")
            
            return render_to_response("TagSentence.html",
                                {'textInfoJson':json.dumps(textInfo),
                                'textInfo':textInfo,
                                'questionIndex':questionIndex,
                                'lastIndex':lastIndex,
                                'thisIndex':globalIndex,
                                'nextIndex':nextIndex,
                                'papername':papername,
                                'papertype':papertype,
                                'allValidIndex':json.dumps(allValidIndex)})
                                
    elif request.method=="POST":
        globalIndex=None
        globalIndexFieldName=None
        if papertype=="choice":
            globalIndexFieldName="combinedChoiceIndex"
            globalIndex=request.GET['combinedChoiceIndex']
        elif papertype=="subjective":
            globalIndexFieldName="subQuestionIndex"
            globalIndex=request.GET['subQuestionIndex']

        tagInfo={}
        tagInfo['seg']=request.POST.get("seg_input_name")
        tagInfo['seg_fg']=request.POST.get("seg_fg_input_name")
        tagInfo['pos']=request.POST.get("pos_input_name")
        tagInfo['time']=request.POST.get("time_input_name")
        tagInfo['loc']=request.POST.get("loc_input_name")
        tagInfo['term']=request.POST.get("term_input_name")
        tagInfo['quant']=request.POST.get("quant_input_name")

        if papertype=="choice":
            tagInfo['timian']=request.POST.get("timian_name")
            tagInfo['xuanxiang']=request.POST.get('xuanxiang_name')
        else:
            tagInfo['timian']=request.POST.get("timian_name")

        username=request.POST.get("username_name")
        if "save_btn" in request.POST:
            if saveTagInfoToDB(papername,papertype,globalIndex,tagInfo,username):
                checkGlobalTagState(papername,papertype)
                return HttpResponseRedirect('./TagSentence?papername='+papername+"&papertype="+papertype+"&"+globalIndexFieldName+"="+globalIndex)
            else:
                return HttpResponse("保存出错")
        elif "saveAndNext_btn" in request.POST:
            if saveTagInfoToDB(papername,papertype,globalIndex,tagInfo,username):
                checkGlobalTagState(papername,papertype)
                nextIndex=checkAndFindTextInfoInDB(papername,papertype,globalIndex)[3]
                return HttpResponseRedirect('./TagSentence?papername='+papername+"&papertype="+papertype+"&"+globalIndexFieldName+"="+nextIndex)
            else:
                return HttpResponse("保存出错")
        

def checkAndFindTextInfoInDB(papername,papertype,globalIndex):
    #连接数据库
    configFile=open("static/config.txt",'r')
    mongoIP=configFile.readline().split("\t")[1].strip()
    mongoPort=int(configFile.readline().split("\t")[1].strip())
    conn=pymongo.Connection(mongoIP,mongoPort)
    
    GeoPaperDB=conn['GeoPaper']

    dataCollection=None
    globalIndexFieldName=None
    textFieldName=None
    if papertype=="choice":
        dataCollection=GeoPaperDB['ChoiceData']
        globalIndexFieldName="combinedChoiceIndex"
        textFieldName="combinedTexts"
    elif papertype=="subjective":
        dataCollection=GeoPaperDB['SubjectiveData']
        globalIndexFieldName="subQuestionIndex"
        textFieldName="subQuestions"

    paperInfo=dataCollection.find_one({'testpaperName':papername})
    if paperInfo==None:
        return False
    
    res=[]
    lastIndex=None
    nextIndex=None
    
    findFlag=False
    nextFlag=False
    
    allValidIndex=[]

    relativeFieldNames=['goldlocs','goldtimes','goldterms','goldquants']

    for question in paperInfo['Questions']:
        for ctext in question[textFieldName]:            
            allValidIndex.append(ctext[globalIndexFieldName])
            if findFlag==True and nextFlag==False:   #只有在nextFlag为False的时候才对nextIndex赋值
                nextIndex=ctext[globalIndexFieldName]
                nextFlag=True
            if findFlag==True:
                continue
            if globalIndex==ctext[globalIndexFieldName]:
                #一些预处理
                for f in relativeFieldNames:
                    if f in ctext:
                        ctext[f]=" ".join([str(l) for l in ctext[f]])
                    else:
                        ctext[f]=""

                res.append(ctext)
                if papertype=="choice":
                    res.append(question['QuestionIndex'])
                elif papertype=="subjective":
                    res.append(question['number'])
                findFlag=True
            else:
                lastIndex=ctext[globalIndexFieldName]

            
    if findFlag:
        res.append(lastIndex)
        res.append(nextIndex)
        res.append(allValidIndex)
        return res
    else:
        #如果遍历后没有找到则返回False
        return False
        
        
def saveTagInfoToDB(papername,papertype,globalIndex,tagInfo,username):
    #连接数据库
    configFile=open("static/config.txt",'r')
    mongoIP=configFile.readline().split("\t")[1].strip()
    mongoPort=int(configFile.readline().split("\t")[1].strip())
    conn=pymongo.Connection(mongoIP,mongoPort)
    GeoPaperDB=conn['GeoPaper']
    
    dataCollection=None
    globalIndexFieldName=None
    textFieldName=None
    if papertype=="choice":
        dataCollection=GeoPaperDB['ChoiceData']
        globalIndexFieldName="combinedChoiceIndex"
        textFieldName="combinedTexts"
    elif papertype=="subjective":
        dataCollection=GeoPaperDB['SubjectiveData']
        globalIndexFieldName="subQuestionIndex"
        textFieldName="subQuestions"
    
    try:
        paperInfo=dataCollection.find_one({'testpaperName':papername})
        if paperInfo==None:
            return False
        for question in paperInfo['Questions']:
            for ctext in question[textFieldName]:
                if globalIndex==ctext[globalIndexFieldName]:
                    #如果改变了分词，人工模板和成分分析、自动模版的标注都会失效
                    if ctext['segres']!=[p.split("_")[0] for p in tagInfo['seg'].split()]:
                        ctext['conpparse_valid']=False
                        ctext['auto_conpparse_valid']=False
                        ctext['template_valid']=False
                        ctext['auto_template_valid']=False
                        paperInfo['States']['bpres']=False
                        paperInfo['States']['fullTemplate']=False
                        paperInfo['States']['fullTemplateTypes']=False
                        paperInfo['States']['fullTemplateCueword']=False
                        paperInfo['States']['simplifiedTemplate']=False
                        paperInfo['States']['simplifiedTemplateTypes']=False
                        paperInfo['States']['simplifiedTemplateCueword']=False
                        paperInfo['States']['autoTemplate']=False

                    #如果改变了词性标注，成分分析、自动模版的标注会失效
                    if ctext['posres']!=[p.split("_")[1] for p in tagInfo['pos'].split()]:
                        ctext['conpparse_valid']=False
                        ctext['auto_conpparse_valid']=False
                        ctext['auto_template_valid']=False
                        paperInfo['States']['auto_bpres']=False
                        paperInfo['States']['bpres']=False
                        paperInfo['States']['autoTemplate']=False

                    ctext['sentence_tagger']=username
                    ctext['segres']=[p.split("_")[0] for p in tagInfo['seg'].split()]
                    ctext['segres_fg']=[p.split("_")[0] for p in tagInfo['seg_fg'].split()]
                    ctext['posres']=[p.split("_")[1] for p in tagInfo['pos'].split()]
                    ctext['goldtimes']=[int(x) for x in tagInfo['time'].split()]
                    ctext['goldlocs']=[int(x) for x in tagInfo['loc'].split()]
                    ctext['goldterms']=[int(x) for x in tagInfo['term'].split()]
                    ctext['goldquants']=[int(x) for x in tagInfo['quant'].split()]

                    #试题文本，如果有修改，添加一个字段，记录之前的试题文本的内容
                    if papertype=="choice":
                        if tagInfo['timian']+"\t"+tagInfo['xuanxiang']!=ctext['text']:
                            if 'deprecated_text' in ctext:                            
                                ctext["deprecated_text"].append(ctext['text'])
                            else:
                                ctext['deprecated_text']=[ctext['text']]
                            ctext['text']=tagInfo['timian']+"\t"+tagInfo['xuanxiang']
                    else:
                        if tagInfo['timian']!=ctext['text']:
                            if 'deprecated_text' in ctext:
                                ctext['deprecated_text'].append(ctext['text'])
                            else:
                                ctext['deprecated_text']=[ctext['text']]
                            ctext['text']=tagInfo['timian']

                    
        dataCollection.save(paperInfo)

    except Exception, e:
        print e
        print traceback.format_exc()
        return False
    return True


def checkGlobalTagState(papername,papertype):
    #连接数据库
    configFile=open("static/config.txt",'r')
    mongoIP=configFile.readline().split("\t")[1].strip()
    mongoPort=int(configFile.readline().split("\t")[1].strip())
    conn=pymongo.Connection(mongoIP,mongoPort)
    GeoPaperDB=conn['GeoPaper']

    dataCollection=None
    globalIndexFieldName=None
    textFieldName=None
    if papertype=="choice":
        dataCollection=GeoPaperDB['ChoiceData']
        globalIndexFieldName="combinedChoiceIndex"
        textFieldName="combinedTexts"
    elif papertype=="subjective":
        dataCollection=GeoPaperDB['SubjectiveData']
        globalIndexFieldName="subQuestionIndex"
        textFieldName="subQuestions"

    
    paperInfo=dataCollection.find_one({'testpaperName':papername})
    
    seg_state=True
    pos_state=True
    time_state=True
    loc_state=True
    conp_state=True

    FT_state=True
    FTT_state=True
    FTCW_state=True
    STT_state=True
    ST_state=True
    STCW_state=True
   
    for question in paperInfo['Questions']:
        for ctext in question[textFieldName]:
            '''
            #单句标注出现前保证完成下列四项的标注
            if "seg_tagged" not in ctext:
                seg_state=False
            if "pos_tagged" not in ctext:
                pos_state=False
            if "time_tagged" not in ctext:
                time_state=False
            if "loc_tagged" not in ctext:
                loc_state=False
            '''
            if 'conpparse_valid' in ctext and ctext['conpparse_valid']==False or 'bpres' not in ctext or ctext['bpres']=="":
                conp_state=False
            if 'template_valid' in ctext and ctext['template_valid']==False or 'fullTemplate' not in ctext or ctext['fullTemplate']=="":
                FT_state=False
                FTT_state=False
                FTCW_state=False
            if 'template_valid' in ctext and ctext['template_valid']==False or 'simplifiedTemplate' not in ctext or ctext['simplifiedTemplate']=="":
                ST_state=False
                STT_state=False
                STCW_state=False                             

    '''
    paperInfo['States']['seg']=seg_state
    paperInfo['States']['loc']=pos_state
    paperInfo['States']['loc']=time_state
    paperInfo['States']['loc']=loc_state
    '''
    paperInfo['States']['bpres']=conp_state
    paperInfo['States']['fullTemplate']=FT_state
    paperInfo['States']['fullTemplateTypes']=FTT_state
    paperInfo['States']['fullTemplateCueword']=FTCW_state
    paperInfo['States']['simplifiedTemplate']=ST_state
    paperInfo['States']['simplifiedTemplateTypes']=STT_state
    paperInfo['States']['simplifiedTemplateCueword']=STCW_state
    dataCollection.save(paperInfo)
    return paperInfo['States']






        