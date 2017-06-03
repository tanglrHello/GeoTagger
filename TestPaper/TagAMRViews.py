#coding=utf-8
from django.shortcuts import render_to_response
from django.http import HttpResponse,HttpResponseRedirect

import pymongo
import time
import json
import traceback
import os
import mongoConnection

# Create your views here.
def tagAMR(request):
    # 连接数据库
    conn = mongoConnection.connect_mongodb()

    GeopaperDB=conn['GeoPaper']

    papername=request.GET['papername']
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


    paperInfo=dataCollection.find_one({'testpaperName':papername})  
    if not paperInfo:
        return HttpResponse("没有这份试卷")

    #必须是时间地点手动标注完了才来标注时间地点(这里使用粗粒度的版本)
    if paperInfo['States']['seg']!=True: 
        return HttpResponse("请先完成对该试卷的分词标注")
    
    result=checkAndFindTextInfoInDB(papername,papertype,globalIndex)


    if result==False:
        return HttpResponse("<h1>非法访问，该试卷没有这个选项文本")

    textInfo=result[0]
    questionIndex=result[1]
    lastIndex=result[2]
    nextIndex=result[3]
    allValidIndex=result[4]

    tagtype = "null"
    
    if papertype == "choice":
        #将text拆成题面和选项，供前端显示
        textInfo['timian'] = textInfo['text'].split("\t")[0]
        textInfo['xuanxiang'] = textInfo['text'].split("\t")[1]

        seg = textInfo['segres']
    else:
        return HttpResponse("不支持主观题标注")

    username = request.COOKIES.get("username", "")
    # pos tag type
    postag = None
    if 'posres' in textInfo and textInfo['posres'] != []:
        postag = textInfo['posres']
        pos_type = "人工标注"
    elif 'auto_pos' in textInfo:
        postag = textInfo['auto_pos']
        pos_type = "自动标注"
    else:
        pos_type = "暂无"

    seg = textInfo['segres']
    segpos = []
    if postag:
        for index, (s, p) in enumerate(zip(seg, postag)):
            segpos.append("/".join([s, p, str(index)]))
    else:
        for index, s in enumerate(seg):
            segpos.append(s + "/" + str(index))
    segpos = " ".join(segpos)
    textInfo['segpos'] = segpos
    # amr tag type
    if 'amr' in textInfo and textInfo['amr'].strip()!="":
        amr_type="人工标注"
    else:                  
        textInfo['amr']= ""
        amr_type="暂无标注"

    if request.method=='GET':  
        return render_to_response("TagAMR.html",
                            {"amr_type":amr_type,
                            "pos_type":pos_type,
                            'textInfoJson':json.dumps(textInfo),
                            "textInfo": textInfo,
                            'questionIndex':questionIndex,
                            'lastIndex':lastIndex,
                            'thisIndex':globalIndex,
                            'nextIndex':nextIndex,
                            'papertype':papertype,
                            'papername':papername,
                            'allValidIndex':json.dumps(allValidIndex),
                             'username': username
                             })

    elif request.method=="POST" and "generateAMR" in request.POST:   #自动生成整张试卷所有试题文本的成分分析结果
        input_sentences_goldseg=[]     

        for question in paperInfo['Questions']:
            for ctext in question[textFieldName]:
                input_sentences_goldseg.append(" ".join(ctext['segres']))

        #自动amr parsing
        print "AMR Parsing..."
        timestamp=time.time()
        timestamp=str(timestamp).replace(".","")
        
        infilename="SingleSentenceFiles/"+timestamp+".AMR.in"            
        tmpfile=open(infilename, "w")
        for seg in input_sentences_goldseg:
            tmpfile.write(seg.encode("utf-8") + "\n")
        tmpfile.close()

        outfilename="SingleSentenceFiles/"+timestamp+".AMR.out"
        
        # AMR automatic parsing
        # remain to be implemented

        #将自动分析的结果写回数据库
        '''
        paperInfo=dataCollection.find_one({'testpaperName':papername})  
        outfile=open(outfilename,"r")
        for question in paperInfo['Questions']:
            for ctext in question[textFieldName]:            
                ctext["auto_bpres"]=outfile.readline().decode("utf-8").strip()
                if 'auto_conpparse_valid' in ctext:
                    del ctext['auto_conpparse_valid']
                if globalIndex==ctext[globalIndexFieldName]:
                    textInfo['conpparse']=ctext['auto_bpres']
                    tagtype="自动标注结果"
        outfile.close()
        '''

        #删除相关文件
        os.remove(infilename)
        os.remove(outfilename)

        paperInfo['States']['auto_amr'] = False

        dataCollection.save(paperInfo)

        return render_to_response("TagAMR.html",
                            {"amr_type":amr_type,
                            "pos_type":pos_type,
                            'textInfoJson':json.dumps(textInfo),
                            "textInfo": textInfo,
                            'questionIndex':questionIndex,
                            'lastIndex':lastIndex,
                            'thisIndex':globalIndex,
                            'nextIndex':nextIndex,
                            'papertype':papertype,
                            'papername':papername,
                            'allValidIndex':json.dumps(allValidIndex),
                             'username': username
                             })

    elif request.method=='POST':
        tagInfo={}
        tagInfo['amr']=request.POST.get("amr_input_name")
        print tagInfo
        username=request.POST.get("username_name")

        if "save_btn" in request.POST:
            if saveTagInfoToDB(papername,papertype,globalIndex,tagInfo,username):
                checkGlobalTagState(papername,papertype)
                response = HttpResponseRedirect('./TagAMR?papername='+papername+"&papertype="+papertype+"&"+globalIndexFieldName+"="+globalIndex)
                response.set_cookie("username", username.strip(), 3600)
                return response
            else:
                return HttpResponse("保存出错")
        elif "saveAndNext_btn" in request.POST:
            if saveTagInfoToDB(papername,papertype,globalIndex,tagInfo,username):
                checkGlobalTagState(papername,papertype)
                nextIndex=checkAndFindTextInfoInDB(papername,papertype,globalIndex)[3]
                response = HttpResponseRedirect('./TagAMR?papername='+papername+"&papertype="+papertype+"&"+globalIndexFieldName+"="+nextIndex)
                response.set_cookie("username", username.strip(), 3600)
                return response
            else:
                return HttpResponse("保存出错")


def checkAndFindTextInfoInDB(papername,papertype,globalIndex):
    # 连接数据库
    conn = mongoConnection.connect_mongodb()
    
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

    for question in paperInfo['Questions']:
        for ctext in question[textFieldName]:
            allValidIndex.append(ctext[globalIndexFieldName])
            if findFlag==True and nextFlag==False:   #只有在nextFlag为False的时候才对nextIndex赋值
                nextIndex=ctext[globalIndexFieldName]
                nextFlag=True
            if findFlag==True:
                continue
            if globalIndex==ctext[globalIndexFieldName]:        
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
    # 连接数据库
    conn = mongoConnection.connect_mongodb()
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
                    ctext['amr_tagger']=username
                    ctext['amr']=tagInfo['amr']

                    print "save amr here...."

        dataCollection.save(paperInfo)
    except Exception, e:
        print e
        print traceback.format_exc()
        return False
    
    return True

def checkGlobalTagState(papername,papertype):
    # 连接数据库
    conn = mongoConnection.connect_mongodb()
    GeoPaperDB=conn['GeoPaper']
    choiceCollection=GeoPaperDB['ChoiceData']
    
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

    conp_state=True

    taggers={}
    for question in paperInfo['Questions']:
        for ctext in question[textFieldName]:
            if 'amr' not in ctext or ctext['amr']=="":
                conp_state=False
            else:
                if ctext['amr_tagger'] not in taggers:
                    taggers[ctext['amr_tagger']]=1
                else:
                    taggers[ctext['amr_tagger']]+=1

    paperInfo['relativeUsernames']['amr_tagger']=list(taggers)
        
    paperInfo['States']['amr']=conp_state

    dataCollection.save(paperInfo)

    return paperInfo['States']