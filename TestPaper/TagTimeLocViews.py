#coding=utf-8
from django.shortcuts import render,render_to_response
from django.http import HttpResponse

import pymongo
import time

from . import geoProcessor

# Create your views here.
def tagTimeLoc(request):
    #连接数据库
    configFile=open("static/config.txt",'r')
    mongoIP=configFile.readline().split("\t")[1].strip()
    mongoPort=int(configFile.readline().split("\t")[1].strip())
    conn=pymongo.Connection(mongoIP,mongoPort)

    GeopaperDB=conn['GeoPaper']

    papername=request.GET['papername']
    papertype=request.GET['papertype']

    dataCollection=None
    textFieldName=None
    if papertype=="choice":
        dataCollection=GeopaperDB['ChoiceData']
        textFieldName="combinedTexts"
    elif papertype=="subjective":
        dataCollection=GeopaperDB['SubjectiveData']
        textFieldName="subQuestions"

    # change all time loc infos into string
    for paperInfo in dataCollection.find():
        for question in paperInfo['Questions']:
            for ctext in question['combinedTexts']:
                if type(ctext['goldtimes'])!=type(u"string"):
                    print "1"
                    if 'goldtimes' in ctext:
                        ctext['goldtimes'] = " ".join([str(x) for x in ctext['goldtimes']])
                    if 'goldlocs' in ctext:
                        ctext['goldlocs'] = " ".join([str(x) for x in ctext['goldlocs']])
                    if 'goldquants' in ctext:
                        ctext['goldquants'] = " ".join([str(x) for x in ctext['goldquants']])
                    if 'goldterms' in ctext:
                        ctext['goldterms'] = " ".join([str(x) for x in ctext['goldterms']])
                else:
                    print "?"
                    break

        #dataCollection.save(paperInfo)

    paperInfo=dataCollection.find_one({'testpaperName':papername})

    if not paperInfo:
        return HttpResponse("没有这份试卷")
    #必须是手动分词标注完了才来标注时间地点(这里使用粗粒度的版本)
    if paperInfo['States']['seg']==False:
        return HttpResponse("请先完成对改试卷的分词标注")
    if paperInfo['States']['pos']==True:
            return HttpResponse(u"<h1>本试卷已完成词性标注，不能再标注实体术语</h1><br><a href='./TagEachField.html?papername="+papername+u"'>前往单项标注页面</a>")

    fieldNames=['goldtimes','goldlocs','goldterms','goldquants']
    auto_fieldNames=["auto_time",'auto_loc','auto_term','auto_quant']
    names=['time',"loc","term","quant"]

    if request.method=='POST' and "submitTimeLoc" in request.POST:   #提交时间地点术语数量词标注结果
        paperInfo=dataCollection.find_one({'testpaperName':papername})

        segs=[]

        tltq_lists=[]
        for n in names:
            tltq_lists.append([])
        
        #保存标注者信息
        username=request.POST['username_name']
        paperInfo['relativeUsernames']['timeloc_tagger']=username
        
        index=0        
        for question in paperInfo['Questions']:
            for ctext in question[textFieldName]:
                segs.append(" ".join([w+"_"+str(i) for w,i in zip(ctext['segres'],range(len(ctext['segres'])))]))
                for i,fn in enumerate(fieldNames):
                    ctext[fn]=request.POST[str(index)+"_"+names[i]]

                for i,l in enumerate(tltq_lists):
                    l.append(ctext[fieldNames[i]])

                index+=1

        #修改试卷标注状态
        paperInfo['States']['time']=True
        paperInfo['States']['loc']=True
        paperInfo['States']['term']=True
        paperInfo['States']['quant']=True

        dataCollection.save(paperInfo)
        return render_to_response("TagTimeLoc.html",
                                {'timeloc_tagger':username, 
                                 'States':paperInfo['States'],
                                 "restype":u"人工标注",
                                 "seg_time_loc":zip(segs,tltq_lists[0],tltq_lists[1],tltq_lists[2],tltq_lists[3]),
                                 'papername':papername,
                                 'papertype':papertype})

    elif request.method=='POST' and "generateTimeLoc" in request.POST:    #自动生成时间地点候选标注
        tl_input_sentences=[]
        for question in paperInfo['Questions']:
            for ctext in question[textFieldName]:
                tl_input_sentences.append(" ".join(ctext['segres']))

        #自动分词
        geo_processor=geoProcessor.geo_Processor()
        segtl_output_sentences=geo_processor.process(tl_input_sentences,4)        #接口4（分词结果-》含时间地点的分词）
        
        #对时间地点的结果进行处理
        AllSegStrs=[]

        All_tltq_lists=[]
        for n in names:
            All_tltq_lists.append([])

        for s in segtl_output_sentences:
            tag_lists=[]
            for n in names:
                tag_lists.append([])

            tmpstr=""
            s=s.decode("utf-8")
            for index,w in enumerate(s.strip().split()):                                
                if "_" in w:
                    tmpstr+=w.split("_")[0]+"_"+str(index)+" "
                    for i,n in enumerate(names):
                        if w.split("_")[1]==n:
                            tag_lists[i].append(index)
                            break
                    else:
                        print "error"
                        print w
                        return HttpResponse("出错了！")
                else:
                    tmpstr+=w+"_"+str(index)+" "
            AllSegStrs.append(tmpstr)

            for i,atl in enumerate(All_tltq_lists):
                atl.append(tag_lists[i])

        #将自动分析的时间地点放入数据库
        paperInfo=dataCollection.find_one({'testpaperName':papername})

        index=0
        for question in paperInfo['Questions']:
            for ctext in question[textFieldName]:
                for i,afn in enumerate(auto_fieldNames):
                    ctext[afn]=All_tltq_lists[i][index]                  
                index+=1
        dataCollection.save(paperInfo)

        #时间地点格式处理，供前端显示
        All_tltq_str_lists=[]
        for i in range(len(All_tltq_lists)):
            All_tltq_str_lists.append([" ".join([str(i) for i in t]) for t in All_tltq_lists[i]])

        return render_to_response("TagTimeLoc.html",
            {'States':paperInfo['States'],
             "restype":u"自动标注",
             "seg_time_loc":zip(AllSegStrs,All_tltq_str_lists[0],All_tltq_str_lists[1],All_tltq_str_lists[2],All_tltq_str_lists[3]),
             'papername':papername,
             'papertype':papertype})

    else:    #直接显示页面
        paperInfo=dataCollection.find_one({'testpaperName':papername})        

        #标注者信息
        username=None
        if 'relativeUsernames' in paperInfo and 'timeloc_tagger' in paperInfo['relativeUsernames']:
            username=paperInfo['relativeUsernames']['timeloc_tagger']

        seg=[]

        tltq_lists=[]
        for n in names:
            tltq_lists.append([])

        restype=""

        autoTagFlag=False
        for question in paperInfo['Questions']:
            for ctext in question[textFieldName]:                   
                #给分词结果加上index
                seg.append(" ".join([w+"_"+str(i) for w,i in zip(ctext['segres'],range(len(ctext['segres'])))]))

                res_strs={}
                for n in names:
                    res_strs[n]=""

                if paperInfo['States']['time']==True and paperInfo['States']['loc']==True:  #有人工标注的时间地点
                    for index,fn in enumerate(fieldNames):
                        if fn in ctext:
                            res_strs[names[index]]=ctext[fn]
                        else:
                            res_strs=""

                else:   
                    #如果没有人工标注的时间，查找是否有自动标注的时间
                    for index,afn in enumerate(auto_fieldNames):
                        if afn in ctext:
                            autoTagFlag=True
                            res_strs[names[index]]=" ".join([str(i) for i in ctext[afn]])
                        else:
                            termstr=""
                            quantstr=""
                
                for index,l in enumerate(tltq_lists):
                    l.append(res_strs[names[index]])

        if paperInfo['States']['time']==True:
            restype=u"人工标注"
        elif autoTagFlag==True:
            restype=u"自动标注"
        else:
            restype=u"无标注"
        if username==None:
            return render_to_response("TagTimeLoc.html",
                                    {'States':paperInfo['States'],
                                     "restype":restype,
                                     "seg_time_loc":zip(seg,tltq_lists[0],tltq_lists[1],tltq_lists[2],tltq_lists[3]),
                                     'papername':papername,
                                     'papertype':papertype})
        else:
            return render_to_response("TagTimeLoc.html",
                                    {'timeloc_tagger':username,
                                    'States':paperInfo['States'],
                                    "restype":restype,
                                    "seg_time_loc":zip(seg,tltq_lists[0],tltq_lists[1],tltq_lists[2],tltq_lists[3]),
                                    'papername':papername,
                                    'papertype':papertype})
    