#coding=utf-8
from django.shortcuts import render,render_to_response
from django.http import HttpResponse

import pymongo
import json
import time
import os,shutil
import zipfile
import StringIO

from . import getConfig

# Create your views here.
def browseByPaper(request):
    #连接数据库
    configFile=open("static/config.txt",'r')
    mongoIP=configFile.readline().split("\t")[1].strip()
    mongoPort=int(configFile.readline().split("\t")[1].strip())
    conn=pymongo.Connection(mongoIP,mongoPort)

    GeopaperDB=conn['GeoPaper']

    papertype="choice"
    if 'papertype' in request.GET:
        papertype=request.GET.get("papertype")

    if papertype=="choice":
        dataCollection=GeopaperDB['ChoiceData']
    else:
        dataCollection=GeopaperDB['SubjectiveData']

    #获取模板、标注字段配置信息
    tagFields_Info=getConfig.getTagFieldConfig(papertype)
    #获取显示状态的字段信息
    showStateFields_Info=getConfig.getShowStateFieldConfid(papertype)
    
    if request.method=='POST' and "outcontent" in request.POST:   #导出数据请求
        papersToExtract=request.POST.getlist('choosePaper')
        outContent=request.POST.getlist('outcontent')
        
        #用来创建此次下载的临时文件夹（作为文件夹名的一部分）
        timestamp=time.time()
        timestamp=str(timestamp).replace(".","")
        #创建文件夹
        outPath="TestPaperData/DownloadData/"+timestamp+"/"
        os.mkdir(outPath)
            
        for paperName in papersToExtract:
            paper=dataCollection.find_one({'testpaperName':paperName})
            
            tagContent=outContent[:]
            #如果有拆分信息，单独处理（仅对选择题有效）
            '''
            if u"splitinfoChk" in outContent:
                #写文件：
                split_tmpf=open(outPath+paperName+"."+papertype+".split.csv","w")
                for question in paper['Questions']:
                    for textInfo in question['combinedTexts']:
                        split_tmpf.write(str(question['QuestionIndex'])+"-"+textInfo['number'].encode('utf-8')+",")
                        split_tmpf.write(textInfo['text'].encode('utf-8')+",")
                        split_tmpf.write(str(textInfo['splitinfo']).encode("utf-8")+"\n")
                split_tmpf.close()
                
                outContent.remove(u"splitinfoChk")
                tagContent=outContent[:]
                outContent.append(u"splitinfoChk")
            '''
            
            #标注信息
            if len(tagContent)>0:
                #写文件：
                tag_tmpf=open(outPath+paperName+"."+papertype+".tag.csv","w")
                #写表头
                for index,content in enumerate(tagContent):
                    for tagField in tagFields_Info:
                        if content==tagField[0]+"Chk":
                            tag_tmpf.write(tagField[1])

                    if index<len(outContent)-1:
                        tag_tmpf.write(",")
                tag_tmpf.write("\n")
            

                textsField=None
                if papertype=="choice":
                    textsField="combinedTexts"
                elif papertype=="subjective":
                    textsField="subQuestions"

                #写标注信息
                for question in paper['Questions']:
                    for textInfo in question[textsField]:
                        for index,content in enumerate(tagContent):
                            if content=="numberChk":
                                if papertype=="choice":
                                    tag_tmpf.write(str(question['QuestionIndex'])+"-"+textInfo['number'].encode('utf-8'))
                                elif papertype=="subjective":
                                    tag_tmpf.write(str(question['number'])+"-"+str(textInfo['number']))
                            else:
                                for tagField in tagFields_Info:
                                    if content==tagField[0]+"Chk":
                                        #如果有依赖关系，进行判断，如果无效则不写入文件
                                        if tagField[3]!=None and tagField[3] in textInfo and textInfo[tagField[3]]==False:   
                                            tag_tmpf.write("")
                                        elif tagField[0] in textInfo:
                                            if tagField[2]=="string":
                                                tag_tmpf.write(textInfo[tagField[0]].encode("utf-8"))
                                            elif tagField[2]=="list_num":
                                                tag_tmpf.write(" ".join([str(i) for i in textInfo[tagField[0]]]).encode("utf-8"))
                                            elif tagField[2]=="list_string":
                                                tag_tmpf.write(" ".join(textInfo[tagField[0]]).encode("utf-8"))
                                            elif tagField[2]=="list_string_index":
                                                tag_tmpf.write(" ".join(textInfo[tagField[0]]).encode("utf-8"))
                                        else:
                                            tag_tmpf.write("")

                            if index<len(outContent)-1:
                                tag_tmpf.write(",")
                        tag_tmpf.write("\n")

                #关闭文件
                tag_tmpf.close()
        
        #打包生成的所有文件
        source_dir=outPath
        buffer=StringIO.StringIO()
        z=zipfile.ZipFile(buffer,"w",zipfile.ZIP_DEFLATED)
        files=os.listdir(outPath)
        for f in files:
            file=open(outPath+f,'r')
            z.writestr(f,file.read())
            file.close()
        z.close()
        buffer.seek(0)
        
        #返回压缩包文件
        response=HttpResponse(buffer.read())
        response['Content-Type']="application/x-zip"
        response['Content-Disposition']='attachment; filename='+timestamp+".byPaper."+papertype+".zip"

        #删除未打包的文件夹
        shutil.rmtree(source_dir)
        
        return response
    elif request.method=='POST' and "query_kw_name" in request.POST:    #检索请求
        query_kw=request.POST['query_kw_name']
        print query_kw
        paperInfoData=getData(conn,papertype,query_kw)
        return render_to_response("BrowseByPaper.html",
                                {'paperInfoData':paperInfoData,
                                 'papertype':papertype,
                                 'tagFields_config':tagFields_Info,
                                 "showStateFields_Info":showStateFields_Info})

        
    elif request.method=="GET":
        paperInfoData=getData(conn,papertype,"")
        return render_to_response("BrowseByPaper.html",
                                {'paperInfoData':paperInfoData,
                                 'papertype':papertype,
                                 'tagFields_config':tagFields_Info,
                                 "showStateFields_Info":showStateFields_Info})

def getData(conn,papertype,paperName_kw):
    GeopaperDB=conn['GeoPaper']
    if papertype=="choice":
        dataCollection=GeopaperDB['ChoiceData']
    else:
        dataCollection=GeopaperDB['SubjectiveData']

    papers=dataCollection.find().sort("uploadTimestamp",pymongo.DESCENDING)
    paperInfoData=[]
    for paper in papers:
        if paperName_kw!="":
            if paperName_kw not in paper['testpaperName']:
                continue
        data={}
        data['testpaperName']=paper['testpaperName']
        data['uploadTime']=paper['uploadTime']
        data['relativeUsernames']=paper['relativeUsernames']

        if papertype=='subjective':
            smallQuestionNum=0
            for q in paper['Questions']:
                smallQuestionNum+=len(q['subQuestions'])
            data['QuestionNum']=smallQuestionNum
        elif papertype=='choice':
            data['QuestionNum']=len(paper['Questions'])

        if 'template_tagger' in data['relativeUsernames']:
            data['relativeUsernames']['template_tagger']=" ".join(data['relativeUsernames']['template_tagger'])
        if 'conpparse_tagger' in data['relativeUsernames']:
            data['relativeUsernames']['conpparse_tagger']=" ".join(data['relativeUsernames']['conpparse_tagger'])
        if 'question_tagger' in data['relativeUsernames']:
            data['relativeUsernames']['question_tagger']=" ".join(data['relativeUsernames']['question_tagger'])
        if 'new_template_tagger' in data['relativeUsernames']:
            data['relativeUsernames']['new_template_tagger']=" ".join(data['relativeUsernames']['new_template_tagger'])

        data['States']=paper['States']
        if 'term' not in data['States']:
            data['States']['term']=False
        if 'quant' not in data['States']:
            data['States']['quant']=False
        if 'auto_bpres' not in data['States']:
            data['States']['auto_bpres']=False
        if 'autoTemplate' not in data['States']:
            data['States']['autoTemplate']=False
        if "questionInfo" not in data['States']:
            data['States']['questionInfo']=False
        if "topTemplate" not in data['States']:
            data['States']['topTemplate']=False
        if "secondTemplate" not in data['States']:
            data['States']['secondTemplate']=False

        paperInfoData.append(data)
    return paperInfoData