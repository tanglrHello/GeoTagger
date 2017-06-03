#coding=utf-8
from django.shortcuts import render,render_to_response
from django.http import HttpResponse

import mongoConnection
from . import geoProcessor

# Create your views here.
def tagPos(request):
    # 连接数据库
    conn = mongoConnection.connect_mongodb()

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
                seg_tl.append(" ".join(ctext['segres']))
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

    elif request.method=="POST" and "generatePOS" in request.POST:    # 自动生成词性候选标注
        pos_input_sentences=[]
        for question in paperInfo['Questions']:
            for ctext in question[textFieldName]:
                pos_input_sentences.append(" ".join(ctext['segres']))

        # 自动分词
        geo_processor=geoProcessor.geo_Processor()
        segpos_output_sentences=geo_processor.process(pos_input_sentences, 5)        # 接口5（分词-》词性）
        segpos_output_sentences = [line.strip() for line in segpos_output_sentences]

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
                                 "segtl_pos":zip(pos_input_sentences,segpos_output_sentences),
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
                seg_tl.append(" ".join(ctext['segres']))

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




