#coding=utf-8
from django.shortcuts import render,render_to_response
from django.http import HttpResponse

import pymongo
import time

from . import geoProcessor

# Create your views here.
def tagPos(request):
    #连接数据库
    configFile=open("static/config.txt",'r')
    mongoIP=configFile.readline().split("\t")[1].strip()
    mongoPort=int(configFile.readline().split("\t")[1].strip())
    conn=pymongo.Connection(mongoIP,mongoPort)

    GeopaperDB=conn['GeoPaper']

    papername=request.GET['papername']
    papertype=request.GET['papertype']

    fieldNames=['goldtimes','goldlocs','goldterms','goldquants']
    appendix=['_time',"_loc","_term","_num"]
    
    dataCollection=None
    textFieldName=None
    if papertype=="choice":
        dataCollection=GeopaperDB['ChoiceData']
        textFieldName="combinedTexts"
    elif papertype=="subjective":
        dataCollection=GeopaperDB['SubjectiveData']
        textFieldName="subQuestions"

    paperInfo=dataCollection.find_one({'testpaperName':papername})

    if not paperInfo:
        return HttpResponse("没有这份试卷")

    if request.method=="POST" and "submitPOS" in request.POST:   #提交词性标注结果
        #保存标注者信息
        username=request.POST['username_name']
        paperInfo['relativeUsernames']['pos_tagger']=username

        seg_tl=[]
        pos=[]

        index=0
        for question in paperInfo['Questions']:
            for ctext in question[textFieldName]:
                #给分词结果加上时间地点标注结果
                timedict={}
                locdict={}
                termdict={}
                quantdict={}
                for t in ctext['goldtimes']:
                    timedict[t]=1
                for l in ctext['goldlocs']:
                    locdict[l]=1
                for t in ctext['goldterms']:
                    termdict[t]=1
                for q in ctext['goldquants']:
                    quantdict[q]=1


                segstr=""
                for i,w in enumerate(ctext['segres']):
                    if i in timedict:
                        segstr+=w+"_time "
                    elif i in locdict:
                        segstr+=w+"_loc "
                    elif i in termdict:
                        segstr+=w+"_term "
                    elif i in quantdict:
                        segstr+=w+"_num "
                    else:
                        segstr+=w+" "
                seg_tl.append(segstr)

                posinfo=request.POST[str(index)+"_pos"]

                
                newpos=[wp.rsplit("_",1)[1] for wp in posinfo.split()]
                if ctext['posres']!=newpos and 'bpres' in ctext and ctext['bpres']!="":
                    ctext['conpparse_valid']=False
                    ctext['auto_conpparse_valid']=False
                    ctext['auto_template_valid']=False

                    paperInfo['States']['bpres']=False
                    paperInfo['States']['autoTemplate']=False
                
                ctext['posres']=newpos

                pos.append(posinfo)
                index+=1

        #修改试卷标注状态
        paperInfo['States']['pos']=True

        dataCollection.save(paperInfo)

        return render_to_response("TagPos.html",
                                {'pos_tagger':username,
                                 'States':paperInfo['States'],
                                 "restype":"人工标注",
                                 "segtl_pos":zip(seg_tl,pos),
                                 'papername':papername,
                                 'papertype':papertype})

    elif request.method=="POST" and "generatePOS" in request.POST:    #自动生成词性候选标注
        pos_input_sentences=[]
        for question in paperInfo['Questions']:
            for ctext in question[textFieldName]:
                tl_str=" ".join(ctext['segres'])
                pos_input_sentences.append(tl_str)

        #自动分词
        geo_processor=geoProcessor.geo_Processor()
        segpos_output_sentences=geo_processor.process(pos_input_sentences,5)        #接口5（分词-》词性）

        #解析成前端需要的格式
        segTexts=[]
        segposTexts=[]
        #print segpos_output_sentences[0].decode("utf-8")
        for s in segpos_output_sentences:
            segstr=""
            segposstr=""

            for index,p in enumerate(s.decode("utf-8").strip().split()):
                word=p.split("_")[0]
                pos=p.split("_")[1]

                segposstr+=p+" "
                
                if pos=="time" or pos=="loc" or pos=="term" or pos=="num":    #时间地点的标注会在页面左侧的分词结果中显示
                    segstr+=p+" "
                else:
                    segstr+=word+" "
            segstr=segstr[:-1]
            segposstr=segposstr[:-1]
            segTexts.append(segstr)
            segposTexts.append(segposstr)
            

        #将自动分析的词性放入数据库
        paperInfo=dataCollection.find_one({'testpaperName':papername})

        index=0
        for question in paperInfo['Questions']:
            for ctext in question[textFieldName]:
                ctext['auto_pos']=[p.split("_")[1] for p in segpos_output_sentences[index].split()]
                index+=1
        dataCollection.save(paperInfo)

        return render_to_response("TagPos.html",
                                {'States':paperInfo['States'],
                                 "restype":"自动标注",
                                 "segtl_pos":zip(segTexts,segposTexts),
                                 'papername':papername,
                                 'papertype':papertype})

    else:    #直接显示页面
        seg_tl=[]
        pos=[]

        #必须是手动标注完分词和时间地点后才来标注词性
        if not (paperInfo['States']['time']==True and paperInfo['States']['loc']==True):
            return HttpResponse('请先完成对该试卷的时间地点标注')

        #获取标注者信息
        username=None
        if 'relativeUsernames' in paperInfo and 'pos_tagger' in paperInfo['relativeUsernames']:
            username=paperInfo['relativeUsernames']['pos_tagger']

        restype=""
        for question in paperInfo['Questions']:
            for ctext in question[textFieldName]:
                #给分词结果加上时间地点标注结果
                dicts=[]
                for fn in fieldNames:
                    dicts.append({})

                for i,field in enumerate(fieldNames):
                    if field in ctext:
                        for x in ctext[field]:
                            dicts[i][x]=1

                segstr=""
                for index,w in enumerate(ctext['segres']):
                    for i,d in enumerate(dicts):
                        if index in d:
                            segstr+=w+appendix[i]+" "
                            break
                    else:
                        segstr+=w+" "

                seg_tl.append(segstr)

                #读取人工标注的词性
                if 'posres' in ctext and ctext['posres']!=[]:
                    restype="人工标注"
                    pos.append(" ".join([s+"_"+p for s,p in zip(ctext['segres'],ctext['posres'])]))
                elif "auto_pos" in ctext:   #没有人工标注的词性，查找是否有自动标注的词性
                    restype="自动标注"
                    pos.append(" ".join([s+"_"+p for s,p in zip(ctext['segres'],ctext['auto_pos'])]))
                else:   #没有自动生成的词性，显示默认的词性
                    restype="暂无标注（除了时间地点术语数量词，所有词性设置为默认的NN）"
                    posstr=""
                    for index,w in enumerate(ctext['segres']):
                        for i,d in enumerate(dicts):
                            if index in d:
                                posstr+=w+appendix[i]+" "
                                break
                        else:
                            posstr+=w+"_NN "
                        
                    posstr=posstr[:-1]  #删除最后的空格
                    pos.append(posstr)
        if username==None:
            return render_to_response("TagPos.html",
                                    {'States':paperInfo['States'],
                                     "restype":restype,
                                     "segtl_pos":zip(seg_tl,pos),
                                     'papername':papername,
                                     'papertype':papertype})
        else:
            return render_to_response("TagPos.html",
                                    {'pos_tagger':username,
                                     'States':paperInfo['States'],
                                     "restype":restype,
                                     "segtl_pos":zip(seg_tl,pos),
                                     'papername':papername,
                                     'papertype':papertype})




